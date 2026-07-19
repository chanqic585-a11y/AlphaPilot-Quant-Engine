from __future__ import annotations

from copy import deepcopy

import pytest

from alphapilot.evolution.registry.hashing import stable_hash
from alphapilot.formal_validation.v36_contracts import (
    build_v36_data_snapshot,
    build_v36_formal_run_authorization,
    build_v36_preregistration,
    build_v36_split_policy,
    verify_v36_data_snapshot,
    verify_v36_formal_run_authorization,
    verify_v36_preregistration,
)


CANDIDATE_ID = "v35_tsmom_crypto_adaptation"
IMPLEMENTATION_COMMIT = "a" * 40
UNIVERSE = ["BTC-USDT-SWAP", "ETH-USDT-SWAP", "SOL-USDT-SWAP"]


def _dataset_references() -> list[dict[str, object]]:
    return [
        {
            "instrumentId": symbol,
            "timeframe": "4h",
            "path": f"okx/{symbol}/4h.parquet",
            "sha256": str(index) * 64,
            "provider": "okx",
            "exchange": "okx",
            "columnMap": {"volume": "volCcyQuote", "confirmed": "confirm"},
        }
        for index, symbol in enumerate(UNIVERSE, start=1)
    ]


def _funding_references() -> list[dict[str, object]]:
    return [
        {
            "instrumentId": symbol,
            "provider": "okx",
            "exchange": "okx",
            "sourceEndpointContains": "okx.com",
            "maximumGapHours": 8,
            "partitions": [
                {
                    "path": f"funding/{symbol}/part.parquet",
                    "sha256": str(index + 3) * 64,
                }
            ],
        }
        for index, symbol in enumerate(UNIVERSE, start=1)
    ]


def _snapshot() -> dict[str, object]:
    return build_v36_data_snapshot(
        candidate_id=CANDIDATE_ID,
        timeframe="4h",
        universe=UNIVERSE,
        common_start="2025-01-01T00:00:00Z",
        common_cutoff_exclusive="2026-07-18T16:00:00Z",
        dataset_references=_dataset_references(),
        funding_references=_funding_references(),
        source_snapshot_id="source-snapshot",
    )


def _policy_template() -> dict[str, object]:
    return {
        "costModel": {
            "baseRoundTripCostRate": 0.002,
            "missingFundingMayBeFilledWithZero": False,
            "scenarios": [
                {"scenarioId": "base", "multiplier": 1.0},
                {"scenarioId": "cost_1_5x", "multiplier": 1.5},
                {"scenarioId": "cost_2_0x", "multiplier": 2.0},
            ],
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
        "statisticalPolicy": {"multipleTestingResultsMayBeReconstructedAfterRun": False},
        "stoppingRules": {"sameFormalWindowRerunAllowed": False},
        "trialLineagePolicy": {"postResultParameterChangeAllowed": False},
    }


def _readiness() -> dict[str, object]:
    return {
        "readinessHash": "readiness-hash",
        "formalRunCount": 0,
        "formalInputReadCount": 0,
        "resultReadCount": 0,
        "lockedOosAccessCount": 0,
        "releaseCount": 0,
        "demoArm": False,
        "orderCount": 0,
        "candidates": [
            {
                "candidateId": CANDIDATE_ID,
                "selectedTrialId": "v36_trial_43b2c0f5804b1f0596bc6d5691d79013699a5e1b3db0a07e7a3332ac3f6f0599",
                "strategyDefinitionHash": "v36_replay_definition_500e95aa9039039462514ee499bbb4548246b6b479b656e13a407967885d312e",
                "exitPolicyHash": "v36_tsmom_exit_policy_d608e75474fae769bb44d038d46e254f1cdee1b3de8bd259337adf4e3fc3f347",
                "timeframe": "4h",
                "status": "ready",
                "blockers": [],
            }
        ],
    }


def _preregistration() -> dict[str, object]:
    snapshot = _snapshot()
    split = build_v36_split_policy(
        timeframe="4h",
        sample_count=3382,
        common_start="2025-01-01T00:00:00Z",
        common_cutoff_exclusive="2026-07-18T16:00:00Z",
        maximum_hold_bars=180,
    )
    return build_v36_preregistration(
        implementation_commit=IMPLEMENTATION_COMMIT,
        readiness=_readiness(),
        candidate_id=CANDIDATE_ID,
        snapshot=snapshot,
        split_policy=split,
        policy_template=_policy_template(),
        remote_freeze_tag="v13.27.1.36-formal-handoff",
    )


def test_v36_snapshot_is_deterministic_and_requires_explicit_same_exchange_funding() -> None:
    first = _snapshot()
    second = _snapshot()

    assert first == second
    assert verify_v36_data_snapshot(first)
    assert first["fundingRequired"] is True
    assert first["missingFundingMayBeFilledWithZero"] is False
    assert len(first["fundingDatasetReferences"]) == 3
    assert first["coreUniverse"]["instrumentCount"] == len(UNIVERSE)

    tampered = deepcopy(first)
    tampered["fundingDatasetReferences"][0]["exchange"] = "binance"
    assert not verify_v36_data_snapshot(tampered)

    missing_count = deepcopy(first)
    del missing_count["coreUniverse"]["instrumentCount"]
    assert not verify_v36_data_snapshot(missing_count)


def test_v36_split_is_exactly_five_purged_folds_and_rejects_1d_capacity() -> None:
    split = build_v36_split_policy(
        timeframe="4h",
        sample_count=3382,
        common_start="2025-01-01T00:00:00Z",
        common_cutoff_exclusive="2026-07-18T16:00:00Z",
        maximum_hold_bars=180,
    )

    assert split["foldCount"] == 5
    assert len(split["folds"]) == 5
    assert split["purgeBars"] == 180
    assert split["embargoBars"] == 180
    assert min(row["testSize"] for row in split["folds"]) >= 60

    with pytest.raises(ValueError, match="walk_forward_capacity_insufficient"):
        build_v36_split_policy(
            timeframe="1dutc",
            sample_count=563,
            common_start="2025-01-01T00:00:00Z",
            common_cutoff_exclusive="2026-07-18T00:00:00Z",
            maximum_hold_bars=120,
        )


def test_v36_preregistration_preserves_policy_objects_and_is_tamper_evident() -> None:
    first = _preregistration()
    second = _preregistration()

    assert first == second
    assert verify_v36_preregistration(first)
    assert first["candidateCount"] == 1
    assert first["parameterChanges"] == 0
    assert first["exitPolicyChanges"] == 0
    assert first["costChanges"] == 0
    assert first["formalRunClaimBudget"] == 1
    assert first["coreUniverse"]["instrumentCount"] == len(UNIVERSE)
    assert first["lockedOosPolicy"]["contentRead"] is False
    assert first["lockedOosPolicy"]["accessCount"] == 0
    assert first["capitalCompetitionPolicyHash"] == "capital-hash"
    assert first["signalRankingPolicyHash"] == "ranking-hash"

    tampered = deepcopy(first)
    tampered["splitPolicy"]["folds"][0]["testEndExclusive"] += 1
    assert not verify_v36_preregistration(tampered)

    missing_count = deepcopy(first)
    del missing_count["coreUniverse"]["instrumentCount"]
    missing_count["preregistrationHash"] = stable_hash(
        {
            key: value
            for key, value in missing_count.items()
            if key != "preregistrationHash"
        },
        prefix="v36_tsmom_formal_preregistration",
    )
    assert not verify_v36_preregistration(missing_count)


def test_v36_authorization_stays_zero_budget_until_all_freezes_pass() -> None:
    preregistration = _preregistration()
    passed_audit = {
        "status": "passed",
        "headCommit": "b" * 40,
        "implementationCommit": IMPLEMENTATION_COMMIT,
        "blockers": [],
    }
    authorization = build_v36_formal_run_authorization(
        preregistration=preregistration,
        readiness=_readiness(),
        remote_freeze_audit=passed_audit,
    )

    assert authorization["authorizationStatus"] == "authorized"
    assert authorization["formalRunClaimBudget"] == 1
    assert authorization["formalRunCount"] == 0
    assert authorization["formalInputReadCount"] == 0
    assert verify_v36_formal_run_authorization(
        authorization, preregistration=preregistration
    )

    blocked = build_v36_formal_run_authorization(
        preregistration=preregistration,
        readiness=_readiness(),
        remote_freeze_audit={"status": "blocked", "blockers": ["tag_missing"]},
    )
    assert blocked["authorizationStatus"] == "blocked"
    assert not verify_v36_formal_run_authorization(
        blocked, preregistration=preregistration
    )
