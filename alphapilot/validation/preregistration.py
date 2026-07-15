from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence

from .hashing import stable_hash


RISK_MODELS: dict[str, dict[str, Any]] = {
    "model_0_equal_r_signal": {
        "role": "signal_normalization_only",
        "riskPerTradeR": 1.0,
        "compounding": False,
    },
    "model_1_low_risk_fixed_ratio": {
        "role": "primary_acceptance",
        "riskPerTradePct": 0.25,
        "maximumOpenRiskPct": 1.0,
        "maximumConcurrentPositions": 4,
        "maximumSymbolRiskPct": 0.5,
        "maximumDirectionalClusterRiskPct": 0.5,
        "dailyNewRiskPausePct": -1.5,
        "drawdownResearchStopPct": 10.0,
    },
    "model_2_standard_fixed_ratio": {
        "role": "sensitivity_only",
        "riskPerTradePct": 0.5,
        "maximumOpenRiskPct": 1.5,
        "maximumConcurrentPositions": 3,
        "maximumSymbolRiskPct": 0.75,
        "maximumDirectionalClusterRiskPct": 0.75,
        "dailyNewRiskPausePct": -2.0,
        "drawdownResearchStopPct": 15.0,
    },
    "model_3_correlation_constrained": {
        "role": "sensitivity_only",
        "riskPerTradePct": 0.25,
        "maximumOpenRiskPct": 1.0,
        "maximumDirectionalClusterRiskPct": 0.5,
        "highBetaRiskDiscount": True,
        "leverageCannotIncreaseAllowedLoss": True,
    },
}

COST_MODEL: dict[str, Any] = {
    "id": "uniform_registered_swap_cost_v1",
    "feeRatePerSide": 0.0005,
    "slippageRatePerSide": 0.0005,
    "fundingTreatment": "actual_when_present_otherwise_unavailable",
    "latencyBars": [0, 1, 2],
    "sameBarAmbiguity": "stop_first",
    "stressMultipliers": [1.0, 1.5, 2.0],
}

SAMPLE_THRESHOLDS: dict[str, Any] = {
    "1d": {
        "minimumDurationDays": 365,
        "minimumEffectiveTrades": 50,
        "exploratoryTradeRange": [30, 49],
    },
    "1h": {"minimumDurationDays": 183, "minimumEffectiveTrades": 80},
    "15m": {"minimumDurationDays": 183, "minimumEffectiveTrades": 150},
}

PASS_THRESHOLDS: dict[str, Any] = {
    "evidence": {
        "signalDefinitionReproducible": True,
        "dataSnapshotTraceable": True,
        "pointInTimeUniverseRequired": True,
        "lockedSampleUnusedForSelection": True,
    },
    "signal": {
        "profitFactor": 1.10,
        "averageNetR": 0.05,
        "probabilityAverageNetRPositive": 0.90,
        "positiveAverageRWalkForwardRatio": 0.60,
    },
    "locked": {
        "profitFactorExclusive": 1.0,
        "averageNetRExclusive": 0.0,
        "totalRExclusive": 0.0,
    },
    "costStress": {
        "multiplier": 1.5,
        "profitFactor": 1.0,
        "averageNetR": 0.0,
        "twoTimesCostIsObservationOnly": True,
    },
    "stability": {
        "maximumSingleSymbolPositiveContribution": 0.35,
        "maximumSingleMonthPositiveContribution": 0.35,
        "minimumPositiveWalkForwardWindows": 2,
    },
    "primaryRisk": {
        "historicalMaximumDrawdownPct": 15.0,
        "monteCarlo95MaximumDrawdownPct": 25.0,
    },
}

OUTPUT_FILES = [
    "candidate_validation_data_manifest.json",
    "candidate_validation_cost_models.json",
    "candidate_validation_risk_models.json",
    "candidate_signal_layer_report.json",
    "candidate_locked_sample_report.json",
    "candidate_walk_forward_report.json",
    "candidate_cost_stress_report.json",
    "candidate_risk_model_report.json",
    "candidate_monte_carlo_report.json",
    "candidate_portfolio_risk_report.json",
    "candidate_evidence_closure_report.json",
    "candidate_evidence_closure_summary.md",
    "candidate_evidence_closure_leaderboard.csv",
    "candidate_continue_archive.json",
    "candidate_new_version_recommendations.json",
]


def verify_preregistration(
    preregistration: Mapping[str, Any],
) -> dict[str, Any]:
    """Return a verified copy of an immutable preregistration payload."""
    payload = deepcopy(dict(preregistration))
    registered_hash = payload.pop("preRegistrationHash", None)
    if not isinstance(registered_hash, str) or not registered_hash:
        raise ValueError("preregistration is missing preRegistrationHash")
    calculated_hash = stable_hash(payload)
    if calculated_hash != registered_hash:
        raise ValueError(
            "preregistration hash mismatch; the locked protocol was modified"
        )
    return {**payload, "preRegistrationHash": registered_hash}


def build_preregistration(
    *,
    candidates: Sequence[Mapping[str, Any]],
    environment_fingerprint: Mapping[str, Any],
    created_at: str,
) -> dict[str, Any]:
    ordered_candidates = sorted(
        (deepcopy(dict(candidate)) for candidate in candidates),
        key=lambda item: (str(item.get("tier")), str(item.get("strategyVersionId"))),
    )
    risk_models = deepcopy(RISK_MODELS)
    for model in risk_models.values():
        model["modelHash"] = stable_hash(model)
    cost_model = deepcopy(COST_MODEL)
    cost_model["costModelHash"] = stable_hash(cost_model)
    core: dict[str, Any] = {
        "schemaVersion": "candidate_locked_validation_preregistration_v1",
        "createdAt": created_at,
        "researchOnly": True,
        "executionEligibilityUnchanged": True,
        "candidateDiscoveryRule": "primaryFailureType=risk_model_failure",
        "candidateDeduplicationRule": (
            "strategyFamily+canonicalSignalHash; metadata-only children do not vote"
        ),
        "candidates": ordered_candidates,
        "primaryRiskModelId": "model_1_low_risk_fixed_ratio",
        "sensitivityRiskModelIds": [
            "model_2_standard_fixed_ratio",
            "model_3_correlation_constrained",
        ],
        "riskModels": risk_models,
        "costModel": cost_model,
        "baselines": [
            {"id": "no_trade", "purpose": "capital preservation reference"},
            {
                "id": "simple_directional",
                "purpose": "frozen long-or-short directional reference",
            },
        ],
        "sampleThresholds": deepcopy(SAMPLE_THRESHOLDS),
        "passThresholds": deepcopy(PASS_THRESHOLDS),
        "multipleTesting": {
            "method": "benjamini_hochberg_fdr",
            "alpha": 0.10,
            "unavailableMetricsRemainNull": True,
        },
        "seedRegistry": {
            "bootstrap": 131071,
            "monteCarlo": 524287,
            "symbolHoldback": 8191,
        },
        "environmentFingerprint": deepcopy(dict(environment_fingerprint)),
        "resourceLimits": {
            "bootstrapDraws": 5000,
            "monteCarloDraws": 5000,
            "maximumParallelCandidates": 1,
            "checkpointAfterEachCandidate": True,
        },
        "decisionStatuses": [
            "passed",
            "failed_signal",
            "failed_cost",
            "failed_risk",
            "insufficient_sample",
            "locked_sample_unavailable",
            "signal_unreproducible",
            "prefilter_stopped",
        ],
        "recommendationLimit": 2,
        "outputFiles": list(OUTPUT_FILES),
    }
    return {**core, "preRegistrationHash": stable_hash(core)}
