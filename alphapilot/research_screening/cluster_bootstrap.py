"""Deterministic cluster bootstrap for event-strategy uncertainty."""

from __future__ import annotations

import random
from collections import defaultdict
from typing import Any, Mapping, Sequence


def _metrics(values: Sequence[float]) -> dict[str, float]:
    wins = sum(value for value in values if value > 0)
    losses = abs(sum(value for value in values if value < 0))
    cumulative = 0.0
    peak = 0.0
    drawdown = 0.0
    for value in values:
        cumulative += value
        peak = max(peak, cumulative)
        drawdown = max(drawdown, peak - cumulative)
    return {
        "profitFactor": wins / losses if losses else (999.0 if wins else 0.0),
        "averageNetR": sum(values) / len(values) if values else 0.0,
        "totalNetR": sum(values),
        "maximumDrawdownR": drawdown,
    }


def _quantile(values: Sequence[float], probability: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    position = (len(ordered) - 1) * probability
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def cluster_bootstrap_event_metrics(
    events: Sequence[Mapping[str, Any]],
    *,
    cluster_field: str,
    draws: int = 5_000,
    seed: int,
) -> dict[str, Any]:
    if draws <= 0:
        raise ValueError("draws must be positive")
    clusters: dict[str, list[float]] = defaultdict(list)
    for row in events:
        clusters[str(row.get(cluster_field) or "unknown")].append(float(row.get("netR") or 0.0))
    identities = sorted(clusters)
    if not identities:
        raise ValueError("at least one cluster is required")
    rng = random.Random(seed)
    samples: dict[str, list[float]] = {key: [] for key in _metrics([])}
    for _ in range(draws):
        selected = [rng.choice(identities) for _ in identities]
        values = [value for identity in selected for value in clusters[identity]]
        for key, value in _metrics(values).items():
            samples[key].append(value)
    intervals: dict[str, dict[str, list[float]]] = {}
    for key, values in samples.items():
        intervals[key] = {
            "80": [_quantile(values, 0.10), _quantile(values, 0.90)],
            "90": [_quantile(values, 0.05), _quantile(values, 0.95)],
            "95": [_quantile(values, 0.025), _quantile(values, 0.975)],
        }
    return {
        "schemaVersion": "cluster_bootstrap_event_v2",
        "drawCount": draws,
        "seed": seed,
        "clusterField": cluster_field,
        "clusterCount": len(identities),
        "confidenceIntervals": intervals,
        "formalLowerBounds": {
            "profitFactorLower90": intervals["profitFactor"]["90"][0],
            "averageNetRLower90": intervals["averageNetR"]["90"][0],
        },
    }
