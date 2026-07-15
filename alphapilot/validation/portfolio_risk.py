from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

import numpy as np


PORTFOLIO_LIMITS = {
    "maximumCandidateFamilies": 2,
    "maximumAggregateOpenRiskPct": 1.25,
    "maximumSameDirectionClusterRiskPct": 0.75,
    "portfolioResearchStopPct": 12.0,
}


def _month(timestamp_ms: int) -> str:
    return datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc).strftime(
        "%Y-%m"
    )


def analyze_portfolio_risk(
    candidate_trades: Mapping[str, Sequence[dict[str, Any]]],
) -> dict[str, Any]:
    names = sorted(candidate_trades)
    signal_sets = {
        name: {
            (str(row.get("instrumentId") or ""), int(row.get("entryTimestampMs") or 0))
            for row in candidate_trades[name]
        }
        for name in names
    }
    overlap: dict[str, dict[str, float | None]] = {}
    for left in names:
        overlap[left] = {}
        for right in names:
            union = signal_sets[left] | signal_sets[right]
            overlap[left][right] = (
                len(signal_sets[left] & signal_sets[right]) / len(union)
                if union
                else None
            )

    monthly: dict[str, dict[str, float]] = {}
    all_months: set[str] = set()
    for name in names:
        values: dict[str, float] = defaultdict(float)
        for row in candidate_trades[name]:
            values[_month(int(row.get("entryTimestampMs") or 0))] += float(
                row.get("netR") or 0
            )
        monthly[name] = dict(values)
        all_months.update(values)
    ordered_months = sorted(all_months)
    correlation: dict[str, dict[str, float | None]] = {name: {} for name in names}
    for left in names:
        for right in names:
            x = np.asarray([monthly[left].get(month, 0.0) for month in ordered_months])
            y = np.asarray([monthly[right].get(month, 0.0) for month in ordered_months])
            if len(ordered_months) < 2 or x.std() == 0 or y.std() == 0:
                correlation[left][right] = None
            else:
                correlation[left][right] = float(np.corrcoef(x, y)[0, 1])
    positive_by_candidate = {
        name: sum(max(0.0, float(row.get("netR") or 0)) for row in candidate_trades[name])
        for name in names
    }
    positive_total = sum(positive_by_candidate.values())
    return {
        "portfolioLimits": dict(PORTFOLIO_LIMITS),
        "signalOverlapJaccard": overlap,
        "monthlyReturnCorrelation": correlation,
        "positiveContributionShare": {
            name: value / positive_total if positive_total else None
            for name, value in positive_by_candidate.items()
        },
        "btcBeta": None,
        "btcBetaUnavailableReason": (
            "formal trade evidence does not include an independent BTC market return series"
        ),
        "candidateCount": len(names),
    }
