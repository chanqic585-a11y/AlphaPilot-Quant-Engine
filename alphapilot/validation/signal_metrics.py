from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime, timezone
from statistics import median
from typing import Any, Iterable, Sequence

import numpy as np


def _number(row: dict[str, Any], key: str) -> float:
    value = row.get(key)
    return float(value) if value is not None else 0.0


def _profit_factor(values: Sequence[float]) -> float | None:
    positive = sum(value for value in values if value > 0)
    negative = abs(sum(value for value in values if value < 0))
    if negative == 0:
        return None if positive == 0 else math.inf
    return positive / negative


def _month(timestamp_ms: int | float | None) -> str:
    if timestamp_ms is None:
        return "unknown"
    return datetime.fromtimestamp(float(timestamp_ms) / 1000, tz=timezone.utc).strftime(
        "%Y-%m"
    )


def _maximum_consecutive_losses(values: Sequence[float]) -> int:
    maximum = current = 0
    for value in values:
        current = current + 1 if value < 0 else 0
        maximum = max(maximum, current)
    return maximum


def _basic_summary(trades: Sequence[dict[str, Any]]) -> dict[str, Any]:
    values = [_number(row, "netR") for row in trades]
    wins = [value for value in values if value > 0]
    losses = [value for value in values if value < 0]
    profit_factor = _profit_factor(values)
    return {
        "tradeCount": len(values),
        "winRate": sum(value > 0 for value in values) / len(values) if values else None,
        "profitFactor": profit_factor if profit_factor != math.inf else None,
        "profitFactorUnbounded": profit_factor == math.inf,
        "averageNetR": sum(values) / len(values) if values else None,
        "medianNetR": median(values) if values else None,
        "averageWinR": sum(wins) / len(wins) if wins else None,
        "averageLossR": sum(losses) / len(losses) if losses else None,
        "totalNetR": sum(values),
        "maximumConsecutiveLosses": _maximum_consecutive_losses(values),
    }


def _breakdown(
    trades: Sequence[dict[str, Any]], key: str, *, month: bool = False
) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in trades:
        value = _month(row.get(key)) if month else str(row.get(key) or "unknown")
        groups[value].append(row)
    return {name: _basic_summary(groups[name]) for name in sorted(groups)}


def summarize_trades(trades: Iterable[dict[str, Any]]) -> dict[str, Any]:
    ordered = sorted(
        (dict(row) for row in trades),
        key=lambda row: (int(row.get("entryTimestampMs") or 0), str(row.get("instrumentId") or "")),
    )
    summary = _basic_summary(ordered)
    mfe = [_number(row, "mfeR") for row in ordered]
    mae = [_number(row, "maeR") for row in ordered]
    summary.update(
        {
            "expectancyR": summary["averageNetR"],
            "averageMfeR": sum(mfe) / len(mfe) if mfe else None,
            "averageMaeR": sum(mae) / len(mae) if mae else None,
            "mfeMaeRatio": (
                (sum(mfe) / len(mfe)) / abs(sum(mae) / len(mae))
                if mfe and mae and sum(mae) != 0
                else None
            ),
            "touchRates": {
                "plusOneR": sum(value >= 1 for value in mfe) / len(mfe) if mfe else None,
                "plusTwoR": sum(value >= 2 for value in mfe) / len(mfe) if mfe else None,
                "minusOneR": sum(value <= -1 for value in mae) / len(mae) if mae else None,
            },
            "firstHitRates": {
                "plusOneRFirst": None,
                "plusTwoRFirst": None,
                "minusOneRFirst": None,
                "unavailableReason": "trade evidence has extrema but no intratrade path order",
            },
            "durationDays": (
                (max(int(row.get("exitTimestampMs") or 0) for row in ordered)
                 - min(int(row.get("entryTimestampMs") or 0) for row in ordered))
                / 86_400_000
                if ordered
                else None
            ),
            "breakdowns": {
                "instrument": _breakdown(ordered, "instrumentId"),
                "month": _breakdown(ordered, "entryTimestampMs", month=True),
                "regime": _breakdown(ordered, "regime"),
                "direction": _breakdown(ordered, "direction"),
                "setup": _breakdown(ordered, "setupName"),
                "exitReason": _breakdown(ordered, "exitReason"),
                "split": _breakdown(ordered, "split"),
                "walkForwardFold": _breakdown(ordered, "fold"),
            },
        }
    )
    return summary


def _finite_quantile(values: np.ndarray, quantile: float) -> float | None:
    value = float(np.quantile(values, quantile))
    return value if math.isfinite(value) else None


def block_bootstrap_metrics(
    trades: Iterable[dict[str, Any]], *, draws: int, seed: int
) -> dict[str, Any]:
    ordered = sorted(
        (dict(row) for row in trades),
        key=lambda row: int(row.get("entryTimestampMs") or 0),
    )
    grouped: dict[str, list[float]] = defaultdict(list)
    for row in ordered:
        grouped[_month(row.get("entryTimestampMs"))].append(_number(row, "netR"))
    blocks = [np.asarray(grouped[key], dtype=float) for key in sorted(grouped)]
    if not blocks:
        return {
            "draws": draws,
            "seed": seed,
            "blockUnit": "calendar_month",
            "averageNetRIntervals": {"80": None, "90": None, "95": None},
            "profitFactorIntervals": {"80": None, "90": None, "95": None},
            "probabilityAverageNetRPositive": None,
            "probabilityProfitFactorAboveOne": None,
        }
    rng = np.random.default_rng(seed)
    average_values = np.empty(draws, dtype=float)
    profit_factors = np.empty(draws, dtype=float)
    for index in range(draws):
        selected = rng.integers(0, len(blocks), size=len(blocks))
        sample = np.concatenate([blocks[item] for item in selected])
        average_values[index] = float(sample.mean())
        positive = float(sample[sample > 0].sum())
        negative = abs(float(sample[sample < 0].sum()))
        profit_factors[index] = positive / negative if negative else math.inf

    def intervals(values: np.ndarray) -> dict[str, list[float | None]]:
        finite = values[np.isfinite(values)]
        if finite.size == 0:
            return {str(confidence): [None, None] for confidence in (80, 90, 95)}
        return {
            str(confidence): [
                _finite_quantile(finite, (1 - confidence / 100) / 2),
                _finite_quantile(finite, 1 - (1 - confidence / 100) / 2),
            ]
            for confidence in (80, 90, 95)
        }

    return {
        "draws": draws,
        "seed": seed,
        "blockUnit": "calendar_month",
        "averageNetRIntervals": intervals(average_values),
        "profitFactorIntervals": intervals(profit_factors),
        "probabilityAverageNetRPositive": float((average_values > 0).mean()),
        "probabilityProfitFactorAboveOne": float((profit_factors > 1).mean()),
    }
