"""Typed portfolio-strategy gates for cross-sectional hypothesis C."""

from __future__ import annotations

from typing import Any, Mapping

from .gate_schema import public_gate_projection, require_metric_type


def _number(row: Mapping[str, Any], key: str) -> float:
    value = row.get(key)
    if value is None:
        return float("-inf")
    return float(value)


def _operational_gates(row: Mapping[str, Any]) -> bool:
    return all(
        row.get(key) is True
        for key in ("betaPassed", "turnoverPassed", "capacityPassed")
    )


def evaluate_portfolio_strategy_gates(
    *,
    development_metrics: Mapping[str, Any] | None,
    walk_forward_metrics: Mapping[str, Any] | None,
    holdout_metrics: Mapping[str, Any] | None,
    stress_1_5x_metrics: Mapping[str, Any] | None,
    uncertainty: Mapping[str, Any] | None,
    simple_benchmark_passed: bool,
    capital_competition_passed: bool,
    implementation_parity_passed: bool,
    formal_data_provenance_passed: bool,
    portfolio_backtest_executed: bool = True,
    translation_parity_passed: bool = True,
) -> dict[str, Any]:
    development = require_metric_type(development_metrics, "portfolio", "developmentMetrics")
    walk_forward = require_metric_type(walk_forward_metrics, "portfolio", "walkForwardMetrics")
    holdout = require_metric_type(holdout_metrics, "portfolio", "holdoutMetrics")
    stress = require_metric_type(stress_1_5x_metrics, "portfolio", "stress1_5xMetrics")
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
            _number(development, "netReturn") > 0,
            _number(development, "positiveRebalanceRatio") >= 0.60,
            _number(development, "maximumDrawdownPct") <= 25.0,
            _operational_gates(development),
        )
    )
    walk_forward_basic = not missing and all(
        (
            _number(walk_forward, "netReturn") > 0,
            _number(walk_forward, "positiveFoldCount") >= 3,
            _number(walk_forward, "foldCount") == 5,
            _number(walk_forward, "maximumDrawdownPct") <= 25.0,
            _number(walk_forward, "positiveRebalanceRatio") >= 0.60,
            _operational_gates(walk_forward),
        )
    )
    formal_walk_forward = not missing and all(
        (
            _number(walk_forward, "netReturn") > 0,
            _number(walk_forward, "positiveFoldCount") >= 4,
            _number(walk_forward, "foldCount") == 5,
            _number(walk_forward, "maximumDrawdownPct") <= 20.0,
            _operational_gates(walk_forward),
        )
    )
    clean_holdout_passed = not missing and all(
        (
            _number(holdout, "netReturn") > 0,
            _number(holdout, "relativeBenchmarkExcessReturn") > 0,
            _number(holdout, "positiveRebalanceRatio") >= 0.60,
            _operational_gates(holdout),
            holdout.get("singleSymbolContributionPassed") is True,
            holdout.get("singleMonthContributionPassed") is True,
        )
    )
    stress_passed = not missing and _number(stress, "netReturn") > 0
    uncertainty_passed = (
        not missing and _number(uncertainty, "benchmarkExcessReturnLower90") > 0
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
            portfolio_backtest_executed,
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
        "schemaVersion": "portfolio_strategy_gate_v2",
        "strategyType": "portfolio",
        **public,
        "eventReplayExecuted": False,
        "freqtradeBacktestExecuted": False,
        "portfolioBacktestExecuted": portfolio_backtest_executed,
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
