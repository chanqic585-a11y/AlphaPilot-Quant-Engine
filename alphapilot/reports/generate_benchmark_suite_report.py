"""Generate V13.4.23 benchmark suite report.

This reads local Freqtrade backtest artifacts and public local OHLCV only. It
does not enter Dry-run, call exchange private APIs, read accounts, create real
orders, or auto trade.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from alphapilot.benchmarks.benchmark_registry import (
    REJECTED_BENCHMARK_IDEAS,
    get_benchmark_by_class,
    list_benchmark_registry,
)
from alphapilot.benchmarks.buy_hold_baseline import build_buy_hold_btc_baseline, build_no_trade_baseline
from alphapilot.reports.benchmark_suite_report_schema import BenchmarkSuiteReport
from alphapilot.reports.export_backtest_report import _read_freqtrade_result_payload

DEFAULT_MANIFEST = Path("reports/v13_4_23_benchmark_manifest.json")
DEFAULT_OUTPUT_JSON = Path("reports/v13_4_23_benchmark_suite_report.json")
DEFAULT_OUTPUT_SUMMARY = Path("reports/v13_4_23_benchmark_suite_summary.md")
DEFAULT_SLIPPAGE_RATES = [0.0005, 0.001, 0.002]
PRIMARY_SLIPPAGE_RATE = 0.001


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _round(value: Any, digits: int = 4) -> float | None:
    try:
        if value is None:
            return None
        return round(float(value), digits)
    except (TypeError, ValueError):
        return None


def _pct_from_ratio(value: Any) -> float | None:
    number = _round(value, 8)
    if number is None:
        return None
    return _round(number * 100, 4) if -1 <= number <= 1 else _round(number, 4)


def _select_strategy_payload(payload: dict[str, Any] | list[Any], strategy: str) -> dict[str, Any]:
    if isinstance(payload, list):
        return payload[0] if payload and isinstance(payload[0], dict) else {}
    strategies = payload.get("strategy")
    if isinstance(strategies, dict):
        if strategy in strategies and isinstance(strategies[strategy], dict):
            return strategies[strategy]
        for value in strategies.values():
            if isinstance(value, dict):
                return value
    return payload if isinstance(payload, dict) else {}


def _trade_profit_abs(trade: dict[str, Any]) -> float:
    return float(trade.get("profit_abs") or 0.0)


def _trade_profit_ratio(trade: dict[str, Any]) -> float:
    return float(trade.get("profit_ratio") or 0.0)


def _trade_notional(trade: dict[str, Any]) -> tuple[float, bool]:
    orders = trade.get("orders") if isinstance(trade.get("orders"), list) else []
    order_costs = [abs(float(order["cost"])) for order in orders if order.get("cost") is not None]
    if order_costs:
        return sum(order_costs), False
    amount = trade.get("amount")
    open_rate = trade.get("open_rate")
    close_rate = trade.get("close_rate")
    if amount is not None and open_rate is not None and close_rate is not None:
        return abs(float(amount) * (float(open_rate) + float(close_rate))), False
    stake_amount = trade.get("stake_amount")
    leverage = trade.get("leverage") or 1
    if stake_amount is not None:
        return abs(float(stake_amount) * float(leverage) * 2), True
    return 0.0, True


def _sum_fees_from_trades(trades: list[dict[str, Any]]) -> float | None:
    total = 0.0
    found = False
    for trade in trades:
        fee_open = trade.get("fee_open")
        fee_close = trade.get("fee_close")
        for order in trade.get("orders", []) or []:
            cost = order.get("cost")
            if cost is None:
                continue
            fee_rate = fee_open if order.get("ft_is_entry") else fee_close
            if fee_rate is None:
                continue
            total += abs(float(cost)) * float(fee_rate)
            found = True
    return _round(total, 8) if found else None


def _max_consecutive_losses(values: list[float]) -> int | None:
    if not values:
        return None
    streak = 0
    max_streak = 0
    for value in values:
        if value < 0:
            streak += 1
            max_streak = max(max_streak, streak)
        else:
            streak = 0
    return max_streak


def _profit_factor(values: list[float]) -> float | None:
    wins = sum(value for value in values if value > 0)
    losses = abs(sum(value for value in values if value < 0))
    if losses == 0:
        return None
    return _round(wins / losses)


def _win_rate(values: list[float]) -> float | None:
    if not values:
        return None
    return _round(sum(1 for value in values if value > 0) / len(values) * 100)


def _average_holding_minutes(trades: list[dict[str, Any]]) -> float | None:
    seconds = [float(trade["trade_duration"]) * 60 for trade in trades if trade.get("trade_duration") is not None]
    if not seconds:
        seconds = [float(trade["holding_time_s"]) for trade in trades if trade.get("holding_time_s") is not None]
    if not seconds:
        return None
    return _round(sum(seconds) / len(seconds) / 60)


def _monthly_stability(trades: list[dict[str, Any]]) -> dict[str, Any]:
    buckets: dict[str, list[float]] = defaultdict(list)
    for trade in trades:
        close_date = str(trade.get("close_date") or trade.get("close_timestamp") or "")
        month = close_date[:7] if len(close_date) >= 7 else "unknown"
        buckets[month].append(_trade_profit_abs(trade))
    rows = []
    for month, values in sorted(buckets.items()):
        rows.append({"month": month, "tradeCount": len(values), "profitAbs": _round(sum(values), 8)})
    usable = [row for row in rows if row["month"] != "unknown"]
    positive = sum(1 for row in usable if (row["profitAbs"] or 0) > 0)
    return {
        "months": rows,
        "positiveMonthRatio": _round(positive / len(usable)) if usable else None,
        "stable": bool(usable and positive / len(usable) >= 0.55),
    }


def _pair_stability(trades: list[dict[str, Any]]) -> dict[str, Any]:
    buckets: dict[str, list[float]] = defaultdict(list)
    for trade in trades:
        buckets[str(trade.get("pair", "unknown"))].append(_trade_profit_abs(trade))
    rows = []
    for pair, values in sorted(buckets.items()):
        rows.append({"pair": pair, "tradeCount": len(values), "profitAbs": _round(sum(values), 8)})
    usable = [row for row in rows if row["pair"] != "unknown"]
    positive = sum(1 for row in usable if (row["profitAbs"] or 0) > 0)
    return {
        "pairs": rows,
        "positivePairRatio": _round(positive / len(usable)) if usable else None,
        "stable": bool(usable and positive / len(usable) >= 0.55),
    }


def _raw_metrics(source: dict[str, Any], trades: list[dict[str, Any]]) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    total_return = _round(source.get("profit_total_pct"), 4)
    if total_return is None:
        total_return = _pct_from_ratio(source.get("profit_total"))
        if total_return is None:
            warnings.append("profit_total_pct and profit_total unavailable.")
    drawdown = _pct_from_ratio(source.get("max_drawdown_account"))
    fees = _sum_fees_from_trades(trades)
    if fees is None:
        warnings.append("feesPaid unavailable from trade orders.")
    profit_values = [_trade_profit_abs(trade) for trade in trades]
    max_losses = source.get("max_consecutive_losses")
    if max_losses is None:
        max_losses = _max_consecutive_losses(profit_values)
        warnings.append("max_consecutive_losses missing; reconstructed from trades.")
    metrics = {
        "totalReturnPct": total_return,
        "maxDrawdownPct": drawdown,
        "profitFactor": _round(source.get("profit_factor")),
        "winRate": _round((source.get("winrate") or 0) * 100) if source.get("winrate") is not None else _win_rate(profit_values),
        "tradeCount": int(source.get("total_trades") or len(trades)),
        "maxConsecutiveLosses": max_losses,
        "averageHoldingMinutes": _average_holding_minutes(trades),
        "feesPaid": fees,
        "slippageCost": 0.0,
        "monthlyStability": _monthly_stability(trades),
        "pairStability": _pair_stability(trades),
        "slippageAppliedByFreqtrade": False,
    }
    return metrics, warnings


def _apply_slippage(source: dict[str, Any], trades: list[dict[str, Any]], slippage_rate: float) -> dict[str, Any]:
    starting_balance = float(source.get("starting_balance") or source.get("dry_run_wallet") or 0.0) or None
    adjusted_values: list[float] = []
    total_slippage = 0.0
    estimated = False
    for trade in trades:
        notional, is_estimated = _trade_notional(trade)
        estimated = estimated or is_estimated
        slippage_cost = notional * slippage_rate
        total_slippage += slippage_cost
        adjusted_values.append(_trade_profit_abs(trade) - slippage_cost)
    adjusted_abs = sum(adjusted_values)
    raw_ratios = [_trade_profit_ratio(trade) for trade in trades]
    return {
        "slippageRateOneWay": slippage_rate,
        "slippageCostPctRoundTrip": _round(slippage_rate * 2 * 100),
        "slippageAppliedByFreqtrade": False,
        "slippageAppliedByPostProcessing": True,
        "slippageCost": _round(total_slippage, 8),
        "slippageCostEstimated": estimated,
        "slippageAdjustedTotalReturnPct": _round(adjusted_abs / starting_balance * 100) if starting_balance else _round((sum(raw_ratios) - len(trades) * slippage_rate * 2) * 100),
        "slippageAdjustedProfitFactor": _profit_factor(adjusted_values),
        "slippageAdjustedWinRate": _win_rate(adjusted_values),
        "slippageAdjustedMaxConsecutiveLosses": _max_consecutive_losses(adjusted_values),
    }


def _extract_pairs(source: dict[str, Any]) -> list[str]:
    pairs = set()
    for row in source.get("results_per_pair", []) or []:
        pair = row.get("key") or row.get("pair")
        if pair and pair != "TOTAL":
            pairs.add(str(pair))
    for trade in source.get("trades", []) or []:
        pair = trade.get("pair")
        if pair:
            pairs.add(str(pair))
    return sorted(pairs)


def _metrics_from_result(path: Path, strategy: str, slippage_rates: list[float]) -> tuple[dict[str, Any], list[str], list[str]]:
    warnings: list[str] = []
    payload = _read_freqtrade_result_payload(path)
    source = _select_strategy_payload(payload, strategy)
    trades = source.get("trades", []) if isinstance(source.get("trades"), list) else []
    raw, raw_warnings = _raw_metrics(source, trades)
    warnings.extend(raw_warnings)
    slippage = {str(rate): _apply_slippage(source, trades, rate) for rate in slippage_rates}
    primary = slippage[str(PRIMARY_SLIPPAGE_RATE)]
    metrics = {
        **raw,
        "slippageStress": slippage,
        "slippageAdjustedTotalReturnPct": primary["slippageAdjustedTotalReturnPct"],
        "slippageAdjustedProfitFactor": primary["slippageAdjustedProfitFactor"],
        "slippageAdjustedWinRate": primary["slippageAdjustedWinRate"],
        "slippageCost": primary["slippageCost"],
        "sourceResult": str(path),
    }
    for key, value in metrics.items():
        if value is None and key not in {"profitFactor", "slippageAdjustedProfitFactor", "averageHoldingMinutes"}:
            warnings.append(f"{key} unavailable.")
    return metrics, warnings, _extract_pairs(source)


def _rank_best(rows: list[dict[str, Any]], adjusted: bool) -> str | None:
    return_field = "slippageAdjustedTotalReturnPct" if adjusted else "totalReturnPct"
    metric = "slippageAdjustedProfitFactor" if adjusted else "profitFactor"
    trade_rows = [row for row in rows if not row.get("isReportOnly") and row.get("tradeCount", 0) is not None]
    ranked = sorted(
        trade_rows,
        key=lambda row: (
            row.get(return_field) if row.get(return_field) is not None else -999,
            row.get(metric) if row.get(metric) is not None else -999,
            -(row.get("maxDrawdownPct") if row.get("maxDrawdownPct") is not None else 999),
        ),
        reverse=True,
    )
    return ranked[0]["className"] if ranked else None


def _build_benchmark_rows(manifest: dict[str, Any], slippage_rates: list[float]) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    entries = {entry.get("strategy"): entry for entry in manifest.get("strategies", [])}
    warnings: list[str] = []
    seen_pairs: set[str] = set()
    rows: list[dict[str, Any]] = []
    for registry_item in list_benchmark_registry():
        if registry_item["isReportOnly"]:
            continue
        class_name = registry_item["className"]
        entry = entries.get(class_name, {})
        if not entry.get("succeeded") or not entry.get("stableResult"):
            warning = entry.get("error") or "Backtest result unavailable."
            rows.append({**registry_item, "backtestSucceeded": False, "warnings": [warning]})
            warnings.append(f"{class_name}: {warning}")
            continue
        metrics, metric_warnings, pairs = _metrics_from_result(Path(entry["stableResult"]), class_name, slippage_rates)
        seen_pairs.update(pairs)
        rows.append({**registry_item, **metrics, "backtestSucceeded": True, "warnings": metric_warnings})
        warnings.extend(f"{class_name}: {warning}" for warning in metric_warnings)
    return rows, warnings, sorted(seen_pairs)


def _excluded_pairs(requested: list[str], supported: list[str]) -> list[dict[str, str]]:
    supported_set = set(supported)
    return [
        {"pair": pair, "reason": "not present in completed benchmark Freqtrade result"}
        for pair in requested
        if pair not in supported_set
    ]


def build_report(manifest_path: Path, slippage_rates: list[float] | None = None) -> BenchmarkSuiteReport:
    slippage_rates = slippage_rates or DEFAULT_SLIPPAGE_RATES
    manifest = _read_json(manifest_path)
    timerange = str(manifest.get("timerange", "20260101-"))
    timeframe = str(manifest.get("timeframe", "1h"))
    requested_pairs = [str(pair) for pair in manifest.get("pairs", [])]
    no_trade = build_no_trade_baseline()
    buy_hold = build_buy_hold_btc_baseline(timerange=timerange, timeframe=timeframe)
    benchmark_rows, warnings, supported_pairs = _build_benchmark_rows(manifest, slippage_rates)
    excluded_pairs = _excluded_pairs(requested_pairs, supported_pairs)
    if excluded_pairs:
        warnings.append("Some requested pairs were not present in completed benchmark results.")

    best_raw = _rank_best(benchmark_rows, adjusted=False)
    best_adjusted = _rank_best(benchmark_rows, adjusted=True)
    interpretation = [
        "Benchmark profitability does not imply trade readiness.",
        "Benchmarks are comparison references only.",
        "Future complex strategies must beat NoTrade, BuyHoldBTC, and simple benchmark baselines after costs.",
        "No benchmark is approved for Dry-run or live trading.",
        "Martingale and inverse averaging are rejected benchmark ideas.",
    ]
    return BenchmarkSuiteReport(
        reportId="v13_4_23_benchmark_suite",
        timerange=timerange,
        timeframe=timeframe,
        requestedPairs=requested_pairs,
        supportedPairs=supported_pairs,
        excludedPairs=excluded_pairs,
        benchmarks=[no_trade, buy_hold] + benchmark_rows,
        bestBenchmarkRaw=best_raw,
        bestBenchmarkSlippageAdjusted=best_adjusted,
        noTradeBaseline=no_trade,
        buyHoldBtcBaseline=buy_hold,
        rejectedBenchmarkIdeas=REJECTED_BENCHMARK_IDEAS,
        interpretation=interpretation,
        warnings=warnings,
        dryRunApproved=False,
        liveTradingApproved=False,
        generatedAt=_utc_now(),
        slippageRatesOneWay=slippage_rates,
    )


def _write_summary(report: dict[str, Any], path: Path) -> None:
    lines = [
        "# AlphaPilot V13.4.23 Benchmark Strategy Suite Summary",
        "",
        "This is a research-only benchmark comparison. It is not a Dry-run approval and not live trading approval.",
        "",
        "## Scope",
        "",
        f"- timerange: {report['timerange']}",
        f"- timeframe: {report['timeframe']}",
        f"- requestedPairs: {len(report['requestedPairs'])}",
        f"- supportedPairs: {len(report['supportedPairs'])}",
        f"- bestBenchmarkRaw: {report['bestBenchmarkRaw']}",
        f"- bestBenchmarkSlippageAdjusted: {report['bestBenchmarkSlippageAdjusted']}",
        f"- dryRunApproved: {report['dryRunApproved']}",
        f"- liveTradingApproved: {report['liveTradingApproved']}",
        "",
        "## Benchmark Table",
        "",
        "| Benchmark | Type | Return % | Adj Return % | Drawdown % | PF | Adj PF | Trades | Win Rate % |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in report["benchmarks"]:
        lines.append(
            f"| {row.get('name') or row.get('className')} | {row.get('type')} | "
            f"{row.get('totalReturnPct')} | {row.get('slippageAdjustedTotalReturnPct')} | "
            f"{row.get('maxDrawdownPct')} | {row.get('profitFactor')} | "
            f"{row.get('slippageAdjustedProfitFactor')} | {row.get('tradeCount')} | {row.get('winRate')} |"
        )
    lines.extend(["", "## Rejected Benchmark Ideas", ""])
    for item in report["rejectedBenchmarkIdeas"]:
        lines.append(f"- {item['name']}: {item['status']} - {item['reason']}")
    lines.extend(["", "## Interpretation", ""])
    lines.extend(f"- {item}" for item in report["interpretation"])
    lines.extend(["", "## Warnings", ""])
    lines.extend(f"- {item}" for item in report["warnings"]) if report["warnings"] else lines.append("- none")
    lines.extend(
        [
            "",
            "## Safety Boundary",
            "",
            "- no Dry-run",
            "- no live trading",
            "- no real API key",
            "- no Trade API / Withdraw API",
            "- no account or position reads",
            "- no real orders",
            "- no auto trading",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def export_report(manifest: Path, output_json: Path, output_summary: Path, slippage_rates: list[float] | None = None) -> tuple[Path, Path]:
    report = build_report(manifest, slippage_rates).to_dict()
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_summary(report, output_summary)
    return output_json, output_summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate V13.4.23 benchmark suite report.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-summary", type=Path, default=DEFAULT_OUTPUT_SUMMARY)
    parser.add_argument("--slippage-rates", default="0.0005,0.001,0.002")
    args = parser.parse_args()
    rates = [float(part.strip()) for part in args.slippage_rates.split(",") if part.strip()]
    output_json, output_summary = export_report(args.manifest, args.output_json, args.output_summary, rates)
    print(f"Exported benchmark suite report: {output_json}")
    print(f"Exported benchmark suite summary: {output_summary}")


if __name__ == "__main__":
    main()
