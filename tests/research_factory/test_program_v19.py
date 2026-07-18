from __future__ import annotations

import json
from pathlib import Path

import pyarrow.parquet as pq

from alphapilot.research_factory.artifact_paths import ProgramArtifactPaths
from alphapilot.research_factory.program_v19 import run_v19_data_capability


def _write_inputs(root: Path) -> tuple[Path, Path, Path]:
    datasets = []
    for instrument in ("BTC-USDT-SWAP", "ETH-USDT-SWAP"):
        for timeframe, rows in (("1h", 50_000), ("4h", 12_500)):
            datasets.append(
                {
                    "datasetId": f"local_{instrument}_{timeframe}",
                    "dataType": "ohlcv",
                    "exchange": "unverified_local_exchange",
                    "marketType": "swap",
                    "symbols": [instrument],
                    "timeframe": timeframe,
                    "startTime": "2020-01-01T00:00:00+00:00",
                    "endTime": "2026-05-01T00:00:00+00:00",
                    "rowCount": rows,
                    "provider": "user_confirmed_local_history",
                    "contentHash": f"hash-{instrument}-{timeframe}",
                    "isPointInTime": False,
                    "isProxy": True,
                }
            )
    catalog = root / "catalog.json"
    audit = root / "audit.json"
    snapshot = root / "snapshot.json"
    catalog.write_text(
        json.dumps({"dataManifestHash": "manifest-fixture", "verified": True, "datasets": datasets}),
        encoding="utf-8",
    )
    audit.write_text(json.dumps({"sources": []}), encoding="utf-8")
    snapshot.write_text(
        json.dumps({"snapshotId": "snapshot-fixture", "pitStatus": "diagnostic_proxy"}),
        encoding="utf-8",
    )
    return catalog, audit, snapshot


def test_v19_writes_complete_resumable_data_capability_evidence(tmp_path: Path) -> None:
    catalog, audit, snapshot = _write_inputs(tmp_path)
    baseline = tmp_path / "baseline.json"
    archived = tmp_path / "archived.json"
    baseline.write_text('{"route":"archive_s01_current_version"}', encoding="utf-8")
    archived.write_text('{"candidateId":"s01"}', encoding="utf-8")

    result = run_v19_data_capability(
        reports_root=tmp_path / "reports",
        program_id="automatic_strategy_demo_fixture",
        baseline_commit="f9f36f4",
        program_spec_hash="spec-fixture",
        generated_at="2026-07-18T00:00:00Z",
        catalog_path=catalog,
        source_audit_path=audit,
        snapshot_path=snapshot,
        baseline_artifacts=[baseline, archived],
    )
    paths = ProgramArtifactPaths(tmp_path / "reports", "automatic_strategy_demo_fixture")

    assert result["status"] == "completed"
    assert result["directionalEventReady"] is True
    expected = {
        "baseline_identity.json",
        "v18_3_reusable_core_manifest.json",
        "v18_3_archived_candidate_reference.json",
        "structural_certification_vs_formal_event_delta_audit.json",
        "data_capability_matrix.parquet",
        "data_capability_matrix.csv",
        "data_capability_summary.json",
        "field_semantics_registry.json",
        "data_profiles.json",
        "data_gap_queue.json",
        "candidate_data_gate_matrix.csv",
        "program_state.json",
        "program_ledger.jsonl",
        "artifact_manifest.json",
    }
    assert expected <= {path.name for path in paths.program_root.iterdir()}
    assert pq.read_table(paths.program_root / "data_capability_matrix.parquet").num_rows > 0
    state = json.loads(paths.state.read_text(encoding="utf-8"))
    assert state["stage"] == "data_capability_ready"
    assert state["nextAllowedStage"] == "hypotheses_frozen"


def test_v19_is_idempotent_for_same_program_identity(tmp_path: Path) -> None:
    catalog, audit, snapshot = _write_inputs(tmp_path)
    baseline = tmp_path / "baseline.json"
    baseline.write_text("{}", encoding="utf-8")
    kwargs = {
        "reports_root": tmp_path / "reports",
        "program_id": "automatic_strategy_demo_fixture",
        "baseline_commit": "f9f36f4",
        "program_spec_hash": "spec-fixture",
        "generated_at": "2026-07-18T00:00:00Z",
        "catalog_path": catalog,
        "source_audit_path": audit,
        "snapshot_path": snapshot,
        "baseline_artifacts": [baseline],
    }

    first = run_v19_data_capability(**kwargs)
    second = run_v19_data_capability(**kwargs)
    paths = ProgramArtifactPaths(tmp_path / "reports", "automatic_strategy_demo_fixture")

    assert second == first
    assert len(paths.ledger.read_text(encoding="utf-8").splitlines()) == 2
