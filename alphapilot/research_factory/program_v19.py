"""V19 data-capability stage for the automatic strategy-to-Demo workflow."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Iterable

import pyarrow as pa
import pyarrow.parquet as pq

from alphapilot.data_foundation.checkpoint import write_json_atomic
from alphapilot.evolution.registry.hashing import sha256_file, stable_hash
from alphapilot.research_factory.artifact_paths import ProgramArtifactPaths
from alphapilot.research_factory.data_capability import (
    build_data_capability_matrix,
    candidate_data_gate,
    summarize_data_capabilities,
)
from alphapilot.research_factory.data_profiles import build_data_profiles
from alphapilot.research_factory.field_semantics import build_field_semantics_registry
from alphapilot.research_factory.program_ledger import ProgramLedger
from alphapilot.research_factory.program_state import ProgramStateStore
from alphapilot.research_factory.program_types import ProgramState


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = list(rows[0]) if rows else []
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        if columns:
            writer.writeheader()
            for row in rows:
                writer.writerow(
                    {
                        key: json.dumps(value, ensure_ascii=False, sort_keys=True)
                        if isinstance(value, (dict, list))
                        else value
                        for key, value in row.items()
                    }
                )


def _artifact_manifest(root: Path) -> dict[str, Any]:
    artifacts = []
    for path in sorted(item for item in root.rglob("*") if item.is_file() and item.name != "artifact_manifest.json"):
        artifacts.append(
            {
                "relativePath": path.relative_to(root).as_posix(),
                "sha256": sha256_file(path),
                "sizeBytes": path.stat().st_size,
            }
        )
    payload = {
        "schemaVersion": "automatic_strategy_demo_artifact_manifest_v1",
        "artifactCount": len(artifacts),
        "artifacts": artifacts,
    }
    payload["manifestHash"] = stable_hash(payload, prefix="artifact_manifest")
    return payload


def _baseline_references(paths: Iterable[Path]) -> list[dict[str, Any]]:
    references = []
    for path in sorted((Path(item) for item in paths), key=lambda item: item.as_posix()):
        if not path.is_file():
            raise FileNotFoundError(path)
        references.append(
            {
                "path": path.as_posix(),
                "sha256": sha256_file(path),
                "sizeBytes": path.stat().st_size,
            }
        )
    return references


def run_v19_data_capability(
    *,
    reports_root: Path,
    program_id: str,
    baseline_commit: str,
    program_spec_hash: str,
    generated_at: str,
    catalog_path: Path,
    source_audit_path: Path,
    snapshot_path: Path,
    baseline_artifacts: Iterable[Path],
) -> dict[str, Any]:
    paths = ProgramArtifactPaths(Path(reports_root), program_id)
    root = paths.program_root
    root.mkdir(parents=True, exist_ok=True)
    state_store = ProgramStateStore(paths)
    state = state_store.initialize(
        ProgramState.create(
            program_id=program_id,
            baseline_commit=baseline_commit,
            program_spec_hash=program_spec_hash,
            created_at=generated_at,
        )
    )
    ledger = ProgramLedger(paths.ledger)
    ledger.append(
        event_type="program_created",
        stage="program_created",
        created_at=generated_at,
        payload={
            "programId": program_id,
            "baselineCommit": baseline_commit,
            "programSpecHash": program_spec_hash,
        },
    )

    catalog = _load_json(Path(catalog_path))
    source_audit = _load_json(Path(source_audit_path))
    snapshot = _load_json(Path(snapshot_path))
    references = _baseline_references(baseline_artifacts)
    baseline_identity = {
        "schemaVersion": "automatic_strategy_demo_baseline_identity_v1",
        "baselineTag": "v13.27.1.18.3",
        "baselineCommit": baseline_commit,
        "programSpecHash": program_spec_hash,
        "dataManifestHash": catalog.get("dataManifestHash"),
        "dataSnapshotId": snapshot.get("snapshotId"),
        "lockedOosAccessCount": 0,
        "releaseCount": 0,
        "arm": False,
        "orderCount": 0,
        "sourceArtifacts": references,
    }
    baseline_identity["baselineIdentityHash"] = stable_hash(
        baseline_identity, prefix="baseline_identity"
    )
    write_json_atomic(root / "baseline_identity.json", baseline_identity)
    write_json_atomic(
        root / "v18_3_reusable_core_manifest.json",
        {
            "schemaVersion": "v18_3_reusable_core_manifest_v1",
            "candidateNeutralCore": [
                "alphapilot.formal_validation.candidate_adapter",
                "alphapilot.formal_validation.generic_formal_runner",
                "alphapilot.formal_validation.policy_objects",
                "alphapilot.evolution.promotion.strategy_validation_release",
            ],
            "baselineArtifacts": references,
            "reuseRule": "do_not_modify_v18_3_artifacts_or_s01_conclusion",
        },
    )
    write_json_atomic(
        root / "v18_3_archived_candidate_reference.json",
        {
            "schemaVersion": "v18_3_archived_candidate_reference_v1",
            "candidateId": "s01_bear_idiosyncratic_selloff_recovery_4h",
            "route": "archive_s01_current_version",
            "formalRunCount": 1,
            "resultReadCount": 1,
            "lockedOosAccessCount": 0,
            "releaseCount": 0,
            "referenceOnly": True,
        },
    )
    write_json_atomic(
        root / "structural_certification_vs_formal_event_delta_audit.json",
        {
            "schemaVersion": "v18_3_structural_formal_event_delta_audit_v1",
            "structuralCertificationRawEventCount": 924,
            "formalRawEventCount": 884,
            "delta": 40,
            "classification": "different_frozen_input_windows_and_preclaim_structural_scope",
            "resultImpact": "none",
            "s01RerunPerformed": False,
            "s01ConclusionChanged": False,
        },
    )

    matrix = build_data_capability_matrix(catalog, source_audit)
    summary = summarize_data_capabilities(matrix)
    semantics = build_field_semantics_registry()
    profiles = build_data_profiles(matrix, catalog)
    core_gate = candidate_data_gate(
        matrix,
        required_fields=["open", "high", "low", "close"],
        optional_fields=["reported_volume"],
        timeframes=["1h", "4h"],
        minimum_history_rows=10_000,
        data_profile_id="ohlcv_core_directional_v1",
    )
    derivatives_gate = candidate_data_gate(
        matrix,
        required_fields=["funding_rate", "open_interest", "basis", "liquidation", "orderbook"],
        optional_fields=[],
        timeframes=["event"],
        minimum_history_rows=1_000,
        data_profile_id="future_derivatives_v1",
    )
    _write_csv(root / "data_capability_matrix.csv", matrix)
    pq.write_table(pa.Table.from_pylist(matrix), root / "data_capability_matrix.parquet")
    write_json_atomic(root / "data_capability_summary.json", summary)
    write_json_atomic(root / "field_semantics_registry.json", semantics)
    write_json_atomic(root / "data_profiles.json", {"profiles": profiles})
    write_json_atomic(
        root / "data_gap_queue.json",
        {
            "schemaVersion": "data_gap_queue_v1",
            "gaps": [
                {
                    "field": field,
                    "status": "unavailable",
                    "action": "future_forward_collection_or_verified_public_source",
                    "blocksCoreDirectionalProfile": False,
                }
                for field in summary["unavailableFields"]
            ],
        },
    )
    gate_rows = [
        {**core_gate, "requiredFields": core_gate["requiredFields"], "optionalFields": core_gate["optionalFields"]},
        {
            **derivatives_gate,
            "requiredFields": derivatives_gate["requiredFields"],
            "optionalFields": derivatives_gate["optionalFields"],
        },
    ]
    _write_csv(root / "candidate_data_gate_matrix.csv", gate_rows)

    terminal = not bool(summary["directionalEventReady"])
    state = state.transition(
        stage="blocked" if terminal else "data_capability_ready",
        updated_at=generated_at,
        previous_checkpoint="baseline_frozen",
        next_allowed_stage=None if terminal else "hypotheses_frozen",
        terminal_route="blocked_data_capability" if terminal else None,
    )
    state_store.save(state)
    state_store.write_checkpoint(
        stage="v19",
        created_at=generated_at,
        payload={
            "status": "blocked" if terminal else "completed",
            "directionalEventReady": summary["directionalEventReady"],
            "dataManifestHash": catalog.get("dataManifestHash"),
            "profileIds": [profile["profileId"] for profile in profiles],
        },
    )
    ledger.append(
        event_type="v19_data_capability_completed" if not terminal else "v19_data_capability_blocked",
        stage=state.stage,
        created_at=generated_at,
        payload={
            "directionalEventReady": summary["directionalEventReady"],
            "nextAllowedStage": state.next_allowed_stage,
        },
    )
    write_json_atomic(paths.artifact_manifest, _artifact_manifest(root))
    return {
        "programId": program_id,
        "status": "blocked" if terminal else "completed",
        "directionalEventReady": bool(summary["directionalEventReady"]),
        "nextAllowedStage": state.next_allowed_stage,
        "artifactRoot": root.as_posix(),
    }
