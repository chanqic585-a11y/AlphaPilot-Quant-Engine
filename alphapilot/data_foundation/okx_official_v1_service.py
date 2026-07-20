"""Bounded due-cycle orchestration for the V34C public-data service."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from alphapilot.data_foundation.okx_official_v1_incremental import (
    OkxOfficialV1IncrementalCollector,
)
from alphapilot.data_foundation.okx_official_v1_quality_monitor import (
    OkxOfficialV1QualityMonitor,
)
from alphapilot.data_foundation.okx_official_v1_schedule import (
    OkxPublicCollectionPolicy,
    SchedulerLease,
    SchedulerLeaseUnavailable,
    SchedulerStateStore,
    TaskCadence,
    select_due_tasks,
)
from alphapilot.evolution.registry.hashing import stable_hash


def _parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"Timestamp must include a timezone: {value}")
    return parsed.astimezone(UTC)


def _bounded_error(error: BaseException) -> str:
    return f"{type(error).__name__}: {error}"[:512]


class OkxOfficialV1PublicDataService:
    def __init__(
        self,
        *,
        policy: OkxPublicCollectionPolicy,
        state_store: SchedulerStateStore,
        collector: OkxOfficialV1IncrementalCollector,
        quality_monitor: OkxOfficialV1QualityMonitor,
        lease_path: Path,
        cycle_ledger_path: Path,
        owner: str,
        pause_file: Path | None = None,
    ) -> None:
        self.policy = policy
        self.state_store = state_store
        self.collector = collector
        self.quality_monitor = quality_monitor
        self.lease_path = Path(lease_path)
        self.cycle_ledger_path = Path(cycle_ledger_path)
        self.owner = owner
        self.pause_file = Path(pause_file) if pause_file else None
        self._tasks_by_name = {task.name: task for task in policy.tasks}

    def run_due_cycle(self, *, now: str) -> dict[str, Any]:
        current_time = _parse_utc(now)
        if self.pause_file and self.pause_file.exists():
            return self._zero_effect_result(
                status="paused",
                now=now,
                extra={"pauseFile": str(self.pause_file.resolve())},
            )

        lease = SchedulerLease(self.lease_path, owner=self.owner)
        try:
            lease.acquire(acquired_at=now)
        except SchedulerLeaseUnavailable as error:
            return self._zero_effect_result(
                status="lease_unavailable",
                now=now,
                extra={"ownerAudit": error.owner_audit},
            )

        try:
            state = self.state_store.load_or_initialize(now=now)
            due_tasks = select_due_tasks(self.policy, state, now=now)
            executed: list[str] = []
            failed: list[str] = []
            results: dict[str, Any] = {}
            errors: dict[str, str] = {}

            for task_name in due_tasks:
                if task_name == "quality":
                    continue
                task = self._tasks_by_name[task_name]
                executed.append(task_name)
                self._mark_started(state, task_name, now)
                try:
                    result = self.collector.collect_task(task_name, now)
                except Exception as error:
                    message = _bounded_error(error)
                    errors[task_name] = message
                    failed.append(task_name)
                    self._mark_failed(state, task, current_time, message)
                else:
                    results[task_name] = result.to_dict()
                    self._mark_succeeded(
                        state,
                        task,
                        current_time,
                        artifact_path=result.artifact_path,
                        artifact_sha256=result.artifact_sha256,
                        row_count=result.row_count,
                        result_status=result.status,
                    )

            quality_artifacts: dict[str, str] = {}
            quality_status: str | None = None
            if "quality" in due_tasks:
                try:
                    report = self.quality_monitor.evaluate(now=now)
                    quality_artifacts = self.quality_monitor.write_report(report)
                    quality_status = report.status
                    executed.append("quality")
                    self._mark_succeeded(
                        state,
                        self._tasks_by_name["quality"],
                        current_time,
                        artifact_path=quality_artifacts.get("jsonPath"),
                        artifact_sha256=quality_artifacts.get("jsonSha256"),
                        row_count=report.artifact_count,
                        result_status=report.status,
                    )
                except Exception as error:
                    message = _bounded_error(error)
                    errors["quality"] = message
                    failed.append("quality")
                    executed.append("quality")
                    self._mark_failed(
                        state,
                        self._tasks_by_name["quality"],
                        current_time,
                        message,
                    )

            core = {
                "schemaVersion": "okx_official_v1_v34c_cycle_receipt_v1",
                "status": "completed_with_errors" if failed else "completed",
                "cycleAt": now,
                "policyHash": self.policy.policy_hash,
                "dueTasks": due_tasks,
                "executedTasks": executed,
                "failedTasks": failed,
                "results": results,
                "errors": errors,
                "qualityStatus": quality_status,
                "qualityArtifacts": quality_artifacts,
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
            return self._append_cycle_receipt(core)
        finally:
            lease.release()

    def record_operator_stop(self, *, now: str) -> dict[str, Any]:
        _parse_utc(now)
        return self._append_cycle_receipt(
            {
                "schemaVersion": "okx_official_v1_v34c_cycle_receipt_v1",
                "status": "stopped_by_operator",
                "cycleAt": now,
                "policyHash": self.policy.policy_hash,
                "dueTasks": [],
                "executedTasks": [],
                "failedTasks": [],
                "results": {},
                "errors": {},
                "qualityStatus": None,
                "qualityArtifacts": {},
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
        )

    def _mark_started(self, state: dict[str, Any], task_name: str, now: str) -> None:
        details = state["tasks"][task_name]
        details.update({"lastStartedAt": now, "lastStatus": "running", "lastError": None})
        state["updatedAt"] = now
        self.state_store.save(state)

    def _mark_succeeded(
        self,
        state: dict[str, Any],
        task: TaskCadence,
        current_time: datetime,
        *,
        artifact_path: str | None,
        artifact_sha256: str | None,
        row_count: int,
        result_status: str,
    ) -> None:
        completed_at = current_time.isoformat()
        state["tasks"][task.name].update(
            {
                "nextDueAt": (current_time + timedelta(seconds=task.interval_seconds)).isoformat(),
                "lastCompletedAt": completed_at,
                "lastStatus": "success",
                "lastResultStatus": result_status,
                "lastError": None,
                "consecutiveFailures": 0,
                "lastArtifactPath": artifact_path,
                "lastArtifactSha256": artifact_sha256,
                "lastRowCount": int(row_count),
            }
        )
        state["updatedAt"] = completed_at
        self.state_store.save(state)

    def _mark_failed(
        self,
        state: dict[str, Any],
        task: TaskCadence,
        current_time: datetime,
        message: str,
    ) -> None:
        details = state["tasks"][task.name]
        failures = int(details.get("consecutiveFailures") or 0) + 1
        retry_seconds = min(
            task.interval_seconds,
            task.retry_base_seconds * (2 ** min(failures - 1, 8)),
        )
        details.update(
            {
                "nextDueAt": (current_time + timedelta(seconds=retry_seconds)).isoformat(),
                "lastCompletedAt": current_time.isoformat(),
                "lastStatus": "failed",
                "lastError": message,
                "consecutiveFailures": failures,
                "lastRetryDelaySeconds": retry_seconds,
            }
        )
        state["updatedAt"] = current_time.isoformat()
        self.state_store.save(state)

    def _append_cycle_receipt(self, core: dict[str, Any]) -> dict[str, Any]:
        previous_hash: str | None = None
        if self.cycle_ledger_path.is_file():
            lines = [
                line
                for line in self.cycle_ledger_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            if lines:
                previous_hash = str(json.loads(lines[-1]).get("cycleHash") or "") or None
        receipt = {**core, "previousCycleHash": previous_hash}
        receipt["cycleHash"] = stable_hash(receipt, prefix="v34c_cycle")
        self.cycle_ledger_path.parent.mkdir(parents=True, exist_ok=True)
        with self.cycle_ledger_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(receipt, ensure_ascii=False, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        return receipt

    @staticmethod
    def _zero_effect_result(
        *,
        status: str,
        now: str,
        extra: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "schemaVersion": "okx_official_v1_v34c_cycle_receipt_v1",
            "status": status,
            "cycleAt": now,
            "executedTasks": [],
            "failedTasks": [],
            "candidateCount": 0,
            "formalRunCount": 0,
            "demoReleaseCount": 0,
            "orderCount": 0,
            **extra,
        }
