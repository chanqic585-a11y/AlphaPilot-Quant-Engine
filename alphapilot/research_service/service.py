"""Bounded campaign runner that stops before execution-track side effects."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Protocol

from alphapilot.evolution.registry.hashing import stable_hash

from .lease import ResearchServiceLease, ResearchServiceLeaseUnavailable
from .policy import ResearchServicePolicy
from .state import ResearchServiceStateStore


class ResearchExecutor(Protocol):
    def execute(self, job: dict[str, object]) -> dict[str, object]: ...


class ResearchService:
    def __init__(
        self,
        *,
        policy: ResearchServicePolicy,
        state_store: ResearchServiceStateStore,
        executor: ResearchExecutor,
        lease_path: Path,
        receipt_path: Path,
        owner: str,
        pause_file: Path | None = None,
    ) -> None:
        self.policy = policy
        self.state_store = state_store
        self.executor = executor
        self.lease_path = Path(lease_path)
        self.receipt_path = Path(receipt_path)
        self.owner = owner
        self.pause_file = Path(pause_file) if pause_file else None

    def enqueue(
        self,
        *,
        campaign_id: str,
        family_ids: tuple[str, ...],
        candidate_ids: tuple[str, ...],
        queued_at: str,
    ) -> dict[str, Any]:
        if len(family_ids) > self.policy.max_families_per_campaign:
            raise ValueError("family_budget_exceeded")
        if len(candidate_ids) > self.policy.max_candidates_per_campaign:
            raise ValueError("candidate_budget_exceeded")
        if not campaign_id or not family_ids or not candidate_ids:
            raise ValueError("campaign_identity_incomplete")

        state = self.state_store.load_or_initialize(now=queued_at)
        if any(job["campaignId"] == campaign_id for job in state["jobs"]):
            raise ValueError("campaign_already_registered")
        if int(state.get("campaignsEnqueued") or 0) >= self.policy.max_campaigns:
            raise ValueError("campaign_budget_exhausted")
        job = {
            "campaignId": campaign_id,
            "familyIds": list(family_ids),
            "candidateIds": list(candidate_ids),
            "queuedAt": queued_at,
            "status": "queued",
            "startedAt": None,
            "completedAt": None,
            "result": None,
        }
        state["jobs"].append(job)
        state["campaignsEnqueued"] = int(state.get("campaignsEnqueued") or 0) + 1
        state["updatedAt"] = queued_at
        self.state_store.save(state)
        return job

    def run_cycle(self, *, now: str) -> dict[str, Any]:
        lease = ResearchServiceLease(self.lease_path, owner=self.owner)
        try:
            lease.acquire(acquired_at=now)
        except ResearchServiceLeaseUnavailable as error:
            return {
                **self._zero_effect_result(status="lease_unavailable", now=now),
                "ownerAudit": error.owner_audit,
            }

        try:
            state = self.state_store.load_or_initialize(now=now)
            if self.pause_file and self.pause_file.exists():
                pending = next(
                    (
                        job
                        for job in state["jobs"]
                        if job.get("status") in {"queued", "running"}
                    ),
                    None,
                )
                pause_result = self._zero_effect_result(
                    status="paused",
                    now=now,
                    campaign_id=(
                        str(pending.get("campaignId") or "") if pending else None
                    ),
                )
                if pending is not None:
                    pending["status"] = "queued"
                    pending["completedAt"] = None
                    pending["result"] = pause_result
                    state["status"] = "paused"
                    state["updatedAt"] = now
                    self.state_store.save(state)
                return self._append_receipt(pause_result)
            if state.get("status") == "waiting_exact_release_approval":
                return self._append_receipt(
                    self._zero_effect_result(
                        status="waiting_exact_release_approval",
                        now=now,
                    )
                )

            queued = next(
                (job for job in state["jobs"] if job.get("status") == "queued"),
                None,
            )
            if queued is None:
                state["status"] = "idle"
                state["updatedAt"] = now
                self.state_store.save(state)
                return self._append_receipt(
                    self._zero_effect_result(status="idle", now=now)
                )

            queued["status"] = "running"
            queued["startedAt"] = now
            state["status"] = "running"
            state["updatedAt"] = now
            self.state_store.save(state)

            result = dict(self.executor.execute(dict(queued)))
            self._validate_execution_boundary(result)
            executor_status = str(result.get("status") or "").strip()
            service_status = (
                "waiting_exact_release_approval"
                if executor_status == "immutable_release_ready"
                else executor_status
            )
            if not service_status:
                raise ValueError("research_executor_status_missing")

            resumable_pause = executor_status == "paused"
            queued["status"] = "queued" if resumable_pause else executor_status
            queued["completedAt"] = None if resumable_pause else now
            queued["result"] = result
            state["status"] = service_status
            state["updatedAt"] = now
            self.state_store.save(state)
            receipt = {
                "schemaVersion": "v35_research_cycle_receipt_v1",
                "status": service_status,
                "cycleAt": now,
                "campaignId": queued["campaignId"],
                "campaignHash": str(result.get("campaignHash") or ""),
                "artifactPath": str(result.get("artifactPath") or ""),
                "policyHash": self.policy.policy_hash,
                "candidateCount": int(result.get("candidateCount") or 0),
                "eligibleCandidateCount": int(
                    result.get("eligibleCandidateCount") or 0
                ),
                "trialCount": int(result.get("trialCount") or 0),
                "blockedFamilyCount": int(
                    result.get("blockedFamilyCount") or 0
                ),
                "formalRunCount": int(result.get("formalRunCount") or 0),
                "resultReadCount": int(result.get("resultReadCount") or 0),
                "lockedOosReadCount": int(result.get("lockedOosReadCount") or 0),
                "releaseCount": int(result.get("releaseCount") or 0),
                "pausedStage": str(result.get("pausedStage") or ""),
                "completedTrialCount": int(
                    result.get("completedTrialCount") or 0
                ),
                "demoReleaseCount": 0,
                "approvalCount": 0,
                "demoArm": False,
                "orderCount": 0,
                "tradeApiUsed": False,
                "withdrawApiUsed": False,
                "privateAccountReadUsed": False,
            }
            return self._append_receipt(receipt)
        finally:
            lease.release()

    @staticmethod
    def _validate_execution_boundary(result: dict[str, object]) -> None:
        prohibited_truthy = (
            "demoReleaseCount",
            "approvalCount",
            "demoArm",
            "orderCount",
            "tradeApiUsed",
            "withdrawApiUsed",
            "privateAccountReadUsed",
        )
        if any(bool(result.get(field)) for field in prohibited_truthy):
            raise ValueError("research_executor_crossed_execution_boundary")

    def _append_receipt(self, core: dict[str, Any]) -> dict[str, Any]:
        previous_hash: str | None = None
        if self.receipt_path.is_file():
            lines = [
                line
                for line in self.receipt_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            if lines:
                previous_hash = str(
                    json.loads(lines[-1]).get("receiptHash") or ""
                ) or None
        receipt = {**core, "previousReceiptHash": previous_hash}
        receipt["receiptHash"] = stable_hash(receipt, prefix="v35_research_cycle")
        self.receipt_path.parent.mkdir(parents=True, exist_ok=True)
        with self.receipt_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(receipt, ensure_ascii=False, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        return receipt

    @staticmethod
    def _zero_effect_result(
        *,
        status: str,
        now: str,
        campaign_id: str | None = None,
    ) -> dict[str, Any]:
        return {
            "schemaVersion": "v35_research_cycle_receipt_v1",
            "status": status,
            "cycleAt": now,
            "campaignId": campaign_id,
            "candidateCount": 0,
            "formalRunCount": 0,
            "resultReadCount": 0,
            "lockedOosReadCount": 0,
            "releaseCount": 0,
            "demoReleaseCount": 0,
            "approvalCount": 0,
            "demoArm": False,
            "orderCount": 0,
            "tradeApiUsed": False,
            "withdrawApiUsed": False,
            "privateAccountReadUsed": False,
        }
