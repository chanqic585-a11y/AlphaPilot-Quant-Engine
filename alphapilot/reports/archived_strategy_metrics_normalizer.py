"""Normalize heterogeneous archived metrics without fabricating missing values."""

from __future__ import annotations

import statistics
from collections import Counter, defaultdict
from typing import Any, Iterable

from alphapilot.reports.archived_strategy_failure_schema_v2 import CORE_METRIC_FIELDS


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _percent(value: Any, *, ratio: bool = False) -> float | None:
    number = _number(value)
    if number is None:
        return None
    return number * 100 if ratio else number


def _mean(values: Iterable[Any]) -> float | None:
    numbers = [number for value in values if (number := _number(value)) is not None]
    return statistics.fmean(numbers) if numbers else None


def _metric_shell(strategy_id: str) -> dict[str, Any]:
    row = {field: None for field in CORE_METRIC_FIELDS}
    row.update(
        {
            "strategyId": strategy_id,
            "averageGrossR": None,
            "longTradeCount": None,
            "shortTradeCount": None,
            "pairCount": None,
            "timeframe": None,
            "bySplit": {},
            "byRegime": {},
            "bySymbol": {},
            "byDirection": {},
            "byMonth": {},
            "byExitReason": {},
            "byEnterTag": {},
            "costStress": {},
            "metricSource": None,
            "missingMetricFields": [],
        }
    )
    return row


def normalize_registry_metrics(record: dict[str, Any]) -> dict[str, Any]:
    source = record.get("metrics") or {}
    row = _metric_shell(str(record.get("strategyId")))
    row.update(
        {
            "tradeCount": source.get("tradeCount"),
            "profitFactor": source.get("profitFactor"),
            "averageNetR": source.get("averageNetR"),
            "averageGrossR": source.get("averageGrossR"),
            "maximumDrawdownR": source.get("maximumDrawdownR"),
            "winRatePct": _percent(source.get("winRate"), ratio=True),
            "totalReturnPct": None,
            "feesPaid": None,
            "fundingFees": None,
            "slippageCost": None,
            "longTradeCount": source.get("longTradeCount"),
            "shortTradeCount": source.get("shortTradeCount"),
            "pairCount": len(source.get("bySymbol") or {}) or None,
            "timeframe": record.get("timeframe"),
            "bySplit": source.get("bySplit") or {},
            "byRegime": source.get("byRegime") or {},
            "bySymbol": source.get("bySymbol") or {},
            "costStress": source.get("costStress") or {},
            "metricSource": "registry_workflow_result",
        }
    )
    row["missingMetricFields"] = [
        field for field in CORE_METRIC_FIELDS if row.get(field) is None
    ]
    return row


def _group_trade_rows(trades: list[dict[str, Any]], field: str) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for trade in trades:
        value = trade.get(field)
        if value is None:
            continue
        if field == "openAt":
            value = str(value)[:7]
        groups[str(value)].append(trade)
    result = {}
    for value, items in sorted(groups.items()):
        profits = [_number(item.get("profitRatio")) for item in items]
        profits = [item for item in profits if item is not None]
        result[value] = {
            "tradeCount": len(items),
            "winCount": sum(item > 0 for item in profits),
            "lossCount": sum(item < 0 for item in profits),
            "averageNetR": _mean(item.get("netRApprox") for item in items),
            "totalProfitRatio": sum(profits) if profits else None,
        }
    return result


def normalize_freqtrade_metrics(
    strategy_id: str,
    timeframe: str | None,
    strategy_result: dict[str, Any],
    trades: list[dict[str, Any]],
) -> dict[str, Any]:
    row = _metric_shell(strategy_id)
    wins = strategy_result.get("wins")
    losses = strategy_result.get("losses")
    trade_count = strategy_result.get("total_trades")
    if trade_count is None:
        trade_count = len(trades)
    fee_values = [
        value for item in trades if (value := _number(item.get("feeCostEstimate"))) is not None
    ]
    funding_values = [
        value for item in trades if (value := _number(item.get("fundingFees"))) is not None
    ]
    long_count = sum(item.get("direction") == "long" for item in trades)
    short_count = sum(item.get("direction") == "short" for item in trades)
    row.update(
        {
            "tradeCount": trade_count,
            "profitFactor": strategy_result.get("profit_factor"),
            "averageNetR": _mean(item.get("netRApprox") for item in trades),
            "averageGrossR": None,
            "maximumDrawdownR": None,
            "maxDrawdownPct": _percent(
                strategy_result.get("max_drawdown_account"), ratio=True
            ),
            "winRatePct": (
                (float(wins) / float(trade_count) * 100)
                if wins is not None and trade_count not in (None, 0)
                else None
            ),
            "totalReturnPct": _percent(strategy_result.get("profit_total"), ratio=True),
            "feesPaid": sum(fee_values) if fee_values else None,
            "fundingFees": sum(funding_values) if funding_values else None,
            "slippageCost": None,
            "longTradeCount": long_count if trades else strategy_result.get("trade_count_long"),
            "shortTradeCount": short_count if trades else strategy_result.get("trade_count_short"),
            "pairCount": len({item.get("pair") for item in trades if item.get("pair")})
            or len(strategy_result.get("pairlist") or [])
            or None,
            "timeframe": timeframe or strategy_result.get("timeframe"),
            "bySymbol": _group_trade_rows(trades, "pair"),
            "byDirection": _group_trade_rows(trades, "direction"),
            "byMonth": _group_trade_rows(trades, "openAt"),
            "byExitReason": _group_trade_rows(trades, "exitReason"),
            "byEnterTag": _group_trade_rows(trades, "enterTag"),
            "costStress": {},
            "metricSource": "freqtrade_primary_artifact",
            "winCount": wins,
            "lossCount": losses,
            "expectancy": strategy_result.get("expectancy"),
            "sharpe": strategy_result.get("sharpe"),
            "sortino": strategy_result.get("sortino"),
            "calmar": strategy_result.get("calmar"),
            "cagrPct": _percent(strategy_result.get("cagr"), ratio=True),
            "tradesPerDay": strategy_result.get("trades_per_day"),
            "rejectedSignals": strategy_result.get("rejected_signals"),
        }
    )
    row["missingMetricFields"] = [
        field for field in CORE_METRIC_FIELDS if row.get(field) is None
    ]
    return row


def merge_metric_rows(strategy_id: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        empty = _metric_shell(strategy_id)
        empty["missingMetricFields"] = list(CORE_METRIC_FIELDS)
        return empty
    if len(rows) == 1:
        return rows[0]
    primary = max(rows, key=lambda row: int(row.get("tradeCount") or 0)).copy()
    primary["artifactMetrics"] = rows
    primary["metricSource"] = "freqtrade_primary_artifacts_by_timeframe"
    return primary
