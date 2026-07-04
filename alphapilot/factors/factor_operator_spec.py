"""Research-only factor operator subset for V13.4.20."""

from __future__ import annotations

from typing import Any


TIME_SERIES_OPERATORS = [
    {"operatorId": "ts_mean", "category": "time_series", "description": "Rolling mean over a lookback window."},
    {"operatorId": "ts_std", "category": "time_series", "description": "Rolling standard deviation over a lookback window."},
    {"operatorId": "ts_rank", "category": "time_series", "description": "Rank latest value within a rolling window."},
    {"operatorId": "ts_zscore", "category": "time_series", "description": "Rolling z-score of latest value."},
    {"operatorId": "ts_delta", "category": "time_series", "description": "Difference from N bars ago."},
    {"operatorId": "ts_return", "category": "time_series", "description": "Return over N bars."},
    {"operatorId": "ts_ema", "category": "time_series", "description": "Exponential moving average."},
    {"operatorId": "ts_corr", "category": "time_series", "description": "Rolling correlation between two fields."},
    {"operatorId": "ts_min", "category": "time_series", "description": "Rolling minimum."},
    {"operatorId": "ts_max", "category": "time_series", "description": "Rolling maximum."},
]

CROSS_SECTIONAL_OPERATORS = [
    {"operatorId": "rank", "category": "cross_sectional", "description": "Cross-sectional rank at one timestamp."},
    {"operatorId": "zscore", "category": "cross_sectional", "description": "Cross-sectional z-score at one timestamp."},
    {"operatorId": "winsorize", "category": "cross_sectional", "description": "Clip extreme cross-sectional values."},
    {"operatorId": "scale", "category": "cross_sectional", "description": "Scale values to comparable magnitude."},
    {"operatorId": "demean", "category": "cross_sectional", "description": "Remove cross-sectional mean."},
]

COMBINATION_OPERATORS = [
    {"operatorId": "add", "category": "combination", "description": "Add two factor expressions."},
    {"operatorId": "sub", "category": "combination", "description": "Subtract one factor expression from another."},
    {"operatorId": "mul", "category": "combination", "description": "Multiply factor expressions."},
    {"operatorId": "div_safe", "category": "combination", "description": "Safe division with zero guard."},
    {"operatorId": "where", "category": "combination", "description": "Conditional selection."},
    {"operatorId": "clip", "category": "combination", "description": "Clip values to a bounded range."},
]

EXCLUDED_OPERATOR_FAMILIES = [
    "genetic_programming",
    "automatic_complex_expression_generation",
    "deep_learning_factors",
    "reinforcement_learning_factors",
]


def build_factor_operator_subset() -> dict[str, Any]:
    return {
        "operatorSetId": "alphapilot_factor_operator_subset_v01",
        "purpose": "Keep first factor research iteration explainable, auditable, and lightweight.",
        "timeSeriesOperators": TIME_SERIES_OPERATORS,
        "crossSectionalOperators": CROSS_SECTIONAL_OPERATORS,
        "combinationOperators": COMBINATION_OPERATORS,
        "excludedOperatorFamilies": EXCLUDED_OPERATOR_FAMILIES,
        "researchOnly": True,
        "implementationStatus": "design_only",
    }
