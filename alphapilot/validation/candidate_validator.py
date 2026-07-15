"""Candidate-level statistical helpers for the locked validation protocol."""

from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

import numpy as np

from alphapilot.validation.baselines import build_baseline_report
from alphapilot.validation.cost_stress import evaluate_cost_scenarios
from alphapilot.validation.monte_carlo import run_monte_carlo
from alphapilot.validation.risk_models import simulate_account_path
from alphapilot.validation.signal_metrics import (
    block_bootstrap_metrics,
    summarize_trades,
)
from alphapilot.validation.status_decision import decide_candidate_status


def effective_sample_size(values: Sequence[float]) -> dict[str, float | int | None]:
    """Estimate trade-count equivalence using lag-one serial correlation.

    Negative autocorrelation does not inflate the reported sample above the
    observed trade count. Positive clustering reduces the effective count.
    """

    series = np.asarray([float(value) for value in values], dtype=float)
    count = int(series.size)
    if count < 2 or float(series.std()) == 0:
        correlation = None
        effective = count
    else:
        correlation = float(np.corrcoef(series[:-1], series[1:])[0, 1])
        if not math.isfinite(correlation):
            correlation = None
            effective = count
        else:
            bounded = max(-0.99, min(0.99, correlation))
            raw_effective = count * (1 - bounded) / (1 + bounded)
            effective = max(1, min(count, math.floor(raw_effective)))
    return {
        "rawTradeCount": count,
        "lagOneAutocorrelation": correlation,
        "effectiveTradeCount": effective,
    }


def sample_assessment(
    *,
    timeframe: str,
    trade_count: int,
    effective_trade_count: int,
    duration_days: float,
    threshold: Mapping[str, Any],
) -> dict[str, Any]:
    """Apply the preregistered duration and effective-trade requirements."""

    minimum_duration = float(threshold["minimumDurationDays"])
    minimum_effective = int(threshold["minimumEffectiveTrades"])
    exploratory_range = threshold.get("exploratoryTradeRange")
    exploratory_only = False
    if timeframe.lower() == "1d" and exploratory_range:
        lower, upper = (int(value) for value in exploratory_range)
        exploratory_only = lower <= int(trade_count) <= upper
    duration_passed = float(duration_days) >= minimum_duration
    effective_passed = int(effective_trade_count) >= minimum_effective
    return {
        "timeframe": timeframe,
        "tradeCount": int(trade_count),
        "effectiveTradeCount": int(effective_trade_count),
        "durationDays": float(duration_days),
        "minimumDurationDays": minimum_duration,
        "minimumEffectiveTrades": minimum_effective,
        "durationPassed": duration_passed,
        "effectiveTradesPassed": effective_passed,
        "exploratoryOnly": exploratory_only,
        "passed": duration_passed and effective_passed and not exploratory_only,
    }


def contribution_concentration(
    breakdown: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Measure concentration among positive contributions only."""

    positive = {
        name: float(metrics.get("totalNetR") or 0.0)
        for name, metrics in breakdown.items()
        if float(metrics.get("totalNetR") or 0.0) > 0
    }
    total = sum(positive.values())
    if not positive or total <= 0:
        return {
            "largestPositiveContributor": None,
            "largestPositiveContributionShare": None,
            "positiveContributorCount": 0,
        }
    contributor, value = max(positive.items(), key=lambda item: (item[1], item[0]))
    return {
        "largestPositiveContributor": contributor,
        "largestPositiveContributionShare": value / total,
        "positiveContributorCount": len(positive),
    }


def benjamini_hochberg(pvalues: Mapping[str, float]) -> dict[str, float]:
    """Return monotonic Benjamini-Hochberg adjusted p-values by identity."""

    ordered = sorted(
        ((name, min(1.0, max(0.0, float(value)))) for name, value in pvalues.items()),
        key=lambda item: (item[1], item[0]),
    )
    count = len(ordered)
    adjusted: dict[str, float] = {}
    running = 1.0
    for reverse_index in range(count - 1, -1, -1):
        name, raw = ordered[reverse_index]
        rank = reverse_index + 1
        running = min(running, raw * count / rank)
        adjusted[name] = min(1.0, max(raw, running))
    return adjusted


def _number_at_least(value: Any, threshold: float) -> bool:
    return value is not None and math.isfinite(float(value)) and float(value) >= threshold


def _number_above(value: Any, threshold: float) -> bool:
    return value is not None and math.isfinite(float(value)) and float(value) > threshold


def _positive_window_report(
    walk_forward_trades: Sequence[Mapping[str, Any]],
    expected_fold_count: int,
) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in walk_forward_trades:
        fold = str(row.get("fold"))
        grouped.setdefault(fold, []).append(dict(row))
    summaries = {fold: summarize_trades(rows) for fold, rows in sorted(grouped.items())}
    positive = sum(
        _number_above(summary.get("averageNetR"), 0.0)
        for summary in summaries.values()
    )
    observed = len(summaries)
    return {
        "expectedFoldCount": expected_fold_count,
        "observedFoldCount": observed,
        "positiveAverageNetRFoldCount": positive,
        "positiveAverageNetRFoldRatio": positive / observed if observed else None,
        "foldSummaries": summaries,
        "foldIdentityIntegrityPassed": observed >= expected_fold_count,
        "limitation": (
            None
            if observed >= expected_fold_count
            else "formal trade rows do not retain all preregistered walk-forward fold identities"
        ),
    }


def _prefilter(candidate: Mapping[str, Any]) -> dict[str, Any]:
    historical = dict(candidate.get("historicalPrefilter") or {})
    required = str(candidate.get("tier")) == "C" or bool(historical.get("required"))
    profit_factor = historical.get("profitFactor")
    average_net_r = historical.get("averageNetR")
    passed = not required or (
        _number_at_least(profit_factor, 1.05)
        and _number_at_least(average_net_r, 0.02)
        and int(historical.get("tradeCount") or 0) > 0
    )
    return {
        "required": required,
        "passed": passed,
        "profitFactor": profit_factor,
        "averageNetR": average_net_r,
        "tradeCount": historical.get("tradeCount"),
        "thresholds": {"profitFactor": 1.05, "averageNetR": 0.02},
    }


def validate_candidate(
    candidate: Mapping[str, Any],
    evidence: Mapping[str, Any],
    preregistration: Mapping[str, Any],
    *,
    candidate_index: int,
) -> dict[str, Any]:
    """Run one frozen candidate through all preregistered research gates.

    Archived evidence may be replayed for diagnostics, but a contaminated or
    non-point-in-time locked sample can never produce a hard pass.
    """

    trades = [dict(row) for row in evidence.get("trades") or []]
    prefilter = _prefilter(candidate)
    base = {
        "strategyVersionId": candidate["strategyVersionId"],
        "strategyFamily": candidate.get("strategyFamily"),
        "displayLabelZh": candidate.get("displayLabelZh"),
        "tier": candidate.get("tier"),
        "timeframe": candidate.get("timeframe"),
        "direction": candidate.get("direction"),
        "prefilter": prefilter,
        "researchOnly": True,
        "archivedVersionRestored": False,
        "fullValidationExecuted": False,
        "executionEligibility": {
            "executionEligible": False,
            "dryRunApproved": False,
            "demoApproved": False,
            "liveTradingApproved": False,
            "reason": "candidate evidence closure is research-only",
        },
    }
    if not prefilter["passed"]:
        gates = {
            "signalReproducible": bool(evidence.get("signalReproducible")),
            "prefilterPassed": False,
            "cleanLockedSampleAvailable": bool(
                evidence.get("cleanLockedSampleAvailable")
            ),
            "sampleSufficient": False,
            "signalPassed": False,
            "lockedPassed": False,
            "costPassed": False,
            "stabilityPassed": False,
            "primaryRiskPassed": False,
        }
        return {
            **base,
            "gates": gates,
            "signalLayer": None,
            "lockedSample": None,
            "walkForward": None,
            "costStress": None,
            "riskModels": None,
            "monteCarlo": None,
            "baselines": None,
            "decision": decide_candidate_status(gates, sensitivity_results={}),
        }

    non_locked = [row for row in trades if row.get("split") != "locked_oos"]
    locked = [row for row in trades if row.get("split") == "locked_oos"]
    walk_forward = [row for row in trades if row.get("split") == "walk_forward"]
    validation_trades = non_locked or trades
    bootstrap_seed = int(preregistration["seedRegistry"]["bootstrap"]) + candidate_index
    monte_carlo_seed = int(preregistration["seedRegistry"]["monteCarlo"]) + candidate_index
    signal_summary = summarize_trades(validation_trades)
    bootstrap = block_bootstrap_metrics(
        validation_trades,
        draws=int(preregistration["resourceLimits"]["bootstrapDraws"]),
        seed=bootstrap_seed,
    )
    signal_layer = {
        "basis": "development_walk_forward_and_holdout_excluding_locked_oos",
        "summary": signal_summary,
        "bootstrap": bootstrap,
        "multipleTestingRawP": (
            1 - float(bootstrap["probabilityAverageNetRPositive"])
            if bootstrap.get("probabilityAverageNetRPositive") is not None
            else None
        ),
        "multipleTestingAdjustedP": None,
        "deflatedSharpeRatio": None,
        "deflatedSharpeUnavailableReason": (
            "trade-level R evidence lacks a preregistered independent return-frequency series"
        ),
        "probabilityBacktestOverfitting": None,
        "probabilityBacktestOverfittingUnavailableReason": (
            "candidate variants are not a complete symmetric parameter-combination matrix"
        ),
    }
    locked_summary = summarize_trades(locked)
    effective = effective_sample_size([float(row.get("netR") or 0) for row in locked])
    threshold = preregistration["sampleThresholds"][str(candidate["timeframe"])]
    sample = sample_assessment(
        timeframe=str(candidate["timeframe"]),
        trade_count=len(locked),
        effective_trade_count=int(effective["effectiveTradeCount"]),
        duration_days=float(locked_summary.get("durationDays") or 0.0),
        threshold=threshold,
    )
    locked_sample = {
        "status": evidence.get("lockedSampleStatus"),
        "cleanLockedSampleAvailable": bool(
            evidence.get("cleanLockedSampleAvailable")
        ),
        "diagnosticOnly": bool(evidence.get("diagnosticReplayOnly", True)),
        "summary": locked_summary,
        "effectiveSample": effective,
        "sampleAssessment": sample,
        "pointInTimeUniverseAvailable": bool(
            evidence.get("historicalPointInTimeUniverse")
        ),
        "selectionContamination": bool(evidence.get("lockedOrHoldoutUsedForSelection", True)),
    }
    expected_folds = len(
        (evidence.get("manifests") or {})
        .get("walk-forward.json", {})
        .get("folds", [])
    )
    walk_forward_report = _positive_window_report(walk_forward, expected_folds)
    cost_stress = evaluate_cost_scenarios(
        validation_trades,
        multipliers=preregistration["costModel"]["stressMultipliers"],
    )
    instrument_concentration = contribution_concentration(
        signal_summary["breakdowns"]["instrument"]
    )
    month_concentration = contribution_concentration(
        signal_summary["breakdowns"]["month"]
    )

    risk_results: dict[str, Any] = {}
    monte_carlo_results: dict[str, Any] = {}
    net_r_values = [float(row.get("netR") or 0.0) for row in trades]
    for model_offset, (model_id, model) in enumerate(preregistration["riskModels"].items()):
        if model.get("role") == "signal_normalization_only":
            continue
        risk_results[model_id] = simulate_account_path(trades, model=dict(model))
        monte_carlo_results[model_id] = run_monte_carlo(
            net_r_values,
            risk_per_trade_pct=float(model["riskPerTradePct"]),
            draws=int(preregistration["resourceLimits"]["monteCarloDraws"]),
            seed=monte_carlo_seed + model_offset,
            research_stop_pct=float(model.get("drawdownResearchStopPct", 100.0)),
        )

    pass_thresholds = preregistration["passThresholds"]
    signal_thresholds = pass_thresholds["signal"]
    wf_ratio = walk_forward_report["positiveAverageNetRFoldRatio"]
    signal_passed = all(
        (
            _number_at_least(signal_summary.get("profitFactor"), signal_thresholds["profitFactor"]),
            _number_at_least(signal_summary.get("averageNetR"), signal_thresholds["averageNetR"]),
            _number_at_least(
                bootstrap.get("probabilityAverageNetRPositive"),
                signal_thresholds["probabilityAverageNetRPositive"],
            ),
            _number_at_least(
                wf_ratio,
                signal_thresholds["positiveAverageRWalkForwardRatio"],
            ),
        )
    )
    locked_thresholds = pass_thresholds["locked"]
    locked_passed = all(
        (
            _number_above(locked_summary.get("profitFactor"), locked_thresholds["profitFactorExclusive"]),
            _number_above(locked_summary.get("averageNetR"), locked_thresholds["averageNetRExclusive"]),
            _number_above(locked_summary.get("totalNetR"), locked_thresholds["totalRExclusive"]),
        )
    )
    cost_thresholds = pass_thresholds["costStress"]
    stressed = cost_stress["scenarios"][str(float(cost_thresholds["multiplier"]))]
    cost_passed = _number_at_least(
        stressed.get("profitFactor"), cost_thresholds["profitFactor"]
    ) and _number_at_least(stressed.get("averageNetR"), cost_thresholds["averageNetR"])
    stability_thresholds = pass_thresholds["stability"]
    stability_passed = all(
        (
            _number_at_least(
                stability_thresholds["maximumSingleSymbolPositiveContribution"],
                instrument_concentration.get("largestPositiveContributionShare") or math.inf,
            ),
            _number_at_least(
                stability_thresholds["maximumSingleMonthPositiveContribution"],
                month_concentration.get("largestPositiveContributionShare") or math.inf,
            ),
            walk_forward_report["positiveAverageNetRFoldCount"]
            >= int(stability_thresholds["minimumPositiveWalkForwardWindows"]),
            walk_forward_report["foldIdentityIntegrityPassed"],
        )
    )
    primary_id = str(preregistration["primaryRiskModelId"])
    primary_risk = risk_results[primary_id]
    primary_mc = monte_carlo_results[primary_id]
    risk_thresholds = pass_thresholds["primaryRisk"]
    primary_risk_passed = _number_at_least(
        risk_thresholds["historicalMaximumDrawdownPct"],
        primary_risk.get("maximumDrawdownPct"),
    ) and _number_at_least(
        risk_thresholds["monteCarlo95MaximumDrawdownPct"],
        (primary_mc.get("maximumDrawdownPct") or {}).get("p95"),
    )
    sensitivity = {
        model_id: {
            "historicalMaximumDrawdownPct": result.get("maximumDrawdownPct"),
            "monteCarlo95MaximumDrawdownPct": (
                monte_carlo_results[model_id].get("maximumDrawdownPct") or {}
            ).get("p95"),
            "diagnosticOnly": True,
        }
        for model_id, result in risk_results.items()
        if model_id != primary_id
    }
    gates = {
        "signalReproducible": bool(evidence.get("signalReproducible")),
        "prefilterPassed": prefilter["passed"],
        "cleanLockedSampleAvailable": bool(
            evidence.get("cleanLockedSampleAvailable")
        ) and bool(evidence.get("historicalPointInTimeUniverse")),
        "sampleSufficient": sample["passed"],
        "signalPassed": signal_passed,
        "lockedPassed": locked_passed,
        "costPassed": cost_passed,
        "stabilityPassed": stability_passed,
        "primaryRiskPassed": primary_risk_passed,
    }
    return {
        **base,
        "fullValidationExecuted": True,
        "gates": gates,
        "signalLayer": signal_layer,
        "lockedSample": locked_sample,
        "walkForward": walk_forward_report,
        "costStress": cost_stress,
        "stability": {
            "instrumentConcentration": instrument_concentration,
            "monthConcentration": month_concentration,
            "passed": stability_passed,
        },
        "riskModels": risk_results,
        "monteCarlo": monte_carlo_results,
        "baselines": build_baseline_report(trades, direction=str(candidate["direction"])),
        "decision": decide_candidate_status(gates, sensitivity_results=sensitivity),
    }
