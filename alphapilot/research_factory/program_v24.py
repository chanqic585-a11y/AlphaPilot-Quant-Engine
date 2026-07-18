"""V24 verified Console receipt and terminal zero-Release program closure."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from alphapilot.data_foundation.checkpoint import write_json_atomic
from alphapilot.evolution.registry.hashing import stable_hash
from alphapilot.research_factory.artifact_paths import ProgramArtifactPaths
from alphapilot.research_factory.program_ledger import ProgramLedger
from alphapilot.research_factory.program_state import ProgramStateStore
from alphapilot.research_factory.program_v19 import _artifact_manifest


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected_json_object:{path}")
    return payload


def finalize_v24_zero_release_route(
    *,
    reports_root: Path,
    program_id: str,
    generated_at: str,
    console_audit_path: Path,
) -> dict[str, Any]:
    """Close only the verified 0/0/0/0 Console route; never infer an approval."""

    paths = ProgramArtifactPaths(Path(reports_root), program_id)
    state_store = ProgramStateStore(paths)
    state = state_store.load()
    if state.stage == "completed":
        checkpoint = state_store.load_checkpoint("v24")
        return {**checkpoint["payload"], "resumed": True}
    if state.stage != "release_ready":
        raise ValueError(f"v24_stage_not_allowed:{state.stage}")
    v23 = state_store.load_checkpoint("v23")["payload"]
    if (
        int(v23.get("releaseCount") or 0) != 0
        or v23.get("approvalRequired") is not False
        or v23.get("demoArm") is not False
        or int(v23.get("orderCount") or 0) != 0
        or v23.get("terminalRoute") != "completed_zero_qualified_candidates"
    ):
        raise ValueError("v24_zero_release_checkpoint_invalid")

    audit_path = Path(console_audit_path).resolve()
    audit = _read_json(audit_path)
    supplied_hash = audit.get("auditHash")
    canonical = {key: value for key, value in audit.items() if key != "auditHash"}
    expected_hash = stable_hash(canonical, prefix="automatic_v24_release_import_audit")
    if supplied_hash != expected_hash:
        raise ValueError("console_v24_audit_hash_mismatch")
    required_zero = {
        "releaseCount": 0,
        "importedReleaseCount": 0,
        "approvalCount": 0,
        "orderCount": 0,
    }
    if audit.get("status") != "completed_zero_qualified_candidates":
        raise ValueError("console_v24_terminal_route_mismatch")
    if any(int(audit.get(key) or 0) != value for key, value in required_zero.items()):
        raise ValueError("console_v24_zero_count_mismatch")
    if audit.get("demoArm") is not False:
        raise ValueError("console_v24_zero_route_must_not_arm")
    if audit.get("engineeringSmokeCountedAsStrategyEvidence") is not False:
        raise ValueError("engineering_smoke_evidence_isolation_failed")

    receipt = {
        "schemaVersion": "automatic_v24_console_completion_receipt_v1",
        "programId": program_id,
        "campaignId": state.active_campaign_id,
        "consoleAuditPath": audit_path.as_posix(),
        "consoleAuditSha256": hashlib.sha256(audit_path.read_bytes()).hexdigest(),
        "consoleAuditHash": supplied_hash,
        "terminalRoute": "completed_zero_qualified_candidates",
        "releaseCount": 0,
        "importedReleaseCount": 0,
        "approvalCount": 0,
        "demoArm": False,
        "orderCount": 0,
        "engineeringSmokeCountedAsStrategyEvidence": False,
        "generatedAt": generated_at,
    }
    receipt["receiptHash"] = stable_hash(receipt, prefix="automatic_v24_console_receipt")
    write_json_atomic(paths.program_root / "console_v24_completion_receipt.json", receipt)

    state = state.transition(
        stage="completed",
        updated_at=generated_at,
        stage_attempt=state.stage_attempt + 1,
        previous_checkpoint="v23",
        next_allowed_stage=None,
        terminal_route="completed_zero_qualified_candidates",
        human_gate_status="not_required",
    )
    state_store.save(state)
    checkpoint_payload = {
        "programId": program_id,
        "campaignId": state.active_campaign_id,
        "status": "completed",
        "terminalRoute": "completed_zero_qualified_candidates",
        "releaseCount": 0,
        "importedReleaseCount": 0,
        "approvalCount": 0,
        "demoArm": False,
        "orderCount": 0,
        "consoleAuditHash": supplied_hash,
        "receiptHash": receipt["receiptHash"],
    }
    state_store.write_checkpoint(stage="v24", created_at=generated_at, payload=checkpoint_payload)
    ProgramLedger(paths.ledger).append(
        event_type="v24_zero_release_program_completed",
        stage=state.stage,
        created_at=generated_at,
        payload=checkpoint_payload,
    )
    write_json_atomic(paths.artifact_manifest, _artifact_manifest(paths.program_root))
    return checkpoint_payload


__all__ = ["finalize_v24_zero_release_route"]
