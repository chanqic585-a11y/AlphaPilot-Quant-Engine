"""Selection-bias and HAC statistics for the frozen S01 formal campaign."""

from __future__ import annotations

from itertools import combinations
import math
from statistics import NormalDist
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

from alphapilot.evolution.evaluation.multiple_testing import (
    benjamini_hochberg,
    deflated_sharpe_probability,
    probability_of_backtest_overfitting,
)


def _finite(values: Sequence[float] | np.ndarray) -> np.ndarray:
    array = np.asarray(values, dtype="float64")
    return array[np.isfinite(array)]


def _normal_one_sided_p(t_value: float) -> float:
    return 1.0 - NormalDist().cdf(t_value)


def _newey_west_once(values: np.ndarray, lag: int) -> dict[str, float | int]:
    if len(values) < 3:
        raise ValueError("Newey-West requires at least three observations")
    lag = min(max(0, int(lag)), len(values) - 1)
    mean = float(values.mean())
    centered = values - mean
    long_run_variance = float(np.dot(centered, centered) / len(values))
    for offset in range(1, lag + 1):
        covariance = float(
            np.dot(centered[offset:], centered[:-offset]) / len(values)
        )
        long_run_variance += 2.0 * (1.0 - offset / (lag + 1.0)) * covariance
    standard_error = math.sqrt(max(long_run_variance, 1e-18) / len(values))
    t_value = mean / standard_error
    return {
        "alpha": mean,
        "annualizedAlpha": mean * 365.0,
        "hacStandardError": standard_error,
        "hacT": t_value,
        "oneSidedP": _normal_one_sided_p(t_value),
        "lag": lag,
        "sampleCount": len(values),
    }


def newey_west_alpha(
    differential_returns: Sequence[float] | np.ndarray, *, lag: int
) -> dict[str, Any]:
    values = _finite(differential_returns)
    main = _newey_west_once(values, lag)
    half_lag = max(0, int(lag) // 2)
    double_lag = min(len(values) - 1, int(lag) * 2)
    return {
        "schemaVersion": "s01_newey_west_alpha_v1",
        **main,
        "hypothesis": {"null": "alpha_lte_zero", "alternative": "alpha_gt_zero"},
        "lagSensitivity": {
            str(half_lag): _newey_west_once(values, half_lag)["oneSidedP"],
            str(double_lag): _newey_west_once(values, double_lag)["oneSidedP"],
        },
        "missingValuePolicy": "drop_only_explicit_null_pairs",
    }


def _by_adjusted(p_values: Mapping[str, float]) -> dict[str, float]:
    ordered = sorted(p_values.items(), key=lambda item: (item[1], item[0]))
    count = len(ordered)
    harmonic = sum(1.0 / rank for rank in range(1, count + 1))
    adjusted = [1.0] * count
    running = 1.0
    for position in range(count - 1, -1, -1):
        rank = position + 1
        raw = float(ordered[position][1]) * count * harmonic / rank
        running = min(running, raw)
        adjusted[position] = min(1.0, running)
    return {
        item_id: adjusted[position]
        for position, (item_id, _) in enumerate(ordered)
    }


def campaign_fdr(p_values: Mapping[str, float], *, q: float) -> dict[str, Any]:
    values = {str(key): float(value) for key, value in p_values.items()}
    bh = benjamini_hochberg(values, q=q)
    bh_adjusted = {row.itemId: row.adjustedPValue for row in bh.decisions}
    by_adjusted = _by_adjusted(values)
    return {
        "schemaVersion": "s01_campaign_fdr_v1",
        "familySize": len(values),
        "benjaminiHochberg": {
            "q": q,
            "discoveries": bh.discoveries,
            "adjustedPValues": bh_adjusted,
        },
        "benjaminiYekutieli": {
            "q": q,
            "discoveries": sorted(
                key for key, value in by_adjusted.items() if value <= q
            ),
            "adjustedPValues": by_adjusted,
            "sensitivityOnly": True,
        },
    }


def _moments(values: np.ndarray) -> tuple[float, float]:
    centered = values - values.mean()
    standard_deviation = float(values.std(ddof=1))
    if standard_deviation <= 0:
        return 0.0, 3.0
    skewness = float(np.mean((centered / standard_deviation) ** 3))
    kurtosis = float(np.mean((centered / standard_deviation) ** 4))
    return skewness, kurtosis


def deflated_sharpe_report(
    returns: Sequence[float] | np.ndarray,
    *,
    actual_trials: int,
    comparable_trials: int,
    effective_trials: int,
    sharpe_std: float,
) -> dict[str, Any]:
    values = _finite(returns)
    if len(values) < 3:
        raise ValueError("Deflated Sharpe requires at least three observations")
    standard_deviation = float(values.std(ddof=1))
    observed = (
        float(values.mean()) / standard_deviation * math.sqrt(365.0)
        if standard_deviation > 0
        else 0.0
    )
    skewness, kurtosis = _moments(values)
    actual = deflated_sharpe_probability(
        observed_sharpe=observed,
        n_trials=actual_trials,
        observations=len(values),
        sharpe_std=sharpe_std,
        skewness=skewness,
        kurtosis=kurtosis,
        confidence_threshold=0.90,
    )
    effective = deflated_sharpe_probability(
        observed_sharpe=observed,
        n_trials=max(1, effective_trials),
        observations=len(values),
        sharpe_std=sharpe_std,
        skewness=skewness,
        kurtosis=kurtosis,
        confidence_threshold=0.90,
    )
    return {
        "schemaVersion": "s01_deflated_sharpe_v1",
        "observedSharpe": observed,
        "sampleCount": len(values),
        "skewness": skewness,
        "PearsonKurtosis": kurtosis,
        "actualResultReadTrialCount": actual_trials,
        "validComparableTrialCount": comparable_trials,
        "effectiveIndependentTrialCount": effective_trials,
        "expectedMaximumNoiseSharpe": actual.expectedMaximumSharpe,
        "dsrActualTrials": actual.probability,
        "dsrEffectiveTrials": effective.probability,
        "mainGateUses": "actual_result_read_trial_count",
    }


def _sharpe(values: np.ndarray) -> float:
    standard_deviation = float(values.std(ddof=1))
    return float(values.mean()) / standard_deviation if standard_deviation > 0 else 0.0


def probability_of_overfitting(
    panel: pd.DataFrame, *, block_count: int
) -> dict[str, Any]:
    clean = panel.replace([np.inf, -np.inf], np.nan).dropna(how="any")
    if block_count < 4 or block_count % 2:
        raise ValueError("PBO block_count must be even and at least four")
    if len(clean) < block_count:
        raise ValueError("PBO panel is shorter than its block count")
    blocks = [np.asarray(block, dtype="int64") for block in np.array_split(np.arange(len(clean)), block_count)]
    train_scores: list[list[float]] = []
    test_scores: list[list[float]] = []
    half = block_count // 2
    all_indexes = set(range(block_count))
    for selected_blocks in combinations(range(block_count), half):
        if 0 not in selected_blocks:
            continue
        test_blocks = sorted(all_indexes.difference(selected_blocks))
        train_index = np.concatenate([blocks[index] for index in selected_blocks])
        test_index = np.concatenate([blocks[index] for index in test_blocks])
        train_scores.append(
            [_sharpe(clean.iloc[train_index, column].to_numpy()) for column in range(clean.shape[1])]
        )
        test_scores.append(
            [_sharpe(clean.iloc[test_index, column].to_numpy()) for column in range(clean.shape[1])]
        )
    result = probability_of_backtest_overfitting(
        train_scores=train_scores, test_scores=test_scores
    )
    return {
        "schemaVersion": "s01_probability_of_backtest_overfitting_v1",
        "status": "completed",
        "candidateCount": clean.shape[1],
        "sampleCount": len(clean),
        "blockCount": block_count,
        "combinationCount": result.partitionCount,
        "pbo": result.pbo,
        "selectedIndexes": result.selectedIndexes,
        "logitRanks": result.logits,
        "outOfSamplePercentiles": result.outOfSamplePercentiles,
        "continuousTimeBlocks": True,
    }


def _stationary_indices(
    rng: np.random.Generator, sample_count: int, mean_block_length: int
) -> np.ndarray:
    restart_probability = 1.0 / float(mean_block_length)
    indexes = np.empty(sample_count, dtype="int64")
    indexes[0] = int(rng.integers(0, sample_count))
    for position in range(1, sample_count):
        if float(rng.random()) < restart_probability:
            indexes[position] = int(rng.integers(0, sample_count))
        else:
            indexes[position] = (indexes[position - 1] + 1) % sample_count
    return indexes


def stationary_bootstrap_test(
    panel: pd.DataFrame,
    *,
    bootstrap_count: int,
    mean_block_length: int,
    seed: int,
) -> dict[str, Any]:
    clean = panel.replace([np.inf, -np.inf], np.nan).dropna(how="any")
    values = clean.to_numpy(dtype="float64")
    if len(values) < 3 or values.shape[1] < 1:
        raise ValueError("Stationary bootstrap requires a non-empty aligned panel")
    means = values.mean(axis=0)
    standard_deviations = values.std(axis=0, ddof=1)
    observed_white = float(np.sqrt(len(values)) * np.max(means))
    observed_spa = float(
        np.max(
            np.sqrt(len(values))
            * means
            / np.maximum(standard_deviations, 1e-12)
        )
    )
    centered = values - means
    rng = np.random.default_rng(seed)
    white_exceed = 0
    spa_exceed = 0
    for _ in range(int(bootstrap_count)):
        sample = centered[
            _stationary_indices(rng, len(centered), int(mean_block_length))
        ]
        sample_means = sample.mean(axis=0)
        white_statistic = float(np.sqrt(len(sample)) * np.max(sample_means))
        sample_standard_deviations = sample.std(axis=0, ddof=1)
        spa_statistic = float(
            np.max(
                np.sqrt(len(sample))
                * sample_means
                / np.maximum(sample_standard_deviations, 1e-12)
            )
        )
        white_exceed += white_statistic >= observed_white
        spa_exceed += spa_statistic >= observed_spa
    divisor = bootstrap_count + 1
    return {
        "schemaVersion": "s01_stationary_bootstrap_tests_v1",
        "bootstrapCount": bootstrap_count,
        "meanBlockLength": mean_block_length,
        "seed": seed,
        "candidateCount": values.shape[1],
        "sampleCount": len(values),
        "whiteRealityCheck": {
            "observedStatistic": observed_white,
            "pValue": (white_exceed + 1) / divisor,
            "hardGate": False,
        },
        "spa": {
            "observedStatistic": observed_spa,
            "pValue": (spa_exceed + 1) / divisor,
            "hardGate": True,
        },
    }
