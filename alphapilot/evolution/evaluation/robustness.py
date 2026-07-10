"""Seeded bootstrap and cross-dimension stability summaries."""

from __future__ import annotations

import math
import random
from collections import defaultdict
from dataclasses import dataclass
from statistics import fmean, median, pstdev
from typing import Any


@dataclass(frozen=True)
class BootstrapInterval:
    estimate: float
    lower: float
    upper: float
    confidence: float
    iterations: int
    blockSize: int
    seed: int


@dataclass(frozen=True)
class ParameterNeighborhoodResult:
    centerScore: float
    neighborMedian: float
    medianRatio: float
    positiveFraction: float
    dispersion: float
    stable: bool


@dataclass(frozen=True)
class DimensionStabilityResult:
    dimension: str
    groupCount: int
    groupMetrics: dict[str, float]
    positiveFraction: float
    worstGroup: str | None
    worstScore: float | None
    stable: bool


def _quantile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower_index = math.floor(position)
    upper_index = math.ceil(position)
    if lower_index == upper_index:
        return ordered[lower_index]
    weight = position - lower_index
    return ordered[lower_index] * (1 - weight) + ordered[upper_index] * weight


def block_bootstrap_confidence_interval(
    values: list[float],
    *,
    block_size: int,
    iterations: int = 1000,
    confidence: float = 0.95,
    seed: int = 7,
) -> BootstrapInterval:
    if not values or not all(math.isfinite(value) for value in values):
        raise ValueError("Bootstrap values must be non-empty and finite")
    if not 1 <= block_size <= len(values):
        raise ValueError("block_size must be between one and sample length")
    if iterations <= 0 or not 0 < confidence < 1:
        raise ValueError("Invalid bootstrap iterations or confidence")
    generator = random.Random(seed)
    sample_length = len(values)
    max_start = sample_length - block_size
    estimates: list[float] = []
    for _ in range(iterations):
        sample: list[float] = []
        while len(sample) < sample_length:
            start = generator.randint(0, max_start)
            sample.extend(values[start : start + block_size])
        estimates.append(fmean(sample[:sample_length]))
    tail = (1 - confidence) / 2
    return BootstrapInterval(
        estimate=fmean(values),
        lower=_quantile(estimates, tail),
        upper=_quantile(estimates, 1 - tail),
        confidence=confidence,
        iterations=iterations,
        blockSize=block_size,
        seed=seed,
    )


def evaluate_parameter_neighborhood(
    *,
    center_score: float,
    neighbor_scores: list[float],
    minimum_median_ratio: float = 0.75,
    minimum_positive_fraction: float = 0.75,
) -> ParameterNeighborhoodResult:
    values = [center_score, *neighbor_scores]
    if not neighbor_scores or not all(math.isfinite(value) for value in values):
        raise ValueError("Finite center and neighbor scores are required")
    neighbor_median = median(neighbor_scores)
    if center_score > 0:
        median_ratio = neighbor_median / center_score
    else:
        median_ratio = 0.0
    positive_fraction = sum(value > 0 for value in neighbor_scores) / len(neighbor_scores)
    dispersion = pstdev(neighbor_scores) if len(neighbor_scores) > 1 else 0.0
    stable = (
        center_score > 0
        and median_ratio >= minimum_median_ratio
        and positive_fraction >= minimum_positive_fraction
    )
    return ParameterNeighborhoodResult(
        centerScore=center_score,
        neighborMedian=neighbor_median,
        medianRatio=median_ratio,
        positiveFraction=positive_fraction,
        dispersion=dispersion,
        stable=stable,
    )


def evaluate_group_stability(
    rows: list[dict[str, Any]],
    *,
    dimensions: list[str],
    metric: str,
    minimum_positive_fraction: float = 0.75,
    minimum_groups: int = 2,
) -> dict[str, DimensionStabilityResult]:
    if not rows or not dimensions:
        raise ValueError("Rows and dimensions are required")
    results: dict[str, DimensionStabilityResult] = {}
    for dimension in dimensions:
        grouped: dict[str, list[float]] = defaultdict(list)
        for row in rows:
            if dimension not in row or metric not in row:
                raise ValueError(f"Missing {dimension} or {metric} in robustness row")
            value = float(row[metric])
            if not math.isfinite(value):
                raise ValueError("Robustness metrics must be finite")
            grouped[str(row[dimension])].append(value)
        group_metrics = {key: fmean(values) for key, values in sorted(grouped.items())}
        worst_group = min(group_metrics, key=group_metrics.get) if group_metrics else None
        worst_score = group_metrics[worst_group] if worst_group is not None else None
        positive_fraction = (
            sum(value > 0 for value in group_metrics.values()) / len(group_metrics)
            if group_metrics
            else 0.0
        )
        results[dimension] = DimensionStabilityResult(
            dimension=dimension,
            groupCount=len(group_metrics),
            groupMetrics=group_metrics,
            positiveFraction=positive_fraction,
            worstGroup=worst_group,
            worstScore=worst_score,
            stable=len(group_metrics) >= minimum_groups
            and positive_fraction >= minimum_positive_fraction,
        )
    return results
