from __future__ import annotations

import pytest

from alphapilot.validation.preregistration import (
    build_preregistration,
    verify_preregistration,
)


def _candidate() -> dict:
    return {
        "strategyVersionId": "v1",
        "strategyFamily": "family_a",
        "tier": "A",
        "timeframe": "1d",
        "direction": "long",
        "signalDefinitionHash": "signal_hash",
        "strategyDefinitionHash": "definition_hash",
        "dataSnapshotId": "snapshot_1",
        "dataSnapshotHash": "snapshot_hash",
        "splitManifestHash": "split_hash",
    }


def test_preregistration_freezes_primary_risk_cost_and_thresholds() -> None:
    preregistration = build_preregistration(
        candidates=[_candidate()],
        environment_fingerprint={"python": "3.12.0", "platform": "test"},
        created_at="2026-07-15T00:00:00+00:00",
    )

    assert preregistration["researchOnly"] is True
    assert preregistration["primaryRiskModelId"] == "model_1_low_risk_fixed_ratio"
    assert preregistration["sensitivityRiskModelIds"] == [
        "model_2_standard_fixed_ratio",
        "model_3_correlation_constrained",
    ]
    assert preregistration["riskModels"]["model_1_low_risk_fixed_ratio"][
        "riskPerTradePct"
    ] == 0.25
    assert preregistration["costModel"]["stressMultipliers"] == [1.0, 1.5, 2.0]
    assert preregistration["sampleThresholds"]["1d"]["minimumEffectiveTrades"] == 50
    assert preregistration["passThresholds"]["signal"]["profitFactor"] == 1.10
    assert preregistration["passThresholds"]["locked"]["profitFactorExclusive"] == 1.0


def test_preregistration_has_baselines_seeds_resources_and_stable_hash() -> None:
    first = build_preregistration(
        candidates=[_candidate()],
        environment_fingerprint={"python": "3.12.0", "platform": "test"},
        created_at="2026-07-15T00:00:00+00:00",
    )
    second = build_preregistration(
        candidates=[_candidate()],
        environment_fingerprint={"platform": "test", "python": "3.12.0"},
        created_at="2026-07-15T00:00:00+00:00",
    )

    assert {item["id"] for item in first["baselines"]} == {
        "no_trade",
        "simple_directional",
    }
    assert first["seedRegistry"]["bootstrap"] == 131071
    assert first["resourceLimits"]["bootstrapDraws"] == 5000
    assert first["resourceLimits"]["monteCarloDraws"] == 5000
    assert first["outputFiles"]
    assert len(first["preRegistrationHash"]) == 64
    assert first["preRegistrationHash"] == second["preRegistrationHash"]


def test_missing_candidate_artifacts_remain_null() -> None:
    candidate = _candidate()
    candidate["dataSnapshotHash"] = None

    preregistration = build_preregistration(
        candidates=[candidate],
        environment_fingerprint={"python": "3.12.0"},
        created_at="2026-07-15T00:00:00+00:00",
    )

    assert preregistration["candidates"][0]["dataSnapshotHash"] is None


def test_locked_preregistration_verifies_without_changing_hash() -> None:
    preregistration = build_preregistration(
        candidates=[_candidate()],
        environment_fingerprint={"python": "3.12.0"},
        created_at="2026-07-15T00:00:00+00:00",
    )

    verified = verify_preregistration(preregistration)

    assert verified == preregistration


def test_locked_preregistration_rejects_tampering() -> None:
    preregistration = build_preregistration(
        candidates=[_candidate()],
        environment_fingerprint={"python": "3.12.0"},
        created_at="2026-07-15T00:00:00+00:00",
    )
    preregistration["riskModels"]["model_1_low_risk_fixed_ratio"][
        "riskPerTradePct"
    ] = 0.5

    with pytest.raises(ValueError, match="hash mismatch"):
        verify_preregistration(preregistration)
