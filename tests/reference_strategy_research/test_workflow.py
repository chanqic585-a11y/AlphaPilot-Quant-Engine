from __future__ import annotations

import hashlib
import json
from pathlib import Path

from alphapilot.reference_strategy_research import workflow


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _prepare_repo(repo: Path) -> None:
    manifest_hash = "data_manifest_" + "a" * 64
    snapshot_id = "data_snapshot_" + "b" * 64
    shortlist_id = "factor_shortlist_" + "c" * 64
    registry_hash = "d" * 64
    instrument = "BTC-USDT-SWAP"

    datasets: list[dict[str, object]] = []
    for timeframe in ("1h", "4h"):
        source = repo / "data" / f"{instrument}-{timeframe}.parquet"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(f"verified-{timeframe}".encode("ascii"))
        datasets.append(
            {
                "datasetId": f"fixture-{instrument}-{timeframe}",
                "dataType": "ohlcv",
                "symbols": [instrument],
                "timeframe": timeframe,
                "sourcePath": str(source),
                "contentHash": hashlib.sha256(source.read_bytes()).hexdigest(),
                "startTime": "2020-01-01T00:00:00+00:00",
                "endTime": "2025-01-01T00:00:00+00:00",
            }
        )

    _write_json(
        repo / "reports" / "backtest_screening" / "data_readiness" / "dataset_catalog.json",
        {"dataManifestHash": manifest_hash, "datasets": datasets},
    )
    _write_json(
        repo / "research" / "data_snapshots" / f"{snapshot_id}.json",
        {
            "dataSnapshotId": snapshot_id,
            "dataManifestHash": manifest_hash,
            "instruments": [instrument],
            "pitStatus": "fixture_only",
        },
    )
    _write_json(
        repo / "research" / "factor_shortlists" / f"{shortlist_id}.json",
        {
            "factorShortlistId": shortlist_id,
            "dataSnapshotHash": snapshot_id,
            "factorRegistryHash": registry_hash,
        },
    )
    for relative in workflow._IMPLEMENTATION_SOURCES:
        source = repo / relative
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text(f"fixture source: {relative}\n", encoding="utf-8")


def test_prepare_only_is_resumable_and_never_downloads(
    tmp_path: Path,
    reference_package_zip: Path,
) -> None:
    repo = tmp_path / "repo"
    _prepare_repo(repo)
    code_commit = "e" * 40

    first = workflow.run_reference_workflow(
        repo_root=repo,
        package_path=reference_package_zip,
        code_commit=code_commit,
        execute_campaign=False,
    )
    second = workflow.run_reference_workflow(
        repo_root=repo,
        package_path=reference_package_zip,
        code_commit=code_commit,
        execute_campaign=False,
    )

    assert first == second
    assert first["status"] == "preregistered"
    output = Path(first["output"])
    audit = json.loads((output / "data_gap_audit.json").read_text(encoding="utf-8"))
    state = json.loads((output / "workflow_state.json").read_text(encoding="utf-8"))
    preregistration = json.loads(Path(first["preregistration"]).read_text(encoding="utf-8"))

    assert audit["ready"] is True
    assert audit["downloadRequired"] is False
    assert audit["networkCalls"] == 0
    assert state["completedStages"][-1] == "preregistered"
    assert preregistration["codeCommit"] == code_commit
    assert preregistration["holdout"]["accessCountBeforeFinalEvaluation"] == 0
    assert len(preregistration["candidates"]) == 4
