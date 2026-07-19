from __future__ import annotations

import json
from pathlib import Path

from alphapilot.formal_validation.v36_contracts import (
    verify_v36_data_snapshot,
    verify_v36_preregistration,
)
from alphapilot.scripts.prepare_v36_tsmom_formal_handoff import prepare_handoff


IMPLEMENTATION_COMMIT = "a" * 40
READY_CANDIDATE = "v35_tsmom_crypto_adaptation"
BLOCKED_CANDIDATE = "v35_tsmom_source_replication"
SYMBOLS = ["BTC-USDT-SWAP", "ETH-USDT-SWAP", "SOL-USDT-SWAP"]


def _policy_template() -> dict[str, object]:
    return {
        "costModel": {
            "baseRoundTripCostRate": 0.002,
            "missingFundingMayBeFilledWithZero": False,
        },
        "costModelHash": "cost-hash",
        "gates": {"economic": {"completeFoldCount": 5}},
        "GateHash": "gate-hash",
        "capitalCompetitionPolicy": {"schemaVersion": "capital-v2"},
        "capitalCompetitionPolicyHash": "capital-hash",
        "capacityModelHash": "capacity-hash",
        "correlationClusterPolicyHash": "cluster-hash",
        "portfolioBetaPolicyHash": "beta-hash",
        "signalRankingPolicyHash": "ranking-hash",
        "formalPortfolioPolicyV2Hash": "portfolio-hash",
        "formalPolicyObjects": {"capacity": {"definitionHash": "capacity-hash"}},
        "benchmarkPolicy": {"mainGateBenchmark": "same_event_fixed_12_bar_exit"},
        "statisticalPolicy": {
            "multipleTestingResultsMayBeReconstructedAfterRun": False
        },
        "stoppingRules": {"sameFormalWindowRerunAllowed": False},
        "trialLineagePolicy": {"postResultParameterChangeAllowed": False},
    }


def _candidate(
    candidate_id: str,
    *,
    timeframe: str,
    sample_count: int,
    cutoff: str,
    status: str,
) -> dict[str, object]:
    partitions = []
    for symbol in SYMBOLS:
        partitions.append(
            {
                "instrumentId": symbol,
                "timeframe": timeframe,
                "path": "",
                "sha256": "",
                "rowCount": sample_count,
            }
        )
    return {
        "candidateId": candidate_id,
        "selectedTrialId": f"trial-{candidate_id}",
        "strategyDefinitionHash": f"definition-{candidate_id}",
        "exitPolicyHash": f"exit-{candidate_id}",
        "timeframe": timeframe,
        "status": status,
        "blockers": [] if status == "ready" else ["purged_walk_forward_capacity_insufficient"],
        "formalWindow": {
            "start": "2025-01-01T00:00:00+00:00",
            "cutoffExclusive": cutoff,
            "metadataOnlyAudit": True,
        },
        "ohlcvCoverage": {
            "commonRowCount": sample_count,
            "instrumentCount": 3,
            "partitions": partitions,
        },
    }


def test_prepare_v36_handoff_freezes_only_ready_candidate_and_keeps_zero_budget(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    data_root = tmp_path / "data"
    repo_root.mkdir()
    readiness = {
        "schemaVersion": "v36_tsmom_formal_readiness_v1",
        "campaignId": "v36-development-replay-fixture",
        "snapshotId": "source-snapshot-fixture",
        "sourceCommit": IMPLEMENTATION_COMMIT,
        "readinessHash": "readiness-hash",
        "formalRunCount": 0,
        "formalInputReadCount": 0,
        "resultReadCount": 0,
        "lockedOosAccessCount": 0,
        "releaseCount": 0,
        "demoArm": False,
        "orderCount": 0,
        "candidates": [
            _candidate(
                READY_CANDIDATE,
                timeframe="4h",
                sample_count=3382,
                cutoff="2026-07-18T16:00:00+00:00",
                status="ready",
            ),
            _candidate(
                BLOCKED_CANDIDATE,
                timeframe="1dutc",
                sample_count=563,
                cutoff="2026-07-18T00:00:00+00:00",
                status="blocked",
            ),
        ],
    }
    for candidate in readiness["candidates"]:
        for partition in candidate["ohlcvCoverage"]["partitions"]:
            relative = (
                Path("okx_official_v1")
                / "canonical"
                / "swap"
                / "ohlcv"
                / partition["instrumentId"]
                / candidate["timeframe"]
                / "partition.parquet"
            )
            path = data_root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(f"ohlcv:{candidate['timeframe']}:{partition['instrumentId']}".encode())
            partition["path"] = str(path)
    for symbol in SYMBOLS:
        path = (
            data_root
            / "_alphapilot"
            / "canonical"
            / "okx"
            / "swap"
            / "funding"
            / symbol
            / "part.parquet"
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f"funding:{symbol}".encode())

    readiness_path = tmp_path / "readiness.json"
    policy_path = tmp_path / "policy.json"
    readiness_path.write_text(json.dumps(readiness), encoding="utf-8")
    policy_path.write_text(json.dumps(_policy_template()), encoding="utf-8")

    result = prepare_handoff(
        repo_root=repo_root,
        data_root=data_root,
        readiness_path=readiness_path,
        policy_template_path=policy_path,
        implementation_commit=IMPLEMENTATION_COMMIT,
        remote_freeze_tag="v13.27.1.36-formal-handoff",
    )

    assert result["status"] == "prepared_zero_budget"
    assert result["preparedCandidateIds"] == [READY_CANDIDATE]
    assert result["blockedCandidateIds"] == [BLOCKED_CANDIDATE]
    assert result["formalRunCount"] == 0
    assert result["formalInputReadCount"] == 0
    assert result["resultReadCount"] == 0
    assert result["lockedOosAccessCount"] == 0
    assert result["releaseCount"] == 0
    assert result["demoArm"] is False
    assert result["orderCount"] == 0

    snapshot = json.loads(Path(result["snapshotPaths"][0]).read_text(encoding="utf-8"))
    preregistration = json.loads(
        Path(result["preregistrationPaths"][0]).read_text(encoding="utf-8")
    )
    assert verify_v36_data_snapshot(snapshot)
    assert verify_v36_preregistration(preregistration)
    assert snapshot["candidateId"] == READY_CANDIDATE
    assert snapshot["datasetReferences"][0]["columnMap"] == {
        "confirmed": "confirm",
        "volume": "volCcyQuote",
    }
    assert len(snapshot["fundingDatasetReferences"]) == 3
    assert not list(repo_root.rglob("formal_run_authorization.json"))

    blocked = json.loads(
        (repo_root / result["blockedEvidencePath"]).read_text(encoding="utf-8")
    )
    assert blocked["blockedCandidates"][0]["candidateId"] == BLOCKED_CANDIDATE
    assert blocked["blockedCandidates"][0]["formalRunClaimBudget"] == 0
