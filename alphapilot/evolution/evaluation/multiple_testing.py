"""Multiple-testing and selection-bias diagnostics for research reports."""

from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import NormalDist


@dataclass(frozen=True)
class FdrDecision:
    itemId: str
    pValue: float
    rank: int
    criticalValue: float
    adjustedPValue: float
    significant: bool


@dataclass(frozen=True)
class FdrResult:
    q: float
    discoveries: list[str]
    decisions: list[FdrDecision]


@dataclass(frozen=True)
class DeflatedSharpeResult:
    observedSharpe: float
    expectedMaximumSharpe: float
    standardError: float
    probability: float
    confidenceThreshold: float
    passes: bool
    trialCount: int
    observations: int


@dataclass(frozen=True)
class PboResult:
    pbo: float
    selectedIndexes: list[int]
    outOfSamplePercentiles: list[float]
    logits: list[float]
    partitionCount: int


def benjamini_hochberg(p_values: dict[str, float], *, q: float = 0.1) -> FdrResult:
    if not p_values:
        raise ValueError("At least one p-value is required")
    if not 0 < q <= 1:
        raise ValueError("q must be in (0, 1]")
    ordered = sorted(p_values.items(), key=lambda item: (item[1], item[0]))
    for item_id, p_value in ordered:
        if not math.isfinite(p_value) or not 0 <= p_value <= 1:
            raise ValueError(f"Invalid p-value for {item_id}: {p_value}")
    count = len(ordered)
    largest_significant_rank = 0
    for rank, (_, p_value) in enumerate(ordered, start=1):
        if p_value <= q * rank / count:
            largest_significant_rank = rank

    adjusted: list[float] = [1.0] * count
    running_min = 1.0
    for reverse_index in range(count - 1, -1, -1):
        rank = reverse_index + 1
        raw_adjusted = ordered[reverse_index][1] * count / rank
        running_min = min(running_min, raw_adjusted)
        adjusted[reverse_index] = min(1.0, running_min)

    decisions = [
        FdrDecision(
            itemId=item_id,
            pValue=p_value,
            rank=rank,
            criticalValue=q * rank / count,
            adjustedPValue=adjusted[rank - 1],
            significant=rank <= largest_significant_rank,
        )
        for rank, (item_id, p_value) in enumerate(ordered, start=1)
    ]
    return FdrResult(
        q=q,
        discoveries=[item.itemId for item in decisions if item.significant],
        decisions=decisions,
    )


def deflated_sharpe_probability(
    *,
    observed_sharpe: float,
    n_trials: int,
    observations: int,
    sharpe_std: float,
    skewness: float = 0.0,
    kurtosis: float = 3.0,
    confidence_threshold: float = 0.95,
) -> DeflatedSharpeResult:
    values = [observed_sharpe, sharpe_std, skewness, kurtosis, confidence_threshold]
    if not all(math.isfinite(value) for value in values):
        raise ValueError("Deflated Sharpe inputs must be finite")
    if n_trials <= 0 or observations <= 1:
        raise ValueError("n_trials must be positive and observations must exceed one")
    if sharpe_std < 0 or not 0 < confidence_threshold < 1:
        raise ValueError("Invalid Sharpe dispersion or confidence threshold")

    if n_trials == 1 or sharpe_std == 0:
        expected_maximum = 0.0
    else:
        normal = NormalDist()
        euler_gamma = 0.5772156649015329
        first_quantile = normal.inv_cdf(1 - 1 / n_trials)
        second_quantile = normal.inv_cdf(1 - 1 / (n_trials * math.e))
        expected_maximum = sharpe_std * (
            (1 - euler_gamma) * first_quantile + euler_gamma * second_quantile
        )

    variance_term = 1 - skewness * observed_sharpe + (
        (kurtosis - 1) / 4
    ) * observed_sharpe**2
    standard_error = math.sqrt(max(variance_term, 1e-12) / (observations - 1))
    probability = NormalDist().cdf((observed_sharpe - expected_maximum) / standard_error)
    return DeflatedSharpeResult(
        observedSharpe=observed_sharpe,
        expectedMaximumSharpe=expected_maximum,
        standardError=standard_error,
        probability=probability,
        confidenceThreshold=confidence_threshold,
        passes=probability >= confidence_threshold,
        trialCount=n_trials,
        observations=observations,
    )


def probability_of_backtest_overfitting(
    *,
    train_scores: list[list[float]],
    test_scores: list[list[float]],
) -> PboResult:
    if not train_scores or len(train_scores) != len(test_scores):
        raise ValueError("Aligned non-empty train and test partitions are required")
    selected_indexes: list[int] = []
    percentiles: list[float] = []
    logits: list[float] = []
    overfit_count = 0
    for partition_index, (train, test) in enumerate(zip(train_scores, test_scores, strict=True)):
        if not train or len(train) != len(test):
            raise ValueError(f"Partition {partition_index} has inconsistent candidate counts")
        if not all(math.isfinite(value) for value in [*train, *test]):
            raise ValueError(f"Partition {partition_index} contains a non-finite score")
        selected = max(range(len(train)), key=lambda index: (train[index], -index))
        selected_score = test[selected]
        less_count = sum(value < selected_score for value in test)
        equal_count = sum(value == selected_score for value in test)
        percentile = (less_count + 0.5 * equal_count) / len(test)
        clipped = min(max(percentile, 1e-12), 1 - 1e-12)
        logit = math.log(clipped / (1 - clipped))
        selected_indexes.append(selected)
        percentiles.append(percentile)
        logits.append(logit)
        if percentile <= 0.5:
            overfit_count += 1
    return PboResult(
        pbo=overfit_count / len(train_scores),
        selectedIndexes=selected_indexes,
        outOfSamplePercentiles=percentiles,
        logits=logits,
        partitionCount=len(train_scores),
    )
