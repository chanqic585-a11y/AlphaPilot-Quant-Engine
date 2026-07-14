"""Transparent factor-guard search across development validation segments."""

from __future__ import annotations

from collections import Counter
from itertools import combinations
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd


FACTOR_COLUMNS = (
    "aligned_return",
    "aligned_slope20",
    "aligned_trend20_50",
    "aligned_trend50_200",
    "btc_aligned",
    "btc_trend20_50",
    "btc_trend50_200",
    "btc_slope20_12",
    "atr_pct",
)
_REQUIRED_SEGMENTS = (
    "derivationTrain",
    "derivationValidation",
    "symbolHoldback",
)
_MINIMUM_TRADES = {
    "derivationTrain": 30,
    "derivationValidation": 20,
    "symbolHoldback": 20,
}


def _metrics(frame: pd.DataFrame) -> dict[str, Any]:
    values = pd.to_numeric(frame.get("netR"), errors="coerce").dropna().to_numpy()
    positives = values[values > 0]
    negatives = values[values < 0]
    profit_factor = (
        float(positives.sum() / abs(negatives.sum()))
        if negatives.size
        else (999.0 if positives.size else 0.0)
    )
    pair_counts = Counter(str(value) for value in frame.get("pair", []))
    return {
        "tradeCount": int(values.size),
        "expectancyR": round(float(values.mean()), 8) if values.size else 0.0,
        "profitFactor": round(profit_factor, 8),
        "largestPairShare": (
            round(max(pair_counts.values()) / values.size, 8)
            if values.size and pair_counts
            else 0.0
        ),
    }


def _apply_guards(frame: pd.DataFrame, guards: Mapping[str, float]) -> pd.DataFrame:
    mask = pd.Series(True, index=frame.index)
    for key, value in guards.items():
        if key.endswith("_min"):
            feature = key.removesuffix("_min")
            mask &= pd.to_numeric(frame[feature], errors="coerce") >= float(value)
        elif key.endswith("_max"):
            feature = key.removesuffix("_max")
            mask &= pd.to_numeric(frame[feature], errors="coerce") <= float(value)
        else:
            raise ValueError(f"factor_guard_key_invalid:{key}")
    return frame.loc[mask.fillna(False)]


def _eligible(metrics: Mapping[str, Mapping[str, Any]]) -> bool:
    for segment in _REQUIRED_SEGMENTS:
        values = metrics[segment]
        if int(values["tradeCount"]) < _MINIMUM_TRADES[segment]:
            return False
        if float(values["expectancyR"]) <= 0:
            return False
        if float(values["profitFactor"]) <= 1.0:
            return False
        if float(values["largestPairShare"]) > 0.6:
            return False
    return True


def _score(metrics: Mapping[str, Mapping[str, Any]]) -> tuple[float, float, int]:
    values = [metrics[segment] for segment in _REQUIRED_SEGMENTS]
    return (
        min(float(item["expectancyR"]) for item in values),
        min(float(item["profitFactor"]) for item in values),
        sum(int(item["tradeCount"]) for item in values),
    )


def _guard_options(train: pd.DataFrame) -> tuple[dict[str, float], ...]:
    options: list[dict[str, float]] = []
    for feature in FACTOR_COLUMNS:
        if feature not in train.columns:
            continue
        values = pd.to_numeric(train[feature], errors="coerce").dropna()
        if values.nunique() < 4:
            continue
        for quantile in (0.2, 0.35, 0.5, 0.65, 0.8):
            threshold = float(values.quantile(quantile))
            options.append({f"{feature}_min": threshold})
            options.append({f"{feature}_max": threshold})
    unique: dict[tuple[tuple[str, float], ...], dict[str, float]] = {}
    for option in options:
        key = tuple(sorted((name, round(value, 12)) for name, value in option.items()))
        unique[key] = option
    return tuple(unique.values())


def discover_robust_factor_guards(
    rows_by_segment: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    max_results: int = 10,
) -> tuple[dict[str, Any], ...]:
    missing = [name for name in _REQUIRED_SEGMENTS if name not in rows_by_segment]
    if missing:
        raise ValueError(f"factor_search_segments_missing:{','.join(missing)}")
    frames = {
        name: pd.DataFrame(list(rows_by_segment[name])) for name in _REQUIRED_SEGMENTS
    }
    train = frames["derivationTrain"]
    if train.empty:
        return ()

    single_options = _guard_options(train)
    train_ranked: list[tuple[tuple[float, float, int], dict[str, float]]] = []
    for guards in single_options:
        metrics = _metrics(_apply_guards(train, guards))
        if (
            metrics["tradeCount"] >= _MINIMUM_TRADES["derivationTrain"]
            and metrics["expectancyR"] > 0
            and metrics["profitFactor"] > 1
        ):
            train_ranked.append(
                (
                    (
                        float(metrics["expectancyR"]),
                        float(metrics["profitFactor"]),
                        int(metrics["tradeCount"]),
                    ),
                    guards,
                )
            )
    train_ranked.sort(reverse=True, key=lambda item: item[0])
    strongest = [guards for _, guards in train_ranked[:20]]
    guard_sets = list(strongest)
    for left, right in combinations(strongest, 2):
        merged = {**left, **right}
        if len(merged) != 2:
            continue
        guard_sets.append(merged)

    results: list[dict[str, Any]] = []
    seen: set[tuple[tuple[str, float], ...]] = set()
    for guards in guard_sets:
        identity = tuple(
            sorted((name, round(float(value), 12)) for name, value in guards.items())
        )
        if identity in seen:
            continue
        seen.add(identity)
        segment_metrics = {
            name: _metrics(_apply_guards(frame, guards))
            for name, frame in frames.items()
        }
        if not _eligible(segment_metrics):
            continue
        score = _score(segment_metrics)
        results.append(
            {
                "factorGuards": {
                    name: round(float(value), 12) for name, value in guards.items()
                },
                "segmentMetrics": segment_metrics,
                "eligible": True,
                "score": [round(score[0], 8), round(score[1], 8), score[2]],
            }
        )
    results.sort(
        key=lambda item: tuple(item["score"]),
        reverse=True,
    )
    return tuple(results[:max_results])
