"""Generate V13.4.9 Trend Pullback expanded validation reports.

This module reads local Freqtrade backtest artifacts only. It does not enter
Dry-run, call exchange private APIs, read accounts, create orders, or auto
trade. Slippage is applied as AlphaPilot post-processing, not as a Freqtrade
native execution model.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from alphapilot.reports.export_backtest_report import _read_freqtrade_result_payload
from alphapilot.reports.trend_pullback_expanded_schema import TrendPullbackExpandedReport
from alphapilot.universe.top30_usdt_swap import get_top30_usdt_swap_pairs

DEFAULT_MANIFEST = Path("reports/v13_4_9_trend_pullback_expanded_manifest.json")
DEFAULT_OUTPUT_JSON = Path("reports/v13_4_9_trend_pullback_expanded_validation_report.json")
DEFAULT_OUTPUT_SUMMARY = Path("reports/v13_4_9_trend_pullback_expanded_validation_summary.md")
DEFAULT_SLIPPAGE_RATE = 0.0005
REPORT_VERSION = "V13.4.9"
STRATEGY_CLASS = "AlphaPilotTrendPullback1HV01"
STRATEGY_ID = "alpha_trend_pullback_1h_v01"
STRATEGY_NAME = "AlphaPilot Trend Pullback 1H V0.1"


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


def _select_strategy_payload(payload: dict[str, Any] | list[Any]) -> dict[str, Any]:
    if isinstance(payload, list):
        return payload[0] if payload and isinstance(payload[0], dict) else {}
    strategies = payload.get("strategy")
    if isinstance(strategies, dict):
        if STRATEGY_CLASS in strategies and isinstance(strategies[STRATEGY_CLASS], dict):
            return strategies[STRATEGY_CLASS]
        for value in strategies.values():
            if isinstance(value, dict):
                return value
    return payload if isinstance(payload, dict) else {}


def _trade_notional(trade: dict[str, Any]) -> tuple[float | None, bool]:
    orders = trade.get("orders") if isinstance(trade.get("orders"), list) else []
    order_costs = [abs(float(order["cost"])) for order in orders if order.get("cost") is not None]
    if order_costs:
        return sum(order_costs), False

    amount = trade.get("amount")
    open_rate = trade.get("open_rate")
    close_rate = trade.get("close_rate")
    if amount is not None and open_rate is not None and close_rate is not None:
        return abs(float(amount) * float(open_rate)) + abs(float(amount) * float(close_rate)), True
    if trade.get("stake_amount") is not None:
        leverage = float(trade.get("leverage") or 1.0)
        return abs(float(trade["stake_amount"]) * leverage * 2), True
    return None, True


def _trade_month(trade: dict[str, Any]) -> str:
    close_date = str(trade.get("close_date") or trade.get("open_date") or "unknown")
    return close_date[:7] if len(close_date) >= 7 else "unknown"


def _apply_slippage(trades: list[dict[str, Any]], slippage_rate: float) -> tuple[list[dict[str, Any]], list[str]]:
    adjusted: list[dict[str, Any]] = []
    warnings: list[str] = []
    estimated_count = 0
    for trade in sorted(trades, key=lambda item: item.get("close_timestamp") or item.get("close_date") or ""):
        raw_profit_abs = float(trade.get("profit_abs") or 0.0)
        raw_profit_ratio = float(trade.get("profit_ratio") or 0.0)
        notional, estimated = _trade_notional(trade)
        if notional is None:
            slippage_cost = 0.0
            estimated = True
            warnings.append(f"Unable to estimate slippage notional for {trade.get('pair')} {trade.get('close_date')}.")
        else:
            slippage_cost = notional * slippage_rate
        if estimated:
            estimated_count += 1
        adjusted.append(
            {
                "pair": trade.get("pair"),
                "month": _trade_month(trade),
                "rawProfitAbs": raw_profit_abs,
                "rawProfitRatio": raw_profit_ratio,
                "slippageCost": slippage_cost,
                "slippageCostEstimated": estimated,
                "adjustedProfitAbs": raw_profit_abs - slippage_cost,
                "adjustedProfitRatio": raw_profit_ratio - (slippage_rate * 2),
                "tradeDuration": trade.get("trade_duration"),
                "exitReason": trade.get("exit_reason"),
                "closeTimestamp": trade.get("close_timestamp"),
            }
        )
    if estimated_count:
        warnings.append(f"Slippage cost used estimated notional for {estimated_count} trades.")
    return adjusted, warnings


def _profit_factor(values: list[float]) -> float | None:
    wins = sum(value for value in values if value > 0)
    losses = abs(sum(value for value in values if value < 0))
    if losses == 0:
        return None if wins == 0 else 999.0
    return _round(wins / losses, 4)


def _win_rate(values: list[float]) -> float | None:
    if not values:
        return None
    return _round(sum(1 for value in values if value > 0) / len(values) * 100, 4)


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


def _max_drawdown_pct(profits: list[float], starting_balance: float | None) -> float | None:
    if not profits or not starting_balance or starting_balance <= 0:
        return None
    equity = starting_balance
    peak = starting_balance
    max_drawdown = 0.0
    for profit in profits:
        equity += profit
        peak = max(peak, equity)
        if peak > 0:
            max_drawdown = max(max_drawdown, (peak - equity) / peak * 100)
    return _round(max_drawdown, 4)


def _average_holding_minutes(trades: list[dict[str, Any]]) -> float | None:
    durations = [float(trade["trade_duration"]) for trade in trades if trade.get("trade_duration") is not None]
    if not durations:
        return None
    return _round(sum(durations) / len(durations), 4)


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
            total += float(cost) * float(fee_rate)
            found = True
    return _round(total, 8) if found else None


def _extract_pair_performance(source: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for row in source.get("results_per_pair", []) or []:
        pair = row.get("key") or row.get("pair")
        if not pair or pair == "TOTAL":
            continue
        rows.append(
            {
                "pair": pair,
                "tradeCount": row.get("trades"),
                "totalProfit": _round(row.get("profit_total_abs"), 8),
                "totalReturnPct": _round(row.get("profit_total_pct"), 4),
                "profitFactor": _round(row.get("profit_factor"), 4),
                "winRate": _round((row.get("winrate") or 0) * 100, 4) if row.get("winrate") is not None else None,
                "maxDrawdownPct": _pct_from_ratio(row.get("max_drawdown_account")),
            }
        )
    return rows


def _extract_monthly_performance(source: dict[str, Any]) -> list[dict[str, Any]]:
    periodic = source.get("periodic_breakdown")
    if isinstance(periodic, dict) and isinstance(periodic.get("month"), list):
        return list(periodic["month"])
    monthly = source.get("monthly_breakdown", source.get("results_per_month", []))
    return monthly if isinstance(monthly, list) else []


def _slippage_pair_breakdown(adjusted_trades: list[dict[str, Any]], starting_balance: float | None) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for trade in adjusted_trades:
        grouped[str(trade.get("pair") or "unknown")].append(trade)
    rows = []
    for pair, trades in sorted(grouped.items()):
        profits = [float(trade["adjustedProfitAbs"]) for trade in trades]
        total_profit = sum(profits)
        rows.append(
            {
                "pair": pair,
                "tradeCount": len(trades),
                "slippageAdjustedProfitAbs": _round(total_profit, 8),
                "slippageAdjustedReturnPct": _round(total_profit / starting_balance * 100, 4)
                if starting_balance
                else None,
                "slippageAdjustedProfitFactor": _profit_factor(profits),
                "slippageAdjustedWinRate": _win_rate(profits),
                "slippageCost": _round(sum(float(trade["slippageCost"]) for trade in trades), 8),
            }
        )
    return rows


def _slippage_monthly_breakdown(adjusted_trades: list[dict[str, Any]], starting_balance: float | None) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for trade in adjusted_trades:
        grouped[str(trade.get("month") or "unknown")].append(trade)
    rows = []
    for month, trades in sorted(grouped.items()):
        profits = [float(trade["adjustedProfitAbs"]) for trade in trades]
        total_profit = sum(profits)
        rows.append(
            {
                "month": month,
                "tradeCount": len(trades),
                "slippageAdjustedProfitAbs": _round(total_profit, 8),
                "slippageAdjustedReturnPct": _round(total_profit / starting_balance * 100, 4)
                if starting_balance
                else None,
                "slippageAdjustedWinRate": _win_rate(profits),
                "slippageCost": _round(sum(float(trade["slippageCost"]) for trade in trades), 8),
            }
        )
    return rows


def _largest_abs_contribution(rows: list[dict[str, Any]], amount_key: str) -> float | None:
    values = [abs(float(row.get(amount_key) or 0.0)) for row in rows]
    total = sum(values)
    if total <= 0:
        return None
    return _round(max(values) / total * 100, 4)


def _raw_metrics(source: dict[str, Any], trades: list[dict[str, Any]]) -> dict[str, Any]:
    total_return = _round(source.get("profit_total_pct"), 4)
    if total_return is None:
        total_return = _pct_from_ratio(source.get("profit_total"))
    drawdown = _pct_from_ratio(source.get("max_drawdown_account"))
    return {
        "tradeCount": source.get("total_trades"),
        "totalReturnPct": total_return,
        "maxDrawdownPct": drawdown,
        "winRate": _round((source.get("winrate") or 0) * 100, 4) if source.get("winrate") is not None else None,
        "profitFactor": _round(source.get("profit_factor"), 4),
        "maxConsecutiveLosses": source.get("max_consecutive_losses"),
        "averageHoldingMinutes": _average_holding_minutes(trades),
        "feesPaid": _sum_fees_from_trades(trades),
        "slippageCost": None,
        "netReturnAfterCosts": total_return,
        "slippageAppliedByFreqtrade": False,
        "slippageAppliedByPostProcessing": False,
    }


def _adjusted_metrics(source: dict[str, Any], trades: list[dict[str, Any]], adjusted_trades: list[dict[str, Any]], slippage_rate: float) -> dict[str, Any]:
    starting_balance = float(source.get("starting_balance") or source.get("dry_run_wallet") or 0.0) or None
    adjusted_abs = [float(trade["adjustedProfitAbs"]) for trade in adjusted_trades]
    total_adjusted_abs = sum(adjusted_abs)
    return {
        "tradeCount": len(trades),
        "slippageRateOneWay": slippage_rate,
        "roundTripSlippageRate": slippage_rate * 2,
        "slippageAppliedByFreqtrade": False,
        "slippageAppliedByPostProcessing": True,
        "slippageCost": _round(sum(float(trade["slippageCost"]) for trade in adjusted_trades), 8),
        "slippageCostEstimated": any(bool(trade["slippageCostEstimated"]) for trade in adjusted_trades),
        "slippageAdjustedTotalProfitAbs": _round(total_adjusted_abs, 8),
        "slippageAdjustedTotalReturnPct": _round(total_adjusted_abs / starting_balance * 100, 4)
        if starting_balance
        else None,
        "slippageAdjustedProfitFactor": _profit_factor(adjusted_abs),
        "slippageAdjustedWinRate": _win_rate(adjusted_abs),
        "maxDrawdownPct": _max_drawdown_pct(adjusted_abs, starting_balance),
        "maxConsecutiveLosses": _max_consecutive_losses(adjusted_abs),
        "averageHoldingMinutes": _average_holding_minutes(trades),
        "netReturnAfterCosts": _round(total_adjusted_abs / starting_balance * 100, 4) if starting_balance else None,
    }


def _supported_pairs(manifest: dict[str, Any], source: dict[str, Any]) -> tuple[list[str], list[dict[str, Any]]]:
    requested = list(manifest.get("pairs", get_top30_usdt_swap_pairs()))
    seen: set[str] = set()
    for pair in source.get("pairlist", []) or []:
        seen.add(str(pair))
    for row in source.get("results_per_pair", []) or []:
        pair = row.get("key") or row.get("pair")
        if pair and pair != "TOTAL":
            seen.add(str(pair))
    for trade in source.get("trades", []) or []:
        pair = trade.get("pair")
        if pair:
            seen.add(str(pair))
    supported = [pair for pair in requested if pair in seen]
    excluded = [
        {"pair": pair, "reason": "not present in completed Freqtrade result; pair may be unsupported by exchange or absent in validated data"}
        for pair in requested
        if pair not in seen
    ]
    return supported, excluded


def _quality_gate(raw: dict[str, Any], adjusted: dict[str, Any], pair_rows: list[dict[str, Any]], month_rows: list[dict[str, Any]]) -> dict[str, Any]:
    largest_pair = _largest_abs_contribution(pair_rows, "slippageAdjustedProfitAbs")
    largest_month = _largest_abs_contribution(month_rows, "slippageAdjustedProfitAbs")
    checks = {
        "slippageAdjustedTotalReturnPositive": (adjusted.get("slippageAdjustedTotalReturnPct") or 0) > 0,
        "slippageAdjustedProfitFactorAbove115": (adjusted.get("slippageAdjustedProfitFactor") or 0) > 1.15,
        "strictProfitFactorAbove120": (adjusted.get("slippageAdjustedProfitFactor") or 0) >= 1.2,
        "maxDrawdownBelow15": adjusted.get("maxDrawdownPct") is not None and adjusted["maxDrawdownPct"] < 15,
        "maxConsecutiveLossesAtMost6": adjusted.get("maxConsecutiveLosses") is not None and adjusted["maxConsecutiveLosses"] <= 6,
        "tradeCountPresent": (raw.get("tradeCount") or 0) > 0,
        "largestPairNotDominant": largest_pair is None or largest_pair <= 50,
        "largestMonthNotDominant": largest_month is None or largest_month <= 50,
    }
    passed = all(checks.values())
    if passed:
        next_step = "V13.4.10 Stability Diagnosis / Longer Validation"
    elif (adjusted.get("slippageAdjustedTotalReturnPct") or 0) < -5:
        next_step = "V13.4.10 Trend Pullback Redesign Review"
    else:
        next_step = "V13.4.10 Strategy Adjustment Candidate"
    return {
        "passedExpandedGate": passed,
        "dryRunApproved": False,
        "checks": checks,
        "largestPairAbsContributionPct": largest_pair,
        "largestMonthAbsContributionPct": largest_month,
        "reason": "Dry-run remains false even if all research checks pass; longer validation is required.",
        "nextStepRecommendation": next_step,
    }


def build_report(manifest_path: Path, slippage_rate: float = DEFAULT_SLIPPAGE_RATE) -> TrendPullbackExpandedReport:
    manifest = _read_json(manifest_path)
    requested_pairs = list(manifest.get("pairs", get_top30_usdt_swap_pairs()))
    entry = next(
        (item for item in manifest.get("strategies", []) if item.get("strategy") == STRATEGY_CLASS),
        {},
    )
    warnings: list[str] = []
    if not entry.get("succeeded") or not entry.get("stableResult"):
        warnings.append(entry.get("error") or "Expanded backtest did not complete.")
        return TrendPullbackExpandedReport(
            reportId="v13_4_9_trend_pullback_expanded_validation",
            version=REPORT_VERSION,
            strategyId=STRATEGY_ID,
            strategyName=STRATEGY_NAME,
            timeframe=str(manifest.get("timeframe", "1h")),
            timerange=str(manifest.get("timerange", "20260101-")),
            universe="fixed_top30",
            isMock=True,
            dryRunApproved=False,
            requestedPairCount=len(requested_pairs),
            requestedPairs=requested_pairs,
            supportedPairs=[],
            excludedPairs=[{"pair": pair, "reason": "backtest did not complete"} for pair in requested_pairs],
            rawMetrics={},
            slippageAdjustedMetrics={},
            warnings=warnings,
            qualityGate={"passedExpandedGate": False, "dryRunApproved": False},
            nextStepRecommendation="Fix runtime failure before V13.4.9 can be completed.",
            sourceResult=entry.get("stableResult"),
            generatedAt=_utc_now(),
        )

    result_path = Path(entry["stableResult"])
    payload = _read_freqtrade_result_payload(result_path)
    source = _select_strategy_payload(payload)
    trades = source.get("trades", []) if isinstance(source.get("trades"), list) else []
    adjusted_trades, slippage_warnings = _apply_slippage(trades, slippage_rate)
    warnings.extend(slippage_warnings)

    raw = _raw_metrics(source, trades)
    adjusted = _adjusted_metrics(source, trades, adjusted_trades, slippage_rate)
    raw_pair_rows = _extract_pair_performance(source)
    raw_month_rows = _extract_monthly_performance(source)
    starting_balance = float(source.get("starting_balance") or source.get("dry_run_wallet") or 0.0) or None
    adjusted_pair_rows = _slippage_pair_breakdown(adjusted_trades, starting_balance)
    adjusted_month_rows = _slippage_monthly_breakdown(adjusted_trades, starting_balance)
    supported, excluded = _supported_pairs(manifest, source)
    if excluded:
        warnings.append("Some requested Top30 pairs were excluded or absent from completed result coverage.")

    pair_performance = [
        {"pair": row.get("pair"), "raw": row, "slippageAdjusted": next((item for item in adjusted_pair_rows if item["pair"] == row.get("pair")), None)}
        for row in raw_pair_rows
    ]
    for row in adjusted_pair_rows:
        if not any(item.get("pair") == row["pair"] for item in pair_performance):
            pair_performance.append({"pair": row["pair"], "raw": None, "slippageAdjusted": row})

    monthly_performance = [
        {"raw": row} for row in raw_month_rows
    ] + [{"slippageAdjusted": row} for row in adjusted_month_rows]
    gate = _quality_gate(raw, adjusted, adjusted_pair_rows, adjusted_month_rows)
    return TrendPullbackExpandedReport(
        reportId="v13_4_9_trend_pullback_expanded_validation",
        version=REPORT_VERSION,
        strategyId=STRATEGY_ID,
        strategyName=STRATEGY_NAME,
        timeframe=str(manifest.get("timeframe", "1h")),
        timerange=str(manifest.get("timerange", "20260101-")),
        universe="fixed_top30",
        isMock=False,
        dryRunApproved=False,
        requestedPairCount=len(requested_pairs),
        requestedPairs=requested_pairs,
        supportedPairs=supported,
        excludedPairs=excluded,
        rawMetrics=raw,
        slippageAdjustedMetrics=adjusted,
        pairPerformance=pair_performance,
        monthlyPerformance=monthly_performance,
        warnings=warnings,
        qualityGate=gate,
        nextStepRecommendation=str(gate["nextStepRecommendation"]),
        sourceResult=str(result_path),
        generatedAt=_utc_now(),
    )


def _format(value: Any) -> str:
    if value is None:
        return "null"
    return str(value)


def _write_summary(report: dict[str, Any], path: Path) -> None:
    raw = report["rawMetrics"]
    adjusted = report["slippageAdjustedMetrics"]
    gate = report["qualityGate"]
    lines = [
        "# V13.4.9 Trend Pullback Expanded Validation Summary",
        "",
        "## Decision",
        "",
        f"- isMock: {report['isMock']}",
        f"- dryRunApproved: {report['dryRunApproved']}",
        f"- passedExpandedGate: {gate.get('passedExpandedGate')}",
        f"- nextStepRecommendation: {report['nextStepRecommendation']}",
        "",
        "## Scope",
        "",
        f"- Strategy: {report['strategyName']}",
        f"- strategyId: {report['strategyId']}",
        f"- Universe: {report['universe']}",
        f"- Timeframe: {report['timeframe']}",
        f"- Timerange: {report['timerange']}",
        "",
        "## Raw Metrics",
        "",
        f"- tradeCount: {_format(raw.get('tradeCount'))}",
        f"- totalReturnPct: {_format(raw.get('totalReturnPct'))}",
        f"- maxDrawdownPct: {_format(raw.get('maxDrawdownPct'))}",
        f"- winRate: {_format(raw.get('winRate'))}",
        f"- profitFactor: {_format(raw.get('profitFactor'))}",
        f"- maxConsecutiveLosses: {_format(raw.get('maxConsecutiveLosses'))}",
        "",
        "## Slippage-Adjusted Metrics",
        "",
        f"- slippageAdjustedTotalReturnPct: {_format(adjusted.get('slippageAdjustedTotalReturnPct'))}",
        f"- slippageAdjustedProfitFactor: {_format(adjusted.get('slippageAdjustedProfitFactor'))}",
        f"- maxDrawdownPct: {_format(adjusted.get('maxDrawdownPct'))}",
        f"- maxConsecutiveLosses: {_format(adjusted.get('maxConsecutiveLosses'))}",
        f"- slippageCost: {_format(adjusted.get('slippageCost'))}",
        f"- slippageAppliedByFreqtrade: {adjusted.get('slippageAppliedByFreqtrade')}",
        f"- slippageAppliedByPostProcessing: {adjusted.get('slippageAppliedByPostProcessing')}",
        "",
        "## Supported Pairs",
        "",
        ", ".join(report["supportedPairs"]) if report["supportedPairs"] else "None",
        "",
        "## Excluded Pairs",
        "",
    ]
    if report["excludedPairs"]:
        lines.extend(f"- {item['pair']}: {item['reason']}" for item in report["excludedPairs"])
    else:
        lines.append("- None")
    lines.extend(["", "## Quality Gate Checks", ""])
    for key, value in gate.get("checks", {}).items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Warnings", ""])
    if report["warnings"]:
        lines.extend(f"- {item}" for item in report["warnings"])
    else:
        lines.append("- None")
    lines.extend(
        [
            "",
            "## Safety",
            "",
            "V13.4.9 is expanded validation only. It does not approve Dry-run, does not approve live trading, does not use API keys, does not call Trade API or Withdraw API, does not read accounts, does not create orders, and does not auto trade.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def export_report(manifest: Path, output_json: Path, output_summary: Path, slippage_rate: float) -> tuple[Path, Path]:
    report = build_report(manifest, slippage_rate).to_dict()
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_summary(report, output_summary)
    return output_json, output_summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate V13.4.9 Trend Pullback expanded validation report.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-summary", type=Path, default=DEFAULT_OUTPUT_SUMMARY)
    parser.add_argument("--slippage-rate", type=float, default=DEFAULT_SLIPPAGE_RATE)
    args = parser.parse_args()

    output_json, output_summary = export_report(
        args.manifest,
        args.output_json,
        args.output_summary,
        args.slippage_rate,
    )
    print(f"Exported Trend Pullback expanded validation report: {output_json}")
    print(f"Exported Trend Pullback expanded validation summary: {output_summary}")


if __name__ == "__main__":
    main()
