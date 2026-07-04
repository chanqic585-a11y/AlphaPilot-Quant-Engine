"""Factor evaluation design schema for V13.4.20."""

from __future__ import annotations

from typing import Any

from alphapilot.factors.factor_schema import FactorEvaluationMetric

FORWARD_WINDOWS = [4, 8, 12, 24]
DEFAULT_TIMEFRAME = "1h"
REGIME_SEGMENTS = ["trend", "mean_reversion", "breakout", "avoid", "unknown"]
UNIVERSE_SEGMENTS = ["BTC_ETH_SOL", "DynamicTop10", "DynamicTop15", "Top30"]


FACTOR_EVALUATION_METRICS = [
    FactorEvaluationMetric("ic", "IC", "Pearson correlation between factor value and forward return.", "higher_abs_value"),
    FactorEvaluationMetric("rank_ic", "RankIC", "Spearman rank correlation between factor rank and forward return.", "higher_abs_value"),
    FactorEvaluationMetric("forward_return_mean", "Forward Return Mean", "Mean forward return by factor bucket.", "higher"),
    FactorEvaluationMetric("forward_return_median", "Forward Return Median", "Median forward return by factor bucket.", "higher"),
    FactorEvaluationMetric("top_bottom_spread", "Top-bottom spread", "Top quantile forward return minus bottom quantile forward return.", "higher"),
    FactorEvaluationMetric("hit_tp_before_sl_probability", "Hit TP before SL probability", "Research label probability from AlphaPilot label builder.", "higher", ["Not a live probability of profit."]),
    FactorEvaluationMetric("profit_factor", "Profit Factor", "Research-only gross win over gross loss approximation.", "higher", ["Requires raw samples before promotion."]),
    FactorEvaluationMetric("expectancy", "Expectancy", "Average research sample outcome.", "higher"),
    FactorEvaluationMetric("max_drawdown", "Max Drawdown", "Maximum historical drawdown in factor-sorted research simulation.", "lower"),
    FactorEvaluationMetric("monthly_stability", "Monthly Stability", "Consistency across calendar months.", "higher"),
    FactorEvaluationMetric("pair_stability", "Pair Stability", "Consistency across pairs.", "higher"),
    FactorEvaluationMetric("turnover", "Turnover", "How often selected factor names change.", "lower_or_context_dependent"),
    FactorEvaluationMetric("coverage", "Coverage", "Share of rows with valid factor values.", "higher"),
    FactorEvaluationMetric("missing_rate", "Missing Rate", "Share of rows without valid factor values.", "lower"),
]


def build_factor_evaluation_design() -> dict[str, Any]:
    return {
        "evaluationId": "factor_evaluation_report_v01",
        "defaultTimeframe": DEFAULT_TIMEFRAME,
        "forwardWindowsBars": FORWARD_WINDOWS,
        "metrics": [metric.to_dict() for metric in FACTOR_EVALUATION_METRICS],
        "regimeSegments": REGIME_SEGMENTS,
        "universeSegments": UNIVERSE_SEGMENTS,
        "minimumRequirementsBeforeStrategyCandidate": [
            "sufficient raw sample coverage",
            "regime-aware stability",
            "pair-level stability",
            "slippage-aware sanity check",
            "no direct promotion to Dry-run",
        ],
        "researchOnly": True,
    }
