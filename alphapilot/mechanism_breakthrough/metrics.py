"""Development-only performance summaries for mechanism prefilters."""

from __future__ import annotations

from collections import Counter
from math import inf
from typing import Any, Iterable, Mapping

import numpy as np
import pandas as pd


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if np.isfinite(number) else None


def summarize_executions(
    rows: Iterable[Mapping[str, Any]],
    *,
    symbol_by_trade: Iterable[str],
) -> dict[str, Any]:
    trades = list(rows)
    symbols = list(symbol_by_trade)
    if len(trades) != len(symbols):
        raise ValueError("symbol_count_must_match_trade_count")

    net_r = np.asarray([float(row.get("netR") or 0.0) for row in trades], dtype=float)
    gross_r = np.asarray([float(row.get("grossR") or 0.0) for row in trades], dtype=float)
    positive = float(net_r[net_r > 0].sum()) if len(net_r) else 0.0
    negative = float(-net_r[net_r < 0].sum()) if len(net_r) else 0.0
    profit_factor = positive / negative if negative > 0 else (inf if positive > 0 else 0.0)
    curve = np.concatenate(([0.0], np.cumsum(net_r)))
    maximum_drawdown = float(np.max(np.maximum.accumulate(curve) - curve))

    month_returns: dict[str, float] = {}
    symbol_returns: dict[str, float] = {}
    for row, symbol in zip(trades, symbols):
        timestamp = row.get("entryTimestamp") or row.get("signalTimestamp")
        month = pd.Timestamp(timestamp).strftime("%Y-%m") if timestamp else "unknown"
        month_returns[month] = month_returns.get(month, 0.0) + float(row.get("netR") or 0.0)
        symbol_returns[symbol] = symbol_returns.get(symbol, 0.0) + float(row.get("netR") or 0.0)

    positive_months = sum(value > 0 for value in month_returns.values())
    positive_total = sum(max(0.0, value) for value in symbol_returns.values())
    symbol_concentration = (
        max((max(0.0, value) for value in symbol_returns.values()), default=0.0)
        / positive_total
        if positive_total > 0
        else 0.0
    )
    positive_month_total = sum(max(0.0, value) for value in month_returns.values())
    month_concentration = (
        max((max(0.0, value) for value in month_returns.values()), default=0.0)
        / positive_month_total
        if positive_month_total > 0
        else 0.0
    )

    return {
        "tradeCount": int(len(trades)),
        "grossTotalR": float(gross_r.sum()) if len(gross_r) else 0.0,
        "totalNetR": float(net_r.sum()) if len(net_r) else 0.0,
        "averageNetR": float(net_r.mean()) if len(net_r) else None,
        "profitFactor": None if profit_factor == inf else float(profit_factor),
        "profitFactorInfinite": bool(profit_factor == inf),
        "maximumDrawdownR": maximum_drawdown,
        "winRate": float((net_r > 0).mean()) if len(net_r) else None,
        "positiveMonthRatio": (
            float(positive_months / len(month_returns)) if month_returns else None
        ),
        "singleInstrumentPositiveContribution": float(symbol_concentration),
        "singleMonthPositiveContribution": float(month_concentration),
        "mfeRMean": (
            float(np.mean([float(row.get("mfeR") or 0.0) for row in trades]))
            if trades
            else None
        ),
        "maeRMean": (
            float(np.mean([float(row.get("maeR") or 0.0) for row in trades]))
            if trades
            else None
        ),
        "symbolCount": len(set(symbols)),
        "monthCount": len(month_returns),
        "perSymbolTradeCount": dict(sorted(Counter(symbols).items())),
    }


def evaluate_prefilter_gates(
    *,
    timeframe: str,
    base: Mapping[str, Any],
    stress: Mapping[str, Any],
    benchmark: Mapping[str, Any],
) -> tuple[dict[str, dict[str, Any]], bool]:
    sample_minimum = {"1h": 150, "4h": 80}[timeframe]
    base_pf = _finite(base.get("profitFactor"))
    if base.get("profitFactorInfinite"):
        base_pf = 999.0
    stress_pf = _finite(stress.get("profitFactor"))
    if stress.get("profitFactorInfinite"):
        stress_pf = 999.0
    benchmark_average = _finite(benchmark.get("averageNetR"))
    candidate_average = _finite(base.get("averageNetR"))
    benchmark_total = _finite(benchmark.get("totalNetR")) or 0.0
    candidate_total = _finite(base.get("totalNetR")) or 0.0
    positive_month_ratio = _finite(base.get("positiveMonthRatio"))

    rows = {
        "sampleGate": {
            "actual": int(base.get("tradeCount") or 0),
            "operator": ">=",
            "required": sample_minimum,
            "passed": int(base.get("tradeCount") or 0) >= sample_minimum,
        },
        "developmentProfitFactor": {
            "actual": base_pf,
            "operator": ">=",
            "required": 1.08,
            "passed": base_pf is not None and base_pf >= 1.08,
        },
        "developmentAverageNetR": {
            "actual": candidate_average,
            "operator": ">=",
            "required": 0.03,
            "passed": candidate_average is not None and candidate_average >= 0.03,
        },
        "positiveDevelopmentMonthRatio": {
            "actual": positive_month_ratio,
            "operator": ">=",
            "required": 0.60,
            "passed": positive_month_ratio is not None and positive_month_ratio >= 0.60,
        },
        "stress1_5xPositive": {
            "actual": stress_pf,
            "operator": ">",
            "required": 1.0,
            "passed": stress_pf is not None and stress_pf > 1.0,
        },
        "mechanismIncrementAverageNetR": {
            "actual": (
                candidate_average - benchmark_average
                if candidate_average is not None and benchmark_average is not None
                else None
            ),
            "operator": ">",
            "required": 0.0,
            "passed": (
                candidate_average is not None
                and benchmark_average is not None
                and candidate_average > benchmark_average
            ),
        },
        "mechanismIncrementTotalNetR": {
            "actual": candidate_total - benchmark_total,
            "operator": ">",
            "required": 0.0,
            "passed": candidate_total > benchmark_total,
        },
    }
    return rows, all(bool(row["passed"]) for row in rows.values())

