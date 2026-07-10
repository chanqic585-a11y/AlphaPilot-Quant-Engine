"""Deterministic Platt calibration and reliability summaries."""

from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import fmean


def _sigmoid(value: float) -> float:
    if value >= 0:
        return 1 / (1 + math.exp(-value))
    exponent = math.exp(value)
    return exponent / (1 + exponent)


@dataclass(frozen=True)
class CalibrationBin:
    lowerBound: float
    upperBound: float
    count: int
    meanProbability: float
    observedRate: float


@dataclass(frozen=True)
class CalibrationResult:
    slope: float
    intercept: float
    brierBefore: float
    brierAfter: float
    calibratedProbabilities: list[float]
    reliabilityBins: list[CalibrationBin]
    researchOnly: bool = True


def _validate(scores: list[float], labels: list[int]) -> None:
    if not scores or len(scores) != len(labels):
        raise ValueError("Aligned non-empty scores and labels are required")
    if not all(math.isfinite(value) for value in scores):
        raise ValueError("Calibration scores must be finite")
    if set(labels) - {0, 1} or len(set(labels)) < 2:
        raise ValueError("Calibration labels must contain both binary classes")


def _reliability_bins(
    probabilities: list[float], labels: list[int], bin_count: int
) -> list[CalibrationBin]:
    bins: list[CalibrationBin] = []
    for index in range(bin_count):
        lower = index / bin_count
        upper = (index + 1) / bin_count
        members = [
            item
            for item, probability in enumerate(probabilities)
            if lower <= probability < upper or (index == bin_count - 1 and probability == 1)
        ]
        if not members:
            continue
        bins.append(
            CalibrationBin(
                lowerBound=lower,
                upperBound=upper,
                count=len(members),
                meanProbability=fmean(probabilities[item] for item in members),
                observedRate=fmean(labels[item] for item in members),
            )
        )
    return bins


def calibrate_scores(
    scores: list[float],
    labels: list[int],
    *,
    epochs: int = 1000,
    learning_rate: float = 0.1,
    l2_penalty: float = 0.0001,
    bin_count: int = 10,
) -> CalibrationResult:
    _validate(scores, labels)
    if epochs <= 0 or learning_rate <= 0 or bin_count <= 0:
        raise ValueError("Calibration parameters must be positive")
    slope = 1.0
    intercept = 0.0
    for _ in range(epochs):
        probabilities = [_sigmoid(intercept + slope * score) for score in scores]
        errors = [probability - label for probability, label in zip(probabilities, labels, strict=True)]
        intercept -= learning_rate * fmean(errors)
        slope_gradient = fmean(error * score for error, score in zip(errors, scores, strict=True))
        slope_gradient += l2_penalty * slope
        slope -= learning_rate * slope_gradient
    before = [_sigmoid(score) for score in scores]
    after = [_sigmoid(intercept + slope * score) for score in scores]
    brier_before = fmean(
        (probability - label) ** 2 for probability, label in zip(before, labels, strict=True)
    )
    brier_after = fmean(
        (probability - label) ** 2 for probability, label in zip(after, labels, strict=True)
    )
    return CalibrationResult(
        slope=slope,
        intercept=intercept,
        brierBefore=brier_before,
        brierAfter=brier_after,
        calibratedProbabilities=after,
        reliabilityBins=_reliability_bins(after, labels, bin_count),
    )
