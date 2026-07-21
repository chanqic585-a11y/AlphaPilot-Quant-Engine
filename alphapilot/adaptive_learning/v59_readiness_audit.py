"""Audit whether existing registry records qualify as V59 Live-readiness evidence."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Mapping, Sequence

from alphapilot.evolution.registry.hashing import stable_hash


_FORMAL_FACTOR_EVIDENCE_CLASSES = {
    "formal",
    "formal_market_data",
    "formal_research",
    "production_validated",
}
_LIVE_ELIGIBLE_MODEL_STATUSES = {
    "validated",
    "shadow_approved",
    "challenger",
    "champion",
    "live_candidate",
}
_LIVE_ELIGIBLE_LIFECYCLES = {
    "live_candidate",
    "shadow_approved",
    "challenger",
    "champion",
}


def _mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, str) and value.strip():
        parsed = json.loads(value)
        if isinstance(parsed, Mapping):
            return dict(parsed)
    return {}


def _payload(record: Mapping[str, Any]) -> dict[str, Any]:
    return _mapping(record.get("payload") or record.get("payloadJson"))


def _valid_sha256(value: Any) -> bool:
    text = str(value or "")
    return len(text) == 64 and all(char in "0123456789abcdef" for char in text.lower())


def _audit_factor_run(record: Mapping[str, Any]) -> dict[str, Any]:
    payload = _payload(record)
    blockers: list[str] = []
    if record.get("status") != "completed":
        blockers.append("factor_run_not_completed")
    if payload.get("pointInTimeValidated") is not True:
        blockers.append("factor_run_not_point_in_time_validated")
    if payload.get("formalPromotionEligible") is not True:
        blockers.append("factor_run_not_formal_promotion_eligible")
    evidence_class = str(payload.get("evidenceClass") or "")
    if evidence_class not in _FORMAL_FACTOR_EVIDENCE_CLASSES:
        blockers.append(evidence_class or "factor_run_evidence_class_missing")
    if not _valid_sha256(record.get("resultSha256")):
        blockers.append("factor_run_result_hash_missing")
    return {
        "factorRunId": record.get("factorRunId"),
        "evidenceClass": evidence_class or None,
        "eligible": not blockers,
        "blockers": blockers,
    }


def _audit_model(record: Mapping[str, Any]) -> dict[str, Any]:
    payload = _payload(record)
    artifact = _mapping(payload.get("artifact"))
    training = _mapping(artifact.get("trainingEvidence"))
    blockers: list[str] = []
    if record.get("status") not in _LIVE_ELIGIBLE_MODEL_STATUSES:
        blockers.append("model_lifecycle_not_live_eligible")
    if str(payload.get("lifecycleBoundary") or "") not in _LIVE_ELIGIBLE_LIFECYCLES:
        blockers.append("model_boundary_not_live_eligible")
    if artifact.get("researchOnly") is not False:
        blockers.append("model_research_only")
    if training.get("pointInTimeValidated") is not True:
        blockers.append("training_not_point_in_time_validated")
    if training.get("purgedWalkForward") is not True:
        blockers.append("purged_walk_forward_missing")
    if int(training.get("foldCount") or 0) <= 0:
        blockers.append("walk_forward_fold_count_zero")
    if int(training.get("sampleCount") or 0) <= 0:
        blockers.append("training_sample_count_zero")
    if not str(artifact.get("modelHash") or ""):
        blockers.append("model_hash_missing")
    if not _valid_sha256(record.get("artifactSha256")):
        blockers.append("model_binary_hash_missing")
    return {
        "modelId": record.get("modelId"),
        "status": record.get("status"),
        "eligible": not blockers,
        "blockers": blockers,
    }


def _audit_data_snapshot(record: Mapping[str, Any]) -> dict[str, Any]:
    manifest = _mapping(record.get("manifest") or record.get("manifestJson"))
    metadata = _mapping(manifest.get("metadata"))
    blockers: list[str] = []
    if metadata.get("formalPromotionEligible") is not True:
        blockers.append("snapshot_not_formal_promotion_eligible")
    if metadata.get("provenanceComplete") is not True:
        blockers.append("snapshot_provenance_incomplete")
    if not str(record.get("pointInTimeCutoff") or manifest.get("pointInTimeCutoff") or ""):
        blockers.append("snapshot_point_in_time_cutoff_missing")
    if not list(manifest.get("universeMembers") or []):
        blockers.append("snapshot_universe_missing")
    if not _valid_sha256(record.get("contentHash")):
        blockers.append("snapshot_content_hash_missing")
    return {
        "dataSnapshotId": record.get("dataSnapshotId"),
        "eligible": not blockers,
        "blockers": blockers,
    }


def audit_registry_evidence(
    *,
    factor_runs: Sequence[Mapping[str, Any]],
    models: Sequence[Mapping[str, Any]],
    data_snapshots: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Return a fail-closed qualification audit without mutating registry state."""

    audited_factor_runs = [_audit_factor_run(record) for record in factor_runs]
    audited_models = [_audit_model(record) for record in models]
    audited_snapshots = [_audit_data_snapshot(record) for record in data_snapshots]
    formal_factor_count = sum(item["eligible"] for item in audited_factor_runs)
    live_model_count = sum(item["eligible"] for item in audited_models)
    formal_snapshot_count = sum(item["eligible"] for item in audited_snapshots)
    blockers: list[str] = []
    if formal_factor_count == 0:
        blockers.append("no_formal_factor_runs")
    if live_model_count == 0:
        blockers.append("no_live_eligible_models")
    if formal_snapshot_count == 0:
        blockers.append("no_formal_data_snapshots")
    core = {
        "schemaVersion": "v59_registry_evidence_audit_v1",
        "status": "registry_evidence_ready" if not blockers else "blocked_registry_evidence",
        "factorRunCount": len(audited_factor_runs),
        "formalFactorRunCount": formal_factor_count,
        "modelCount": len(audited_models),
        "liveEligibleModelCount": live_model_count,
        "dataSnapshotCount": len(audited_snapshots),
        "formalDataSnapshotCount": formal_snapshot_count,
        "factorRuns": audited_factor_runs,
        "models": audited_models,
        "dataSnapshots": audited_snapshots,
        "blockers": blockers,
        "mutatesRegistry": False,
        "grantsLiveAuthority": False,
    }
    return {**core, "auditHash": stable_hash(core, prefix="v59_registry_evidence_audit")}


def _read_table(connection: sqlite3.Connection, table: str) -> list[dict[str, Any]]:
    exists = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table,),
    ).fetchone()
    if exists is None:
        return []
    return [dict(row) for row in connection.execute(f'SELECT * FROM "{table}"')]


def audit_registry_database(registry_path: Path | str) -> dict[str, Any]:
    """Read a registry in read-only mode and audit its immutable evidence records."""

    path = Path(registry_path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        return audit_registry_evidence(
            factor_runs=_read_table(connection, "FactorRuns"),
            models=_read_table(connection, "Models"),
            data_snapshots=_read_table(connection, "DataSnapshots"),
        )
    finally:
        connection.close()
