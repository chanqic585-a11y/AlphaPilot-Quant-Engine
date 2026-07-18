"""V33 budget-inheriting dual-track successor governance."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterator

from alphapilot.data_foundation.checkpoint import write_json_atomic
from alphapilot.evolution.registry.hashing import stable_hash

from .program_ledger import ProgramLedger


DUAL_TRACK_LEDGER_FILES = {
    "master": "master_program_ledger.jsonl",
    "research": "research_track_ledger.jsonl",
    "demo_product": "demo_product_track_ledger.jsonl",
    "cross_track": "cross_track_receipt_ledger.jsonl",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_dual_track_program_id(
    *,
    predecessor_program_id: str,
    predecessor_budget_ledger_hash: str,
    implementation_contract_hash: str,
) -> str:
    identity = {
        "schemaVersion": "alphapilot_dual_track_v33_identity_v1",
        "predecessorProgramId": str(predecessor_program_id).strip(),
        "predecessorBudgetLedgerHash": str(
            predecessor_budget_ledger_hash
        ).strip(),
        "implementationContractHash": str(implementation_contract_hash).strip(),
    }
    if not all(identity.values()):
        raise ValueError("dual_track_identity_incomplete")
    digest = stable_hash(identity, prefix="alphapilot_dual_track_v33")
    return f"alphapilot_dual_track_v33_{digest[-16:]}"


class DualTrackLedgerSet:
    """Four isolated ledgers with fail-closed, single-writer file leases."""

    def __init__(self, root: Path, *, writer_id: str) -> None:
        self.root = Path(root)
        self.writer_id = str(writer_id).strip()
        if not self.writer_id:
            raise ValueError("ledger_writer_id_missing")

    def _ledger_path(self, track: str) -> Path:
        try:
            name = DUAL_TRACK_LEDGER_FILES[track]
        except KeyError as error:
            raise ValueError(f"unknown_dual_track_ledger:{track}") from error
        return self.root / name

    @contextmanager
    def writer_lease(self, track: str) -> Iterator[None]:
        ledger_path = self._ledger_path(track)
        lease_path = ledger_path.with_suffix(ledger_path.suffix + ".writer.lock")
        lease_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            descriptor = os.open(
                lease_path,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
            )
        except FileExistsError as error:
            raise RuntimeError(
                f"ledger_writer_lease_unavailable:{track}"
            ) from error
        try:
            lease = {
                "schemaVersion": "dual_track_writer_lease_v1",
                "track": track,
                "writerId": self.writer_id,
                "acquiredAt": datetime.now(UTC).isoformat(),
            }
            os.write(
                descriptor,
                json.dumps(lease, sort_keys=True).encode("utf-8"),
            )
            os.fsync(descriptor)
            yield
        finally:
            os.close(descriptor)
            lease_path.unlink(missing_ok=True)

    def append(
        self,
        track: str,
        *,
        event_type: str,
        stage: str,
        created_at: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        with self.writer_lease(track):
            return ProgramLedger(self._ledger_path(track)).append(
                event_type=event_type,
                stage=stage,
                created_at=created_at,
                payload=payload,
            )


def initialize_dual_track_successor(
    *,
    reports_root: Path,
    predecessor_program_root: Path,
    implementation_contract_hash: str,
    implementation_commit: str,
    generated_at: str,
    writer_id: str,
) -> dict[str, Any]:
    predecessor_root = Path(predecessor_program_root)
    budget_path = predecessor_root / "program_budget.json"
    ledger_path = predecessor_root / "program_ledger.jsonl"
    summary_path = predecessor_root / "program_summary.json"
    for required in (budget_path, ledger_path, summary_path):
        if not required.is_file():
            raise FileNotFoundError(f"predecessor_evidence_missing:{required.name}")

    predecessor_budget = json.loads(budget_path.read_text(encoding="utf-8"))
    predecessor_summary = json.loads(summary_path.read_text(encoding="utf-8"))
    predecessor_program_id = str(predecessor_summary.get("programId") or "").strip()
    if predecessor_summary.get("finalRoute") != "blocked_formal_data":
        raise ValueError("unexpected_predecessor_final_route")
    if int(predecessor_summary.get("formalRunCount") or 0) != 0:
        raise ValueError("predecessor_formal_run_count_nonzero")
    if int(predecessor_summary.get("resultReadCount") or 0) != 0:
        raise ValueError("predecessor_result_read_count_nonzero")

    inherited_budget = {
        "schemaVersion": "dual_track_inherited_budget_v1",
        "predecessorProgramId": predecessor_program_id,
        "campaignsUsed": int(predecessor_budget.get("campaignsUsed") or 0),
        "fullBacktestsUsed": int(
            predecessor_budget.get("fullBacktestsUsed") or 0
        ),
        "fullBacktestsRemaining": int(
            predecessor_budget.get("fullBacktestsRemaining") or 0
        ),
        "maximumAdditionalFullBacktests": int(
            predecessor_budget.get("maximumAdditionalFullBacktests") or 0
        ),
        "budgetReset": False,
    }
    if inherited_budget["campaignsUsed"] != 1:
        raise ValueError("predecessor_campaign_budget_mismatch")
    if inherited_budget["fullBacktestsUsed"] != 0:
        raise ValueError("predecessor_backtest_budget_mismatch")
    if inherited_budget["fullBacktestsRemaining"] != 96:
        raise ValueError("predecessor_remaining_budget_mismatch")

    predecessor_budget_ledger_hash = stable_hash(
        {
            "budgetSha256": _sha256(budget_path),
            "ledgerSha256": _sha256(ledger_path),
        },
        prefix="predecessor_budget_evidence",
    )
    program_id = build_dual_track_program_id(
        predecessor_program_id=predecessor_program_id,
        predecessor_budget_ledger_hash=predecessor_budget_ledger_hash,
        implementation_contract_hash=implementation_contract_hash,
    )
    root = Path(reports_root) / "dual_track" / program_id
    output_summary = root / "program_summary.json"
    if output_summary.is_file():
        return json.loads(output_summary.read_text(encoding="utf-8"))

    qualification_status = {
        "schemaVersion": "dual_track_qualification_status_v1",
        "closeoutIntegrityPassed": True,
        "programObjectivePassed": False,
        "strategyQualified": False,
        "demoQualified": False,
        "liveQualified": False,
    }
    spec = {
        "schemaVersion": "alphapilot_dual_track_program_spec_v1",
        "programId": program_id,
        "continuationOf": predecessor_program_id,
        "predecessorFinalRoute": predecessor_summary["finalRoute"],
        "predecessorBudgetLedgerHash": predecessor_budget_ledger_hash,
        "implementationContractHash": implementation_contract_hash,
        "implementationCommit": implementation_commit,
        "candidateGenerationEnabled": False,
        "formalResultRunsEnabled": False,
        "demoEnabled": False,
        "liveEnabled": False,
        "tradeApiEnabled": False,
        "withdrawEnabled": False,
    }
    spec["programSpecHash"] = stable_hash(spec, prefix="dual_track_program_spec")
    state = {
        "schemaVersion": "alphapilot_dual_track_state_v1",
        "programId": program_id,
        "topLevelState": "baseline_frozen",
        "researchTrackState": "research_blocked_data",
        "demoProductTrackState": "demo_platform_building",
        "generatedAt": generated_at,
    }
    summary = {
        "schemaVersion": "alphapilot_dual_track_summary_v1",
        "programId": program_id,
        "continuationOf": predecessor_program_id,
        "predecessorFinalRoute": predecessor_summary["finalRoute"],
        "predecessorBudgetLedgerHash": predecessor_budget_ledger_hash,
        "topLevelState": "baseline_frozen",
        "generatedAt": generated_at,
        "formalRunCount": 0,
        "resultReadCount": 0,
        "lockedOosReadCount": 0,
        "candidateCount": 0,
        "releaseCount": 0,
        "approvalCount": 0,
        "demoArm": False,
        "orderCount": 0,
        "budget": inherited_budget,
        "qualification": qualification_status,
        "historicalMutationCount": 0,
    }
    summary["summaryHash"] = stable_hash(summary, prefix="dual_track_summary")

    write_json_atomic(root / "program_spec.json", spec)
    write_json_atomic(root / "program_state.json", state)
    write_json_atomic(root / "inherited_budget.json", inherited_budget)
    write_json_atomic(root / "qualification_status.json", qualification_status)
    ledgers = DualTrackLedgerSet(root, writer_id=writer_id)
    common_payload = {
        "programId": program_id,
        "programSpecHash": spec["programSpecHash"],
        "predecessorProgramId": predecessor_program_id,
        "predecessorBudgetLedgerHash": predecessor_budget_ledger_hash,
    }
    ledgers.append(
        "master",
        event_type="successor_program_initialized",
        stage="v33_baseline",
        created_at=generated_at,
        payload={**common_payload, "topLevelState": "baseline_frozen"},
    )
    ledgers.append(
        "research",
        event_type="research_track_initialized",
        stage="v33_baseline",
        created_at=generated_at,
        payload={**common_payload, "trackState": "research_blocked_data"},
    )
    ledgers.append(
        "demo_product",
        event_type="demo_product_track_initialized",
        stage="v33_baseline",
        created_at=generated_at,
        payload={**common_payload, "trackState": "demo_platform_building"},
    )
    ledgers.append(
        "cross_track",
        event_type="baseline_receipt_recorded",
        stage="v33_baseline",
        created_at=generated_at,
        payload={
            **common_payload,
            "candidateCount": 0,
            "releaseCount": 0,
            "orderCount": 0,
        },
    )
    write_json_atomic(output_summary, summary)
    return summary


def record_v34a_data_pilot(
    *,
    program_root: Path,
    pilot_result: dict[str, Any],
    created_at: str,
    writer_id: str,
) -> dict[str, Any]:
    """Append a data-only pilot receipt without admitting a strategy or order."""

    root = Path(program_root)
    summary_path = root / "program_summary.json"
    state_path = root / "program_state.json"
    if not summary_path.is_file() or not state_path.is_file():
        raise FileNotFoundError("dual_track_program_baseline_missing")
    if pilot_result.get("status") != "completed":
        raise ValueError("v34a_data_pilot_not_completed")
    if pilot_result.get("scope") != "v34a_data_only":
        raise ValueError("v34a_data_pilot_scope_mismatch")
    zero_fields = {
        "candidateCount": 0,
        "formalRunCount": 0,
        "demoReleaseCount": 0,
        "orderCount": 0,
    }
    for field, expected in zero_fields.items():
        if int(pilot_result.get(field) or 0) != expected:
            raise ValueError(f"v34a_forbidden_side_effect:{field}")
    snapshot_id = str(pilot_result.get("snapshotId") or "").strip()
    if not snapshot_id:
        raise ValueError("v34a_data_snapshot_id_missing")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if summary.get("dataSnapshotId") == snapshot_id:
        return summary
    if summary.get("dataSnapshotId"):
        raise ValueError("v34a_data_snapshot_already_registered")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    result_hash = stable_hash(pilot_result, prefix="v34a_data_pilot_result")
    payload = {
        "programId": summary["programId"],
        "snapshotId": snapshot_id,
        "pilotResultHash": result_hash,
        "partitionCount": int(pilot_result.get("partitionCount") or 0),
        "reusedPartitionCount": int(
            pilot_result.get("reusedPartitionCount") or 0
        ),
        "downloadedRowCount": int(pilot_result.get("downloadedRowCount") or 0),
        **zero_fields,
    }
    ledgers = DualTrackLedgerSet(root, writer_id=writer_id)
    ledgers.append(
        "master",
        event_type="data_pilot_completed",
        stage="v34a_okx_data_pilot",
        created_at=created_at,
        payload=payload,
    )
    ledgers.append(
        "research",
        event_type="official_data_snapshot_registered",
        stage="v34a_okx_data_pilot",
        created_at=created_at,
        payload=payload,
    )
    ledgers.append(
        "cross_track",
        event_type="data_snapshot_receipt_recorded",
        stage="v34a_okx_data_pilot",
        created_at=created_at,
        payload=payload,
    )
    state.update(
        {
            "topLevelState": "data_pilot_completed",
            "researchTrackState": "data_pilot_completed",
            "generatedAt": created_at,
            "dataSnapshotId": snapshot_id,
        }
    )
    summary.update(
        {
            "topLevelState": "data_pilot_completed",
            "generatedAt": created_at,
            "dataSnapshotId": snapshot_id,
            "dataPilotResultHash": result_hash,
            "candidateCount": 0,
            "formalRunCount": 0,
            "resultReadCount": 0,
            "lockedOosReadCount": 0,
            "releaseCount": 0,
            "approvalCount": 0,
            "demoArm": False,
            "orderCount": 0,
        }
    )
    summary.pop("summaryHash", None)
    summary["summaryHash"] = stable_hash(summary, prefix="dual_track_summary")
    write_json_atomic(state_path, state)
    write_json_atomic(summary_path, summary)
    return summary


__all__ = [
    "DUAL_TRACK_LEDGER_FILES",
    "DualTrackLedgerSet",
    "build_dual_track_program_id",
    "initialize_dual_track_successor",
    "record_v34a_data_pilot",
]
