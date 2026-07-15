"""Read-only evidence loading with mandatory SHA-256 verification."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any, Mapping

from alphapilot.validation.hashing import stable_hash


def sha256_file(path: Path) -> str:
    """Return the lowercase SHA-256 digest for a file without modifying it."""

    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_verified_json(path: Path, *, expected_sha256: str) -> Any:
    """Load JSON only after its bytes match the preregistered digest."""

    path = Path(path)
    actual_sha256 = sha256_file(path)
    if actual_sha256.lower() != expected_sha256.lower():
        raise ValueError(
            f"sha256 mismatch for {path}: expected {expected_sha256}, got {actual_sha256}"
        )
    return json.loads(path.read_text(encoding="utf-8"))


def _json_object(value: str | None, *, label: str) -> dict[str, Any]:
    payload = json.loads(value or "{}")
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object")
    return payload


def _manifest(
    root: Path,
    filename: str,
    *,
    expected_hash: str | None,
) -> dict[str, Any]:
    path = root / filename
    payload = _json_object(path.read_text(encoding="utf-8"), label=filename)
    actual = payload.get("manifestHash")
    if expected_hash and actual != expected_hash:
        raise ValueError(
            f"manifest hash mismatch for {filename}: expected {expected_hash}, got {actual}"
        )
    return payload


def _row_object(row: sqlite3.Row | None, *, label: str) -> dict[str, Any]:
    if row is None:
        raise ValueError(f"missing registry row: {label}")
    return dict(row)


def load_candidate_evidence(
    registry_path: Path,
    candidate: Mapping[str, Any],
) -> dict[str, Any]:
    """Load and cross-check one candidate's existing formal evidence read-only.

    The archived reports are diagnostic inputs. Because candidate selection saw
    their aggregate results and the universe is not point-in-time, this loader
    never relabels their locked split as independent acceptance evidence.
    """

    strategy_version_id = str(candidate["strategyVersionId"])
    registry_path = Path(registry_path).resolve()
    connection = sqlite3.connect(
        f"file:{registry_path.as_posix()}?mode=ro",
        uri=True,
    )
    connection.row_factory = sqlite3.Row
    try:
        workflow = _row_object(
            connection.execute(
                """
                SELECT *
                FROM WorkflowRuns
                WHERE strategyVersionId = ? AND resultJson IS NOT NULL
                ORDER BY completedAt DESC, updatedAt DESC
                LIMIT 1
                """,
                (strategy_version_id,),
            ).fetchone(),
            label=f"WorkflowRuns:{strategy_version_id}",
        )
        result = _json_object(workflow.get("resultJson"), label="WorkflowRuns.resultJson")
        workflow_evidence = result.get("evidence")
        if not isinstance(workflow_evidence, dict):
            raise ValueError(f"workflow evidence missing for {strategy_version_id}")

        report_path = Path(str(workflow_evidence["reportPath"]))
        report_sha256 = str(workflow_evidence["reportSha256"])
        report = load_verified_json(report_path, expected_sha256=report_sha256)
        if not isinstance(report, dict):
            raise ValueError("formal report must be a JSON object")
        report_evidence = report.get("evidence")
        trades = report.get("trades")
        if not isinstance(report_evidence, dict) or not isinstance(trades, list):
            raise ValueError("formal report evidence or trades missing")
        if report_evidence.get("strategyVersionId") != strategy_version_id:
            raise ValueError("formal report strategy version mismatch")

        binding = _row_object(
            connection.execute(
                "SELECT * FROM EvaluationBindings WHERE evaluationBindingId = ?",
                (workflow_evidence.get("evaluationBindingId"),),
            ).fetchone(),
            label=f"EvaluationBindings:{workflow_evidence.get('evaluationBindingId')}",
        )
        snapshot = _row_object(
            connection.execute(
                "SELECT * FROM DataSnapshots WHERE dataSnapshotId = ?",
                (binding["dataSnapshotId"],),
            ).fetchone(),
            label=f"DataSnapshots:{binding['dataSnapshotId']}",
        )
        contract = _row_object(
            connection.execute(
                "SELECT * FROM StrategyDataContracts WHERE strategyDataContractId = ?",
                (binding["strategyDataContractId"],),
            ).fetchone(),
            label=f"StrategyDataContracts:{binding['strategyDataContractId']}",
        )
    finally:
        connection.close()

    expected_snapshot_id = candidate.get("dataSnapshotId")
    expected_snapshot_hash = candidate.get("dataSnapshotHash")
    if expected_snapshot_id and snapshot["dataSnapshotId"] != expected_snapshot_id:
        raise ValueError("data snapshot id mismatch")
    if expected_snapshot_hash and snapshot["contentHash"] != expected_snapshot_hash:
        raise ValueError("data snapshot hash mismatch")
    if report_evidence.get("dataSnapshotId") != snapshot["dataSnapshotId"]:
        raise ValueError("formal report data snapshot mismatch")

    manifest_root = report_path.parent
    expected_manifest_hashes = {
        "walk-forward.json": candidate.get("walkForwardManifestHash"),
        "holdout.json": candidate.get("holdoutManifestHash"),
        "locked-oos.json": candidate.get("lockedOosManifestHash"),
        "cost.json": workflow_evidence.get("costManifestHash"),
        "regime.json": workflow_evidence.get("regimeManifestHash"),
    }
    manifests = {
        filename: _manifest(
            manifest_root,
            filename,
            expected_hash=str(expected_hash) if expected_hash else None,
        )
        for filename, expected_hash in expected_manifest_hashes.items()
    }
    for key, binding_key in (
        ("walk-forward.json", "walkForwardManifestHash"),
        ("holdout.json", "holdoutManifestHash"),
        ("locked-oos.json", "lockedOosManifestHash"),
    ):
        if manifests[key].get("manifestHash") != binding.get(binding_key):
            raise ValueError(f"evaluation binding {binding_key} mismatch")

    point_in_time_available = candidate.get("historicalPointInTimeUniverse") is True
    selection_method = "archived_candidates_selected_after_full_sample_metrics_review"
    leakage_flags = [
        "locked_and_holdout_results_previously_observed_in_archived_metrics",
        "selection_history_not_proven_exclusive",
    ]
    if not point_in_time_available:
        leakage_flags.append("historical_point_in_time_universe_unavailable")
    clean_locked_available = False
    validation_identity = {
        "strategyVersionId": strategy_version_id,
        "signalDefinitionHash": candidate.get("signalDefinitionHash"),
        "timeframe": candidate.get("timeframe"),
        "dataSnapshotHash": snapshot["contentHash"],
        "walkForwardManifestHash": manifests["walk-forward.json"].get("manifestHash"),
        "holdoutManifestHash": manifests["holdout.json"].get("manifestHash"),
        "lockedOosManifestHash": manifests["locked-oos.json"].get("manifestHash"),
        "costManifestHash": manifests["cost.json"].get("manifestHash"),
        "reportSha256": report_sha256,
    }
    return {
        "strategyVersionId": strategy_version_id,
        "workflowRunId": workflow["workflowRunId"],
        "workflowStatus": workflow["status"],
        "evaluationBindingId": binding["evaluationBindingId"],
        "strategyDataContractId": contract["strategyDataContractId"],
        "dataSnapshotId": snapshot["dataSnapshotId"],
        "dataSnapshotHash": snapshot["contentHash"],
        "dataStartTime": snapshot["startTime"],
        "dataEndTime": snapshot["endTime"],
        "pointInTimeCutoff": snapshot["pointInTimeCutoff"],
        "reportPath": str(report_path),
        "reportSha256": report_sha256,
        "reportResultHash": report.get("resultHash"),
        "validationManifestHash": stable_hash(validation_identity),
        "manifestHashes": {
            filename: payload.get("manifestHash")
            for filename, payload in manifests.items()
        },
        "signalReproducible": candidate.get("signalUnreproducibleReason") is None,
        "signalUnreproducibleReason": candidate.get("signalUnreproducibleReason"),
        "historicalPointInTimeUniverse": point_in_time_available,
        "survivorshipAuditStatus": candidate.get("survivorshipAuditStatus"),
        "lockedOrHoldoutUsedForSelection": True,
        "selectionMethod": selection_method,
        "usedForSelectionRanges": ["full formal report aggregate range"],
        "usedForSelectionSymbols": ["all report symbols"],
        "potentialLeakageFlags": leakage_flags,
        "cleanLockedSampleAvailable": clean_locked_available,
        "lockedSampleStatus": "无污染锁定样本不可用",
        "diagnosticReplayOnly": True,
        "pointInTimeUniverseAudit": {
            "available": point_in_time_available,
            "listingDelistingEvidenceAvailable": False,
            "survivorshipBiasControlled": False,
            "status": candidate.get("survivorshipAuditStatus"),
        },
        "sourceFileCount": len(report_evidence.get("sourceFileHashes") or []),
        "contractContentHash": contract["contentHash"],
        "contract": _json_object(contract.get("contractJson"), label="contractJson"),
        "snapshotManifest": _json_object(snapshot.get("manifestJson"), label="manifestJson"),
        "manifests": manifests,
        "report": report,
        "trades": [dict(row) for row in trades],
    }
