"""Frozen V13.27.1.17 contracts created before formal S01 results exist."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

from alphapilot.data_foundation.checkpoint import write_json_atomic
from alphapilot.evolution.evaluation.purged_walk_forward import build_purged_walk_forward
from alphapilot.evolution.registry.hashing import stable_hash
from alphapilot.research_screening.capital_competition import CapitalCompetitionPolicy

from .holdout_lineage_audit import CAMPAIGN_ID as SOURCE_CAMPAIGN_ID, load_metadata_json


FORMAL_CAMPAIGN_ID = "advisory_r_v17"
S01_CANDIDATE_ID = "s01_bear_idiosyncratic_selloff_recovery_4h"
FORMAL_PREREGISTRATION_PATH = (
    Path("research/preregistrations") / f"{FORMAL_CAMPAIGN_ID}_s01_formal_walk_forward.json"
)
SOURCE_PREREGISTRATION_PATH = (
    Path("research/preregistrations") / f"{SOURCE_CAMPAIGN_ID}.json"
)
SNAPSHOT_PATH = Path("research/data_snapshots/minimal_snapshot_785e47b180c17327dcb35e37.json")
FROZEN_AT = "2026-07-17T00:00:00Z"
MAXIMUM_HOLD_BARS = 24
PURGE_BARS = 24
EMBARGO_BARS = 24
FOLD_COUNT = 5
BAR_HOURS = 4


def _parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _hash_payload(payload: Mapping[str, Any], prefix: str) -> str:
    return stable_hash(dict(payload), prefix=prefix)


def verify_s01_formal_preregistration(payload: Mapping[str, Any]) -> bool:
    """Verify the frozen preregistration without reading any result artifact."""

    core = {key: value for key, value in payload.items() if key != "preregistrationHash"}
    expected = _hash_payload(core, "s01_formal_walk_forward_preregistration")
    return payload.get("preregistrationHash") == expected


def _build_split_policy(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    effective_starts = dict(snapshot["effectiveStarts"])
    common_start = max(
        _parse_utc(str(timeframes["4h"])) for timeframes in effective_starts.values()
    )
    common_cutoff = _parse_utc(str(snapshot["commonCutoffByTimeframe"]["4h"]))
    bar_delta = timedelta(hours=BAR_HOURS)
    sample_count = int((common_cutoff - common_start) / bar_delta)
    if sample_count <= 0:
        raise ValueError("frozen 4h sample has no complete bars")

    gap = PURGE_BARS + EMBARGO_BARS
    minimum_train_size = int(sample_count * 0.40)
    test_size = (sample_count - minimum_train_size - gap) // FOLD_COUNT
    if test_size <= 0:
        raise ValueError("frozen 4h sample cannot support five folds")
    manifest = build_purged_walk_forward(
        sample_count=sample_count,
        min_train_size=minimum_train_size,
        test_size=test_size,
        step_size=test_size,
        label_horizon=PURGE_BARS,
        embargo_size=EMBARGO_BARS,
        max_holding_period=MAXIMUM_HOLD_BARS,
        min_folds=FOLD_COUNT,
        mode="expanding",
    )
    if len(manifest.folds) != FOLD_COUNT:
        raise ValueError(f"expected exactly five folds, got {len(manifest.folds)}")

    folds: list[dict[str, Any]] = []
    for fold in manifest.folds:
        item = fold.to_dict()
        item.update(
            {
                "trainStartTimestamp": _iso(common_start + fold.trainStart * bar_delta),
                "trainEndExclusiveTimestamp": _iso(
                    common_start + fold.trainEndExclusive * bar_delta
                ),
                "purgeStartTimestamp": _iso(common_start + fold.purgeStart * bar_delta),
                "purgeEndExclusiveTimestamp": _iso(
                    common_start + fold.purgeEndExclusive * bar_delta
                ),
                "embargoStartTimestamp": _iso(
                    common_start + fold.embargoStart * bar_delta
                ),
                "embargoEndExclusiveTimestamp": _iso(
                    common_start + fold.embargoEndExclusive * bar_delta
                ),
                "testStartTimestamp": _iso(common_start + fold.testStart * bar_delta),
                "testEndExclusiveTimestamp": _iso(
                    common_start + fold.testEndExclusive * bar_delta
                ),
            }
        )
        folds.append(item)

    last_test_end = manifest.folds[-1].testEndExclusive
    policy: dict[str, Any] = {
        "schemaVersion": "s01_purged_walk_forward_split_v1",
        "mode": "expanding",
        "ordering": "chronological_utc",
        "timeframe": "4h",
        "barHours": BAR_HOURS,
        "foldCount": FOLD_COUNT,
        "commonStart": _iso(common_start),
        "commonCutoffExclusive": _iso(common_cutoff),
        "sampleCount": sample_count,
        "minimumTrainFraction": 0.40,
        "minimumTrainBars": minimum_train_size,
        "testBarsPerFold": test_size,
        "purgeBars": PURGE_BARS,
        "embargoBars": EMBARGO_BARS,
        "maximumHoldBars": MAXIMUM_HOLD_BARS,
        "eventMayCrossFoldBoundary": False,
        "unusedTailBars": sample_count - last_test_end,
        "folds": folds,
    }
    policy["splitPolicyHash"] = _hash_payload(policy, "s01_formal_split_policy")
    return policy


def _build_capital_policy() -> dict[str, Any]:
    policy: dict[str, Any] = {
        "schemaVersion": "s01_formal_capital_competition_v1",
        "source": "existing_alphapilot_standard_capital_competition_policy",
        **asdict(CapitalCompetitionPolicy()),
        "duplicateSymbolPolicy": "reject_while_open",
        "capacityRequirement": "capacityPassed_true",
        "rankingPolicy": [
            "residual_z_more_extreme_first",
            "recovery_confirmation_stronger_first",
            "liquidity_higher_first",
            "symbol_id_ascending_tiebreak",
        ],
        "resultDrivenRiskReductionAllowed": False,
    }
    policy["capitalCompetitionPolicyHash"] = _hash_payload(
        policy, "s01_formal_capital_competition"
    )
    return policy


def _build_cost_model() -> dict[str, Any]:
    model: dict[str, Any] = {
        "schemaVersion": "s01_formal_cost_model_v1",
        "source": "v16_round_trip_cost_model",
        "baseRoundTripCostRate": 0.002,
        "baseComponentsBpsPerSide": {
            "fee": 5.0,
            "slippage": 2.5,
            "spreadProxy": 2.5,
        },
        "gapPolicy": "execute_at_observed_gap_open_when_stop_or_exit_is_crossed",
        "partialExitLegsChargedSeparately": True,
        "scenarios": [
            {"scenarioId": "base", "multiplier": 1.0},
            {"scenarioId": "cost_1_5x", "multiplier": 1.5},
            {"scenarioId": "cost_2_0x", "multiplier": 2.0},
        ],
        "historicalFundingMissingValue": None,
        "missingFundingMayBeFilledWithZero": False,
        "conservativeFundingStress": {
            "method": "adverse_quantile_from_available_same_exchange_history",
            "quantile": 0.90,
            "applyByObservedSettlementCount": True,
            "evidenceStatusWhenInsufficient": "partial_or_proxy",
        },
    }
    model["costModelHash"] = _hash_payload(model, "s01_formal_cost_model")
    return model


def _build_benchmark_policy() -> dict[str, Any]:
    policy: dict[str, Any] = {
        "schemaVersion": "s01_formal_benchmark_policy_v1",
        "mainGateBenchmark": "same_event_fixed_12_bar_exit",
        "diagnosticBenchmarks": ["no_trade", "btc_contextual_return"],
        "benchmarkMayChangeAfterResults": False,
    }
    policy["benchmarkHash"] = _hash_payload(policy, "s01_formal_benchmark")
    return policy


def build_s01_formal_preregistration(repo_root: Path) -> dict[str, Any]:
    """Build a deterministic preregistration without opening formal result data."""

    repo_root = Path(repo_root).resolve()
    source = load_metadata_json(repo_root / SOURCE_PREREGISTRATION_PATH)
    snapshot = load_metadata_json(repo_root / SNAPSHOT_PATH)
    candidate = next(
        row for row in source["candidates"] if row["candidateId"] == S01_CANDIDATE_ID
    )
    formal_universe = sorted(
        {
            str(row["instrumentId"])
            for row in snapshot["datasetReferences"]
            if str(row["timeframe"]) == "4h"
        }
    )
    split_policy = _build_split_policy(snapshot)
    capital_policy = _build_capital_policy()
    cost_model = _build_cost_model()
    benchmark_policy = _build_benchmark_policy()
    risk_config = {
        "capitalCompetitionPolicyHash": capital_policy["capitalCompetitionPolicyHash"],
        "initialStopMayWiden": False,
        "addingToLossAllowed": False,
        "martingaleAllowed": False,
    }
    risk_config_hash = _hash_payload(risk_config, "s01_formal_risk_config")

    payload: dict[str, Any] = {
        "schemaVersion": "s01_formal_walk_forward_preregistration_v1",
        "campaignId": FORMAL_CAMPAIGN_ID,
        "frozenAt": FROZEN_AT,
        "sourceCampaignId": source["campaignId"],
        "sourcePreregistrationHash": source["preregistrationHash"],
        "sourceCandidateId": S01_CANDIDATE_ID,
        "strategyDefinitionHash": candidate["strategyDefinitionHash"],
        "exitPolicyHash": candidate["exitPolicyHash"],
        "implementationConformanceHash": source["implementationConformanceHash"],
        "dataSnapshotId": snapshot["snapshotId"],
        "dataSnapshotHash": snapshot["snapshotHash"],
        "coreUniverseHash": snapshot["coreUniverseHash"],
        "coreUniverse": {
            "instrumentCount": len(formal_universe),
            "instrumentIds": formal_universe,
            "selection": "frozen_v16_fixed_core",
            "fixedCohortLimitation": True,
        },
        "riskConfig": risk_config,
        "riskConfigHash": risk_config_hash,
        "costModel": cost_model,
        "costModelHash": cost_model["costModelHash"],
        "benchmarkPolicy": benchmark_policy,
        "benchmarkHash": benchmark_policy["benchmarkHash"],
        "splitPolicy": split_policy,
        "splitPolicyHash": split_policy["splitPolicyHash"],
        "purgeBars": PURGE_BARS,
        "embargoBars": EMBARGO_BARS,
        "capitalCompetitionPolicy": capital_policy,
        "capitalCompetitionPolicyHash": capital_policy[
            "capitalCompetitionPolicyHash"
        ],
        "statisticalPolicy": {
            "dailyReturnPanel": True,
            "neweyWest": {"oneSided": True, "maximumLagDays": 5, "alpha": 0.05},
            "benjaminiHochberg": {"campaignFamilySize": 10, "maximumQ": 0.10},
            "deflatedSharpeRatio": {"actualTrials": 10, "minimum": 0.90},
            "probabilityOfBacktestOverfittingMaximum": 0.40,
            "spaPValueMaximum": 0.10,
        },
        "trialLineagePolicy": {
            "formalCandidateCount": 1,
            "selectionBiasFamilySize": 10,
            "sourceVariantId": "S01",
            "parameterSearchAllowed": False,
        },
        "gates": {
            "economic": {
                "completeFoldCount": 5,
                "profitFactorMinimum": 1.05,
                "averageNetRMinimumExclusive": 0.0,
                "totalNetRMinimumExclusive": 0.0,
                "maximumDrawdownPercent": 25.0,
                "positiveFoldMinimum": 3,
                "cost1_5xProfitFactorMinimum": 1.0,
                "cost1_5xAverageNetRMinimumExclusive": 0.0,
                "cost1_5xTotalNetRMinimumExclusive": 0.0,
                "conservativeFundingAverageNetRMinimumExclusive": 0.0,
                "benchmarkPositiveIncrementFoldMinimum": 3,
                "benchmarkTotalIncrementalNetRMinimumExclusive": 0.0,
            },
            "statistics": {
                "neweyWestAlphaMinimumExclusive": 0.0,
                "neweyWestOneSidedPMaximum": 0.05,
                "campaignBhQMaximum": 0.10,
                "deflatedSharpeRatioMinimum": 0.90,
                "pboMaximum": 0.40,
                "spaPMaximum": 0.10,
            },
            "riskAndEvidence": {
                "maximumSingleSymbolPositiveContribution": 0.35,
                "maximumSingleMonthPositiveContribution": 0.35,
                "translationParity": 1.0,
                "exitLegParity": 1.0,
                "requiresNoLeakage": True,
                "requiresZeroHoldoutAccess": True,
                "requiresCleanLockedOosForAdmission": True,
            },
        },
        "stoppingRules": {
            "economicGateFailure": "archive_s01_current_version",
            "economicPassStatisticalFailure": "weak_or_selection_sensitive_edge",
            "walkForwardPassNoCleanHoldout": "walk_forward_research_pass_no_clean_holdout",
            "sameFormalWindowRerunAllowed": False,
            "postResultParameterChangeAllowed": False,
        },
        "lockedOosPolicy": {
            "contentRead": False,
            "accessCount": 0,
            "cleanLockedOosAvailable": False,
            "formalWalkForwardMayRunWithoutCleanHoldout": True,
            "admissionRequiresCleanHoldout": True,
            "releaseAllowedWithoutCleanHoldout": False,
        },
        "candidateCount": 1,
        "parameterChanges": 0,
        "exitPolicyChanges": 0,
        "universeChanges": 0,
        "costChanges": 0,
        "safetyBoundary": {
            "lockedOosAccessCount": 0,
            "formalEvidenceCount": 0,
            "releaseCount": 0,
            "demoArm": False,
            "orderCount": 0,
        },
    }
    payload["preregistrationHash"] = _hash_payload(
        payload, "s01_formal_walk_forward_preregistration"
    )
    return payload


def write_s01_formal_preregistration(
    payload: Mapping[str, Any], repo_root: Path
) -> Path:
    path = Path(repo_root).resolve() / FORMAL_PREREGISTRATION_PATH
    write_json_atomic(path, dict(payload))
    return path
