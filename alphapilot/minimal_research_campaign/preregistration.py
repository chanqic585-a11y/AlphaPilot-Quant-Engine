"""Immutable preregistration contracts for the bounded campaign."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

from alphapilot.evolution.registry.hashing import stable_hash

from .campaign import build_hypothesis_inventory, build_representative_universe


PREFILTER_GATES = {
    "minimumEvents": 30,
    "minimumProfitFactor": 1.03,
    "minimumAverageNetR": 0.0,
    "minimumTotalNetR": 0.0,
    "minimumPositiveMonthRatio": 0.5,
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _development_start(representatives: list[dict[str, Any]]) -> str:
    starts = [
        str(row["profiles"]["4h"]["effectiveBacktestStart"])
        for row in representatives
    ]
    return max(starts)


def build_prefilter_preregistration(
    *,
    core_universe: Mapping[str, Any],
    snapshot: Mapping[str, Any],
    archived_family_ids: Iterable[str],
    implementation_commit: str,
    implementation_source_hashes: Mapping[str, str],
) -> dict[str, Any]:
    hypotheses = build_hypothesis_inventory(
        archived_family_ids=archived_family_ids
    )
    representatives = build_representative_universe(
        core_universe["members"], count=10
    )
    campaign_seed = {
        "coreUniverseHash": core_universe["coreUniverseHash"],
        "snapshotHash": snapshot["snapshotHash"],
        "hypothesisIds": [row["strategyId"] for row in hypotheses],
        "representativeIds": [row["instrumentId"] for row in representatives],
        "prefilterGates": PREFILTER_GATES,
    }
    campaign_id = f"v13_27_1_13_{stable_hash(campaign_seed)[:16]}"
    payload: dict[str, Any] = {
        "schemaVersion": "minimal_strategy_prefilter_preregistration_v1",
        "campaignId": campaign_id,
        "createdAt": _utc_now(),
        "snapshotId": snapshot["snapshotId"],
        "snapshotHash": snapshot["snapshotHash"],
        "coreUniverseHash": core_universe["coreUniverseHash"],
        "cohortBoundary": {
            "cohortType": "fixed_core_cohort",
            "historicalPitUniverse": False,
            "formalUse": "time_series_only_with_fixed_cohort_limitation",
            "crossSectionalUse": "diagnostic_only_without_historical_pit",
        },
        "hypotheses": hypotheses,
        "representativeUniverse": [
            str(row["instrumentId"]) for row in representatives
        ],
        "representativeSelectionRule": (
            "BTC_ETH_plus_listing_age_liquidity_volatility_strata_and_stable_hash"
        ),
        "dataBoundary": {
            "timeframe": "4h",
            "developmentStart": _development_start(representatives),
            "availableEnd": core_universe["commonCutoffByTimeframe"]["4h"],
            "developmentFraction": 0.55,
            "prefilterMayReadAfterDevelopmentEnd": False,
        },
        "eventDefinition": {
            "residualBenchmark": "representative_core_median_return",
            "residualZWindowBars": 42,
            "residualZThreshold": -1.75,
            "residualRecoveryDelta": 0.20,
            "recaptureRule": "close_above_previous_event_bar_midpoint",
            "marketCrashLookbackBars": 6,
            "marketCrashFloor": -0.08,
            "atrWindowBars": 14,
            "atrStopMultiple": 0.25,
            "maximumHoldBars": 18,
        },
        "eventExecution": {
            "signalOnConfirmedClose": True,
            "nextBarOnly": True,
            "initialStopFrozenBeforeEntry": True,
            "initialStopMayWiden": False,
            "partialExitAtR": 1.0,
            "partialExitFraction": 0.5,
            "remainingTargetR": 2.0,
        },
        "costModel": {
            "roundTripRate": 0.002,
            "components": ["fees", "spread_proxy", "slippage"],
            "funding": "unavailable_not_zero",
            "stressMultipliers": [1.0, 1.5, 2.0],
            "officialFeeScheduleClaimed": False,
        },
        "prefilterGates": dict(PREFILTER_GATES),
        "regimeReporting": {
            "states": ["bull", "bear", "range", "high_vol", "low_vol"],
            "postResultRegimeExclusionAllowed": False,
        },
        "experimentBudget": {
            "maximumHypotheses": 3,
            "prefilterRevisionsPerFamily": 0,
            "formalStructuralRevisionsPerSurvivingFamily": 1,
            "fourthReplacementHypothesisAllowed": False,
        },
        "implementationCommit": implementation_commit,
        "implementationSourceHashes": dict(implementation_source_hashes),
        "safetyBoundary": {
            "demoArm": False,
            "demoReleaseCount": 0,
            "orderCount": 0,
            "liveTradingEnabled": False,
            "withdrawEnabled": False,
        },
    }
    payload["preregistrationHash"] = stable_hash(
        payload, prefix="minimal_prefilter_preregistration"
    )
    return payload

def build_formal_preregistration(
    prefilter_preregistration: Mapping[str, Any],
    *,
    survivor_strategy_ids: list[str],
) -> dict[str, Any]:
    if not survivor_strategy_ids:
        raise ValueError("at least one prefilter survivor is required")
    by_id = {
        str(row["strategyId"]): row
        for row in prefilter_preregistration["hypotheses"]
    }
    invalid = [
        strategy_id
        for strategy_id in survivor_strategy_ids
        if strategy_id not in by_id
        or bool(by_id[strategy_id].get("diagnosticOnly"))
        or not bool(by_id[strategy_id].get("formalPassEligible"))
    ]
    if invalid:
        raise ValueError(f"non-survivor strategy ids are not formal eligible: {invalid}")
    payload = {
        "schemaVersion": "minimal_strategy_formal_preregistration_v1",
        "campaignId": prefilter_preregistration["campaignId"],
        "createdAt": _utc_now(),
        "prefilterPreregistrationHash": prefilter_preregistration[
            "preregistrationHash"
        ],
        "snapshotId": prefilter_preregistration["snapshotId"],
        "snapshotHash": prefilter_preregistration["snapshotHash"],
        "strategyIds": sorted(survivor_strategy_ids),
        "partitions": {
            "development": 0.55,
            "purgedWalkForward": 0.25,
            "campaignLockedOos": 0.20,
        },
        "walkForward": {"foldCount": 5, "purged": True, "embargo": True},
        "campaignLockedOos": {
            "maximumUnlockCount": 1,
            "campaignLocked": True,
            "globalCleanHoldout": False,
        },
        "costStressMultipliers": [1.0, 1.5, 2.0],
        "capitalCompetition": {
            "maximumConcurrentPositions": 5,
            "maximumTotalOpenRiskR": 5.0,
            "maximumSingleInstrumentRiskR": 1.0,
            "maximumSameDirectionPositions": 4,
            "deterministicSignalRanking": True,
        },
        "eventBasicGates": {
            "walkForwardProfitFactor": {"operator": ">=", "required": 1.05},
            "walkForwardAverageNetR": {"operator": ">", "required": 0.0},
            "walkForwardTotalNetR": {"operator": ">", "required": 0.0},
            "positiveFoldCount": {"operator": ">=", "required": 3},
            "maximumDrawdownPct": {"operator": "<=", "required": 25.0},
        },
        "eventFormalGates": {
            "walkForwardProfitFactor": {"operator": ">=", "required": 1.15},
            "walkForwardAverageNetR": {"operator": ">=", "required": 0.05},
            "positiveFoldCount": {"operator": ">=", "required": 4},
            "maximumDrawdownPct": {"operator": "<=", "required": 20.0},
            "lockedOosProfitFactor": {"operator": ">", "required": 1.0},
            "lockedOosAverageNetR": {"operator": ">", "required": 0.0},
            "lockedOosTotalNetR": {"operator": ">", "required": 0.0},
            "stress1_5xProfitFactor": {"operator": ">=", "required": 1.05},
            "stress1_5xAverageNetR": {"operator": ">", "required": 0.0},
            "singleInstrumentPositiveContribution": {
                "operator": "<=",
                "required": 0.35,
            },
            "singleMonthPositiveContribution": {
                "operator": "<=",
                "required": 0.35,
            },
        },
        "safetyBoundary": dict(prefilter_preregistration["safetyBoundary"]),
    }
    payload["preregistrationHash"] = stable_hash(
        payload, prefix="minimal_formal_preregistration"
    )
    return payload
