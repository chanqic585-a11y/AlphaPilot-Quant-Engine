"""Reject high absolute-correlation factor series without imputing missing values."""

from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import fmean


@dataclass(frozen=True)
class CorrelationRejection:
    candidateId: str
    reason: str
    referenceId: str | None
    correlation: float | None


@dataclass(frozen=True)
class CorrelationFilterResult:
    acceptedIds: list[str]
    rejected: list[CorrelationRejection]
    threshold: float
    observationCount: int


def _pearson(left: list[float], right: list[float]) -> float | None:
    left_mean = fmean(left)
    right_mean = fmean(right)
    left_centered = [value - left_mean for value in left]
    right_centered = [value - right_mean for value in right]
    left_ss = sum(value * value for value in left_centered)
    right_ss = sum(value * value for value in right_centered)
    if left_ss <= 0 or right_ss <= 0:
        return None
    return sum(a * b for a, b in zip(left_centered, right_centered, strict=True)) / math.sqrt(
        left_ss * right_ss
    )


def filter_correlated_candidates(
    *,
    candidate_series: dict[str, list[float]],
    reference_series: dict[str, list[float]] | None = None,
    threshold: float = 0.9,
    minimum_observations: int = 30,
) -> CorrelationFilterResult:
    if not 0 < threshold <= 1:
        raise ValueError("threshold must be in (0, 1]")
    if minimum_observations < 2:
        raise ValueError("minimum_observations must be at least two")
    all_series = {**(reference_series or {}), **candidate_series}
    if not all_series:
        return CorrelationFilterResult([], [], threshold, 0)
    lengths = {len(values) for values in all_series.values()}
    if len(lengths) != 1:
        raise ValueError("All correlation series must have equal length")
    observation_count = lengths.pop()
    if observation_count < minimum_observations:
        raise ValueError("Insufficient observations for correlation filtering")
    for series_id, values in all_series.items():
        if not all(math.isfinite(value) for value in values):
            raise ValueError(f"Series {series_id} contains non-finite values")

    accepted: list[str] = []
    rejected: list[CorrelationRejection] = []
    comparison_pool = dict(sorted((reference_series or {}).items()))
    for candidate_id, values in sorted(candidate_series.items()):
        if _pearson(values, values) is None:
            rejected.append(
                CorrelationRejection(candidate_id, "insufficient_variance", None, None)
            )
            continue
        strongest_reference = None
        strongest_correlation = 0.0
        for reference_id, reference_values in comparison_pool.items():
            correlation = _pearson(values, reference_values)
            if correlation is None:
                continue
            if abs(correlation) > abs(strongest_correlation):
                strongest_reference = reference_id
                strongest_correlation = correlation
        if strongest_reference is not None and abs(strongest_correlation) >= threshold:
            rejected.append(
                CorrelationRejection(
                    candidate_id,
                    "correlation_threshold_exceeded",
                    strongest_reference,
                    strongest_correlation,
                )
            )
            continue
        accepted.append(candidate_id)
        comparison_pool[candidate_id] = values
    return CorrelationFilterResult(accepted, rejected, threshold, observation_count)
