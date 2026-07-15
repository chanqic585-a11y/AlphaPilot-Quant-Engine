"""Typed event-strategy gates for hypotheses A and B."""

from __future__ import annotations

from typing import Any, Mapping

from .gate_schema import public_gate_projection, require_metric_type


DEVELOPMENT_MINIMUM_EVENTS = {"15m": 300, "1h": 150, "4h": 80, "1d": 40}
HOLDOUT_MINIMUM_EVENTS = {"15m": 200, "1h": 100, "4h": 50, "1d": 30}


def _number(row: Mapping[str, Any], key: str) -> float:
    value = row.get(key)
    if value is None:
        return float("-inf")
    return float(value)


def evaluate_event_strategy_gates(
    *,
    timeframe: str,
    development_metrics: Mapping[str, Any] | None,
    walk_forward_metrics: Mapping[str, Any] | None,
    holdout_metrics: Mapping[str, Any] | None,
    stress_1_5x_metrics: Mapping[str, Any] | None,
    uncertainty: Mapping[str, Any] | None,
    simple_benchmark_passed: bool,
    capital_competition_passed: bool,
    implementation_parity_passed: bool,
    formal_data_provenance_passed: bool,
    event_replay_executed: bool = True,
    freqtrade_backtest_executed: bool = True,
    translation_parity_passed: bool = True,
) -> dict[str, Any]:
    if timeframe not in DEVELOPMENT_MINIMUM_EVENTS:
        raise ValueError(f"unsupported event timeframe: {timeframe}")
    development = require_metric_type(development_metrics, "event", "developmentMetrics")
    walk_forward = require_metric_type(walk_forward_metrics, "event", "walkForwardMetrics")
    holdout = require_metric_type(holdout_metrics, "event", "holdoutMetrics")
    stress = require_metric_type(stress_1_5x_metrics, "event", "stress1_5xMetrics")
    missing = [
        name
        for name, value in (
            ("developmentMetrics", development),
            ("walkForwardMetrics", walk_forward),
            ("holdoutMetrics", holdout),
            ("stress1_5xMetrics", stress),
            ("uncertainty", uncertainty),
        )
        if value is None
    ]
    development = development or {}
    walk_forward = walk_forward or {}
    holdout = holdout or {}
    stress = stress or {}
    uncertainty = dict(uncertainty or {})

    development_passed = not missing and all(
        (
            _number(development, "profitFactor") >= 1.08,
            _number(development, "averageNetR") >= 0.03,
            _number(development, "totalNetR") > 0,
            _number(development, "positiveMonthRatio") >= 0.60,
            _number(development, "eventCount") >= DEVELOPMENT_MINIMUM_EVENTS[timeframe],
            development.get("mfeMaeComplete") is True,
            development.get("simpleBenchmarkComplete") is True,
        )
    )
    walk_forward_basic = not missing and all(
        (
            _number(walk_forward, "profitFactor") >= 1.05,
            _number(walk_forward, "averageNetR") > 0,
            _number(walk_forward, "totalNetR") > 0,
            _number(walk_forward, "maximumDrawdownPct") <= 25.0,
            _number(walk_forward, "positiveFoldCount") >= 3,
            _number(walk_forward, "foldCount") == 5,
        )
    )
    formal_walk_forward = not missing and all(
        (
            _number(walk_forward, "profitFactor") >= 1.15,
            _number(walk_forward, "averageNetR") >= 0.05,
            _number(walk_forward, "totalNetR") > 0,
            _number(walk_forward, "positiveFoldCount") >= 4,
            _number(walk_forward, "foldCount") == 5,
            _number(walk_forward, "maximumDrawdownPct") <= 20.0,
        )
    )
    clean_holdout_passed = not missing and all(
        (
            _number(holdout, "profitFactor") > 1.0,
            _number(holdout, "averageNetR") > 0,
            _number(holdout, "totalNetR") > 0,
            _number(holdout, "eventCount") >= HOLDOUT_MINIMUM_EVENTS[timeframe],
        )
    )
    stress_passed = not missing and all(
        (
            _number(stress, "profitFactor") >= 1.05,
            _number(stress, "averageNetR") > 0,
        )
    )
    uncertainty_passed = not missing and all(
        (
            _number(uncertainty, "profitFactorLower90") > 1.0,
            _number(uncertainty, "averageNetRLower90") > 0,
        )
    )
    overall_basic = development_passed and walk_forward_basic
    overall_formal = all(
        (
            overall_basic,
            formal_walk_forward,
            clean_holdout_passed,
            stress_passed,
            uncertainty_passed,
            simple_benchmark_passed,
            capital_competition_passed,
            implementation_parity_passed,
            formal_data_provenance_passed,
            event_replay_executed,
            freqtrade_backtest_executed,
            translation_parity_passed,
        )
    )
    public = public_gate_projection(
        {
            "developmentPrefilterPassed": development_passed,
            "walkForwardNumericPassed": walk_forward_basic,
            "simpleBenchmarkPassed": simple_benchmark_passed,
            "uncertaintyPassed": uncertainty_passed,
            "capitalCompetitionPassed": capital_competition_passed,
            "implementationParityPassed": implementation_parity_passed,
            "formalDataProvenancePassed": formal_data_provenance_passed,
            "cleanHoldoutPassed": clean_holdout_passed,
            "overallBasicPassed": overall_basic,
            "overallFormalPassed": overall_formal,
        }
    )
    return {
        "schemaVersion": "event_strategy_gate_v2",
        "strategyType": "event",
        **public,
        "eventReplayExecuted": event_replay_executed,
        "freqtradeBacktestExecuted": freqtrade_backtest_executed,
        "portfolioBacktestExecuted": False,
        "translationParityPassed": translation_parity_passed,
        "formalWalkForwardPassed": formal_walk_forward,
        "stress1_5xPassed": stress_passed,
        "missingEvidence": missing,
        "developmentMetrics": development_metrics,
        "walkForwardMetrics": walk_forward_metrics,
        "holdoutMetrics": holdout_metrics,
        "stress1_5xMetrics": stress_1_5x_metrics,
        "uncertainty": uncertainty,
    }
