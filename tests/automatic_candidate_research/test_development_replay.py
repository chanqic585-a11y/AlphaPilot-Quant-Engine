from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

from alphapilot.automatic_candidate_research.contracts import V36ContractError
from alphapilot.automatic_candidate_research.development_replay import (
    build_development_evidence,
    load_development_frames,
)
from alphapilot.automatic_candidate_research.executor import (
    AutomaticCandidateResearchExecutor,
)
from alphapilot.automatic_candidate_research.preregistration import (
    build_preregistration,
)
from alphapilot.standard_replication import ReplicationSourceRegistry


REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = REPO_ROOT / "research/source_registry/strategy_research_source_registry.json"


def test_snapshot_loader_verifies_hash_and_development_window(tmp_path: Path) -> None:
    manifest_path = _snapshot_fixture(tmp_path)

    frames, audit = load_development_frames(
        manifest_path=manifest_path,
        expected_snapshot_id="snapshot-fixture",
        development_start="2024-02-01T00:00:00Z",
        development_end="2024-03-01T00:00:00Z",
        requirements={
            ("BTC-USDT-SWAP", "1h"),
            ("ETH-USDT-SWAP", "1h"),
        },
    )

    assert set(frames) == {
        ("BTC-USDT-SWAP", "1h"),
        ("ETH-USDT-SWAP", "1h"),
    }
    assert all(frame["date"].min() >= pd.Timestamp("2024-02-01", tz="UTC") for frame in frames.values())
    assert all(frame["date"].max() < pd.Timestamp("2024-03-01", tz="UTC") for frame in frames.values())
    assert audit["verifiedPartitionCount"] == 2
    assert audit["lockedOosReadCount"] == 0

    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["partitions"][0]["outputSha256"] = "0" * 64
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(V36ContractError, match="snapshot_partition_hash_mismatch"):
        load_development_frames(
            manifest_path=manifest_path,
            expected_snapshot_id="snapshot-fixture",
            development_start="2024-02-01T00:00:00Z",
            development_end="2024-03-01T00:00:00Z",
            requirements={("BTC-USDT-SWAP", "1h")},
        )


def test_snapshot_loader_accepts_immutable_snapshot_status(tmp_path: Path) -> None:
    manifest_path = _snapshot_fixture(tmp_path)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["status"] = "immutable_data_snapshot"
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")

    frames, audit = load_development_frames(
        manifest_path=manifest_path,
        expected_snapshot_id="snapshot-fixture",
        development_start="2024-02-01T00:00:00Z",
        development_end="2024-03-01T00:00:00Z",
        requirements={("BTC-USDT-SWAP", "1h")},
    )

    assert len(frames[("BTC-USDT-SWAP", "1h")]) > 0
    assert audit["snapshotId"] == "snapshot-fixture"


def test_real_replay_builds_every_eligible_trial_without_oos_reads(
    tmp_path: Path,
) -> None:
    registry = ReplicationSourceRegistry.load(REGISTRY_PATH)
    manifest_path = _snapshot_fixture(tmp_path, include_all_timeframes=True)
    panel = {
        "developmentStart": "2024-02-01T00:00:00Z",
        "developmentEnd": "2024-07-01T00:00:00Z",
        "dataSnapshotId": "snapshot-fixture",
        "costPolicyHash": "cost-policy-fixture",
        "capitalPolicyHash": "capital-policy-fixture",
        "benchmarkPolicyHash": "benchmark-policy-fixture",
        "randomSeed": 36,
    }
    preregistration = build_preregistration(
        registry=registry,
        campaign_id="v36-real-replay-fixture",
        created_at="2026-07-19T00:00:00Z",
        comparison_panel=panel,
    )

    evidence, audit = build_development_evidence(
        registry=registry,
        preregistration=preregistration,
        comparison_panel=panel,
        replay_config={
            "snapshotManifestPath": str(manifest_path),
            "roundTripCostRate": 0.001,
        },
    )

    assert len(evidence) == preregistration["trialCount"] == 18
    assert {row["strategyType"] for row in evidence} == {"directional", "pair"}
    assert all(row["split"] == "development" for row in evidence)
    assert all(row["lockedOosReadCount"] == 0 for row in evidence)
    assert all(row["metrics"]["maxDrawdownR"] >= 0 for row in evidence)
    assert audit["evidenceCount"] == 18
    assert audit["lockedOosReadCount"] == 0
    assert audit["formalRunCount"] == 0
    assert audit["releaseCount"] == 0
    assert audit["orderCount"] == 0


def test_executor_runs_requested_replay_and_persists_audit(tmp_path: Path) -> None:
    registry = ReplicationSourceRegistry.load(REGISTRY_PATH)
    manifest_path = _snapshot_fixture(tmp_path, include_all_timeframes=True)
    candidate_ids = sorted(
        variant.candidate_id
        for family in registry.items
        for variant in family.variants
    )
    campaign_input = {
        "campaignId": "v36-replay-integration",
        "createdAt": "2026-07-19T00:00:00Z",
        "familyIds": list(registry.family_ids),
        "candidateIds": candidate_ids,
        "comparisonPanel": {
            "developmentStart": "2024-02-01T00:00:00Z",
            "developmentEnd": "2024-07-01T00:00:00Z",
            "dataSnapshotId": "snapshot-fixture",
            "costPolicyHash": "cost-policy-fixture",
            "capitalPolicyHash": "capital-policy-fixture",
            "benchmarkPolicyHash": "benchmark-policy-fixture",
            "randomSeed": 36,
        },
        "developmentReplay": {
            "snapshotManifestPath": str(manifest_path),
            "roundTripCostRate": 0.001,
        },
        "developmentEvidence": [],
        "formalOutcomes": [],
    }
    executor = AutomaticCandidateResearchExecutor(
        registry=registry,
        output_root=tmp_path / "reports",
        campaign_inputs={"v36-replay-integration": campaign_input},
    )

    result = executor.execute(
        {
            "campaignId": "v36-replay-integration",
            "familyIds": list(registry.family_ids),
            "candidateIds": candidate_ids,
        }
    )

    assert result["developmentReplayStatus"] == "completed"
    assert result["developmentEvidenceCount"] == 18
    assert result["developmentProjectionCount"] == 18
    assert result["formalRunCount"] == 0
    assert result["releaseCount"] == 0
    assert result["orderCount"] == 0
    audit = json.loads(
        (
            tmp_path
            / "reports/v36-replay-integration/development_replay_audit.json"
        ).read_text(encoding="utf-8")
    )
    assert audit["lockedOosReadCount"] == 0
    assert audit["snapshotAudit"]["verifiedPartitionCount"] == 9


def _snapshot_fixture(
    root: Path,
    *,
    include_all_timeframes: bool = False,
) -> Path:
    partitions: list[dict[str, str]] = []
    timeframes = ("1h", "4h", "1dutc") if include_all_timeframes else ("1h",)
    for symbol_index, symbol in enumerate(
        ("BTC-USDT-SWAP", "ETH-USDT-SWAP", "SOL-USDT-SWAP")
    ):
        for timeframe in timeframes:
            period = {"1h": "1h", "4h": "4h", "1dutc": "1D"}[timeframe]
            dates = pd.date_range("2024-01-01", "2024-08-01", freq=period, inclusive="left", tz="UTC")
            index = pd.Series(range(len(dates)), dtype="float64")
            trend = (index * (0.018 + symbol_index * 0.003)).to_numpy()
            cycle = ((index % (37 + symbol_index * 5)) - 18).to_numpy() * 0.11
            close = 100.0 + symbol_index * 20.0 + trend + cycle
            frame = pd.DataFrame(
                {
                    "timestamp_ms": dates.astype("int64") // 1_000_000,
                    "date": dates,
                    "open": close * 0.999,
                    "high": close * 1.004,
                    "low": close * 0.996,
                    "close": close,
                    "volCcyQuote": 1_000_000.0 + index.to_numpy() * 100.0,
                    "confirm": 1,
                    "availableAt": (dates + pd.Timedelta(period)).astype(str),
                    "ingestedAt": "2026-07-19T00:00:00+00:00",
                }
            )
            path = root / "data" / symbol / timeframe / "fixture.parquet"
            path.parent.mkdir(parents=True, exist_ok=True)
            frame.to_parquet(path, index=False)
            partitions.append(
                {
                    "instrumentId": symbol,
                    "timeframe": timeframe,
                    "outputPath": str(path),
                    "outputSha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                }
            )
    manifest = {
        "schemaVersion": "okx_official_v1_snapshot_v1",
        "snapshotId": "snapshot-fixture",
        "status": "completed",
        "partitions": partitions,
    }
    manifest_path = root / "snapshot.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return manifest_path
