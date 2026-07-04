"""Research-only factor operator subset for V13.4.20."""

from __future__ import annotations

import math
from statistics import mean, pstdev
from typing import Any, Iterable


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
        "implementationStatus": "lightweight_v13_4_21_subset_implemented",
    }


def _clean(values: Iterable[float | int | None]) -> list[float]:
    cleaned: list[float] = []
    for value in values:
        if value is None:
            continue
        number = float(value)
        if math.isnan(number) or math.isinf(number):
            continue
        cleaned.append(number)
    return cleaned


def safe_div(numerator: float | int | None, denominator: float | int | None) -> float | None:
    if numerator is None or denominator is None:
        return None
    denominator_value = float(denominator)
    if denominator_value == 0 or math.isnan(denominator_value) or math.isinf(denominator_value):
        return None
    numerator_value = float(numerator)
    if math.isnan(numerator_value) or math.isinf(numerator_value):
        return None
    return numerator_value / denominator_value


def ts_mean(values: Iterable[float | int | None], window: int) -> float | None:
    if window <= 0:
        return None
    cleaned = _clean(list(values)[-window:])
    return mean(cleaned) if cleaned else None


def ts_std(values: Iterable[float | int | None], window: int) -> float | None:
    if window <= 1:
        return None
    cleaned = _clean(list(values)[-window:])
    return pstdev(cleaned) if len(cleaned) > 1 else None


def ts_zscore(values: Iterable[float | int | None], window: int) -> float | None:
    sequence = list(values)
    if not sequence:
        return None
    latest = sequence[-1]
    avg = ts_mean(sequence, window)
    std = ts_std(sequence, window)
    if latest is None or avg is None or std is None or std == 0:
        return None
    return (float(latest) - avg) / std


def ts_delta(values: Iterable[float | int | None], periods: int) -> float | None:
    sequence = list(values)
    if periods <= 0 or len(sequence) <= periods:
        return None
    latest = sequence[-1]
    previous = sequence[-1 - periods]
    if latest is None or previous is None:
        return None
    return float(latest) - float(previous)


def ts_return(values: Iterable[float | int | None], periods: int) -> float | None:
    sequence = list(values)
    if periods <= 0 or len(sequence) <= periods:
        return None
    latest = sequence[-1]
    previous = sequence[-1 - periods]
    return safe_div(float(latest) - float(previous), previous) if latest is not None and previous is not None else None


def ts_ema(values: Iterable[float | int | None], span: int) -> float | None:
    if span <= 0:
        return None
    cleaned = _clean(values)
    if not cleaned:
        return None
    alpha = 2 / (span + 1)
    ema_value = cleaned[0]
    for value in cleaned[1:]:
        ema_value = (value * alpha) + (ema_value * (1 - alpha))
    return ema_value


def rank(values: Iterable[float | int | None]) -> list[float | None]:
    sequence = list(values)
    available = sorted((float(value), idx) for idx, value in enumerate(sequence) if value is not None and not math.isnan(float(value)))
    output: list[float | None] = [None] * len(sequence)
    if not available:
        return output
    if len(available) == 1:
        output[available[0][1]] = 100.0
        return output
    denominator = len(available) - 1
    for rank_idx, (_, original_idx) in enumerate(available):
        output[original_idx] = (rank_idx / denominator) * 100
    return output


def zscore(values: Iterable[float | int | None]) -> list[float | None]:
    sequence = list(values)
    cleaned = _clean(sequence)
    if len(cleaned) <= 1:
        return [None] * len(sequence)
    avg = mean(cleaned)
    std = pstdev(cleaned)
    if std == 0:
        return [0.0 if value is not None else None for value in sequence]
    return [((float(value) - avg) / std) if value is not None else None for value in sequence]


def winsorize(values: Iterable[float | int | None], lower: float = 0.01, upper: float = 0.99) -> list[float | None]:
    sequence = list(values)
    cleaned = sorted(_clean(sequence))
    if not cleaned:
        return [None] * len(sequence)
    lower_idx = max(0, min(len(cleaned) - 1, int((len(cleaned) - 1) * lower)))
    upper_idx = max(0, min(len(cleaned) - 1, int((len(cleaned) - 1) * upper)))
    lower_value = cleaned[lower_idx]
    upper_value = cleaned[upper_idx]
    output: list[float | None] = []
    for value in sequence:
        if value is None:
            output.append(None)
        else:
            number = float(value)
            output.append(min(max(number, lower_value), upper_value))
    return output
