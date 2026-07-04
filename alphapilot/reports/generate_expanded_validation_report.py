"""Generate V13.4.5 expanded validation reports.

This module reads local Freqtrade backtest artifacts only. It does not enter
Dry-run, call exchange APIs, read accounts, create orders, or auto trade.
Slippage is applied as post-processing metrics, not as a Freqtrade-native model.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from alphapilot.reports.expanded_validation_schema import (
    ExpandedValidationReport,
    ExpandedValidationResult,
)
from alphapilot.reports.export_backtest_report import _read_freqtrade_result_payload

DEFAULT_MANIFEST = Path("reports/v13_4_5_expanded_validation_manifest.json")
DEFAULT_OUTPUT_JSON = Path("reports/v13_4_5_expanded_validation_report.json")
DEFAULT_OUTPUT_SUMMARY = Path("reports/v13_4_5_expanded_validation_summary.md")
BASELINE_STRATEGY = "AlphaPilotVolumeReboundV01"
DEFAULT_SLIPPAGE_RATE = 0.0005


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


def _select_strategy_payload(payload: dict[str, Any], strategy: str) -> dict[str, Any]:
    strategies = payload.get("strategy")
    if isinstance(strategies, dict):
        if strategy in strategies and isinstance(strategies[strategy], dict):
            return strategies[strategy]
        for value in strategies.values():
            if isinstance(value, dict):
                return value
    return payload if isinstance(payload, dict) else {}


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
            warnings.append(f"Unable to estimate slippage notional for trade {trade.get('pair')} {trade.get('close_date')}.")
        else:
            slippage_cost = notional * slippage_rate
        if estimated:
            estimated_count += 1
        adjusted_profit_abs = raw_profit_abs - slippage_cost
        adjusted_profit_ratio = raw_profit_ratio - (slippage_rate * 2)
        adjusted.append(
            {
                "pair": trade.get("pair"),
                "month": _trade_month(trade),
                "rawProfitAbs": raw_profit_abs,
                "rawProfitRatio": raw_profit_ratio,
                "slippageCost": slippage_cost,
                "slippageCostEstimated": estimated,
                "adjustedProfitAbs": adjusted_profit_abs,
                "adjustedProfitRatio": adjusted_profit_ratio,
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
    wins = sum(1 for value in values if value > 0)
    return _round(wins / len(values) * 100, 4)


def _average_holding_minutes(trades: list[dict[str, Any]]) -> float | None:
    durations = [float(trade["trade_duration"]) for trade in trades if trade.get("trade_duration") is not None]
    if not durations:
        return None
    return _round(sum(durations) / len(durations), 4)


def _extract_pair_performance(source: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for row in source.get("results_per_pair", []) or []:
        if row.get("key") == "TOTAL":
            continue
        rows.append(
            {
                "pair": row.get("key"),
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
    return []


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


def _largest_pair_dominance(pair_rows: list[dict[str, Any]]) -> float | None:
    values = [abs(float(row.get("slippageAdjustedProfitAbs") or 0.0)) for row in pair_rows]
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
        "totalReturnPct": total_return,
        "maxDrawdownPct": drawdown,
        "profitFactor": _round(source.get("profit_factor"), 4),
        "tradeCount": source.get("total_trades"),
        "winRate": _round((source.get("winrate") or 0) * 100, 4) if source.get("winrate") is not None else None,
        "maxConsecutiveLosses": source.get("max_consecutive_losses"),
        "averageHoldingMinutes": _average_holding_minutes(trades),
        "feesPaid": _sum_fees_from_trades(trades),
        "netReturnAfterCosts": total_return,
        "slippageAppliedByFreqtrade": False,
        "slippageAppliedByPostProcessing": False,
    }


def _adjusted_metrics(
    source: dict[str, Any],
    trades: list[dict[str, Any]],
    adjusted_trades: list[dict[str, Any]],
    slippage_rate: float,
) -> dict[str, Any]:
    starting_balance = float(source.get("starting_balance") or source.get("dry_run_wallet") or 0.0) or None
    adjusted_abs = [float(trade["adjustedProfitAbs"]) for trade in adjusted_trades]
    adjusted_ratios = [float(trade["adjustedProfitRatio"]) for trade in adjusted_trades]
    total_adjusted_abs = sum(adjusted_abs)
    pair_rows = _slippage_pair_breakdown(adjusted_trades, starting_balance)
    return {
        "slippageRateOneWay": slippage_rate,
        "slippageCostPctRoundTrip": _round(slippage_rate * 2 * 100, 4),
        "slippageAppliedByFreqtrade": False,
        "slippageAppliedByPostProcessing": True,
        "totalSlippageCost": _round(sum(float(trade["slippageCost"]) for trade in adjusted_trades), 8),
        "slippageCostEstimated": any(bool(trade["slippageCostEstimated"]) for trade in adjusted_trades),
        "slippageAdjustedTotalProfitAbs": _round(total_adjusted_abs, 8),
        "slippageAdjustedTotalReturnPct": _round(total_adjusted_abs / starting_balance * 100, 4)
        if starting_balance
        else _round(sum(adjusted_ratios) * 100, 4),
        "slippageAdjustedProfitFactor": _profit_factor(adjusted_abs),
        "slippageAdjustedWinRate": _win_rate(adjusted_abs),
        "tradeCount": len(trades),
        "maxDrawdownPct": _max_drawdown_pct(adjusted_abs, starting_balance),
        "maxConsecutiveLosses": _max_consecutive_losses(adjusted_abs),
        "averageHoldingMinutes": _average_holding_minutes(trades),
        "largestPairAbsContributionPct": _largest_pair_dominance(pair_rows),
    }


def _metrics_from_result(path: Path, strategy: str, slippage_rate: float) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    payload = _read_freqtrade_result_payload(path)
    source = _select_strategy_payload(payload, strategy) if isinstance(payload, dict) else {}
    trades = source.get("trades", []) if isinstance(source.get("trades"), list) else []
    adjusted_trades, slippage_warnings = _apply_slippage(trades, slippage_rate)
    warnings.extend(slippage_warnings)
    raw = _raw_metrics(source, trades)
    adjusted = _adjusted_metrics(source, trades, adjusted_trades, slippage_rate)
    pair_rows = _extract_pair_performance(source)
    monthly_rows = _extract_monthly_performance(source)
    adjusted_pair_rows = _slippage_pair_breakdown(adjusted_trades, float(source.get("starting_balance") or 0.0) or None)
    adjusted_month_rows = _slippage_monthly_breakdown(adjusted_trades, float(source.get("starting_balance") or 0.0) or None)
    return (
        raw,
        adjusted,
        [{"raw": row} for row in pair_rows] + [{"slippageAdjusted": row} for row in adjusted_pair_rows],
        [{"raw": row} for row in monthly_rows] + [{"slippageAdjusted": row} for row in adjusted_month_rows],
        warnings,
    )


def _delta(candidate: dict[str, Any], baseline: dict[str, Any], fields: list[str]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for field in fields:
        cand = candidate.get(field)
        base = baseline.get(field)
        result[field] = _round(cand - base, 4) if isinstance(cand, (int, float)) and isinstance(base, (int, float)) else None
    return result


def _passes_gate(candidate: dict[str, Any], baseline: dict[str, Any]) -> bool:
    if not candidate.get("tradeCount") or candidate.get("tradeCount", 0) < 50:
        return False
    dominance = candidate.get("largestPairAbsContributionPct")
    if isinstance(dominance, (int, float)) and dominance > 50:
        return False
    checks = [
        candidate.get("slippageAdjustedTotalReturnPct") is not None
        and baseline.get("slippageAdjustedTotalReturnPct") is not None
        and candidate["slippageAdjustedTotalReturnPct"] > baseline["slippageAdjustedTotalReturnPct"],
        candidate.get("slippageAdjustedProfitFactor") is not None
        and baseline.get("slippageAdjustedProfitFactor") is not None
        and candidate["slippageAdjustedProfitFactor"] > baseline["slippageAdjustedProfitFactor"],
        candidate.get("maxDrawdownPct") is not None
        and baseline.get("maxDrawdownPct") is not None
        and candidate["maxDrawdownPct"] < baseline["maxDrawdownPct"],
        candidate.get("maxConsecutiveLosses") is not None
        and baseline.get("maxConsecutiveLosses") is not None
        and candidate["maxConsecutiveLosses"] <= baseline["maxConsecutiveLosses"],
    ]
    return all(checks)


def _comparison_row(strategy: str, metrics: dict[str, Any], adjusted: bool, passed: bool | None = None) -> dict[str, Any]:
    if adjusted:
        return {
            "strategy": strategy,
            "slippageAdjustedTotalReturnPct": metrics.get("slippageAdjustedTotalReturnPct"),
            "maxDrawdownPct": metrics.get("maxDrawdownPct"),
            "slippageAdjustedProfitFactor": metrics.get("slippageAdjustedProfitFactor"),
            "tradeCount": metrics.get("tradeCount"),
            "slippageAdjustedWinRate": metrics.get("slippageAdjustedWinRate"),
            "maxConsecutiveLosses": metrics.get("maxConsecutiveLosses"),
            "totalSlippageCost": metrics.get("totalSlippageCost"),
            "largestPairAbsContributionPct": metrics.get("largestPairAbsContributionPct"),
            "passedExpandedGate": passed,
        }
    return {
        "strategy": strategy,
        "totalReturnPct": metrics.get("totalReturnPct"),
        "maxDrawdownPct": metrics.get("maxDrawdownPct"),
        "profitFactor": metrics.get("profitFactor"),
        "tradeCount": metrics.get("tradeCount"),
        "winRate": metrics.get("winRate"),
        "maxConsecutiveLosses": metrics.get("maxConsecutiveLosses"),
        "feesPaid": metrics.get("feesPaid"),
    }


def _rank_raw(rows: list[dict[str, Any]]) -> str | None:
    candidates = [row for row in rows if row.get("strategy") != BASELINE_STRATEGY]
    ranked = sorted(
        candidates,
        key=lambda row: (
            row.get("profitFactor") if row.get("profitFactor") is not None else -999,
            row.get("totalReturnPct") if row.get("totalReturnPct") is not None else -999,
            -(row.get("maxDrawdownPct") if row.get("maxDrawdownPct") is not None else 999),
        ),
        reverse=True,
    )
    return ranked[0]["strategy"] if ranked else None


def _rank_adjusted(rows: list[dict[str, Any]]) -> str | None:
    candidates = [row for row in rows if row.get("strategy") != BASELINE_STRATEGY]
    ranked = sorted(
        candidates,
        key=lambda row: (
            bool(row.get("passedExpandedGate")),
            row.get("slippageAdjustedProfitFactor")
            if row.get("slippageAdjustedProfitFactor") is not None
            else -999,
            row.get("slippageAdjustedTotalReturnPct")
            if row.get("slippageAdjustedTotalReturnPct") is not None
            else -999,
            -(row.get("maxDrawdownPct") if row.get("maxDrawdownPct") is not None else 999),
        ),
        reverse=True,
    )
    return ranked[0]["strategy"] if ranked else None


def _supported_pairs(manifest: dict[str, Any], result_sources: list[Path]) -> tuple[list[str], list[dict[str, Any]]]:
    requested = list(manifest.get("pairs", []))
    seen: set[str] = set()
    for path in result_sources:
        try:
            payload = _read_freqtrade_result_payload(path)
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        strategies = payload.get("strategy")
        source = next(iter(strategies.values())) if isinstance(strategies, dict) and strategies else payload
        if not isinstance(source, dict):
            continue
        for pair in source.get("pairlist", []) or []:
            seen.add(str(pair))
        for row in source.get("results_per_pair", []) or []:
            pair = row.get("key")
            if pair and pair != "TOTAL":
                seen.add(str(pair))
    supported = [pair for pair in requested if pair in seen] if requested else sorted(seen)
    excluded = [
        {"pair": pair, "reason": "not present in completed Freqtrade backtest result"}
        for pair in requested
        if pair not in seen
    ]
    return supported, excluded


def build_report(manifest_path: Path, slippage_rate: float = DEFAULT_SLIPPAGE_RATE) -> ExpandedValidationReport:
    manifest = _read_json(manifest_path)
    entries = {entry.get("strategy"): entry for entry in manifest.get("strategies", [])}
    warnings: list[str] = []
    baseline_raw: dict[str, Any] = {}
    baseline_adjusted: dict[str, Any] = {}
    results: list[ExpandedValidationResult] = []
    raw_table: list[dict[str, Any]] = []
    adjusted_table: list[dict[str, Any]] = []
    result_sources: list[Path] = []

    baseline_entry = entries.get(BASELINE_STRATEGY, {})
    if baseline_entry.get("succeeded") and baseline_entry.get("stableResult"):
        baseline_path = Path(baseline_entry["stableResult"])
        result_sources.append(baseline_path)
        baseline_raw, baseline_adjusted, pair_rows, month_rows, baseline_warnings = _metrics_from_result(
            baseline_path,
            BASELINE_STRATEGY,
            slippage_rate,
        )
        warnings.extend(f"{BASELINE_STRATEGY}: {warning}" for warning in baseline_warnings)
        raw_table.append(_comparison_row(BASELINE_STRATEGY, baseline_raw, adjusted=False))
        adjusted_table.append(_comparison_row(BASELINE_STRATEGY, baseline_adjusted, adjusted=True, passed=False))
        baseline = {
            "strategy": BASELINE_STRATEGY,
            "backtestReport": baseline_entry.get("stableResult"),
            "rawMetrics": baseline_raw,
            "slippageAdjustedMetrics": baseline_adjusted,
            "pairBreakdown": pair_rows,
            "monthlyBreakdown": month_rows,
        }
    else:
        baseline = {
            "strategy": BASELINE_STRATEGY,
            "backtestReport": baseline_entry.get("stableResult"),
            "rawMetrics": {},
            "slippageAdjustedMetrics": {},
            "pairBreakdown": [],
            "monthlyBreakdown": [],
        }
        warnings.append("Baseline backtest missing or failed.")

    for strategy in list(manifest.get("strategiesRequested", [])) or list(entries):
        if strategy == BASELINE_STRATEGY:
            continue
        entry = entries.get(strategy, {})
        if not entry.get("succeeded") or not entry.get("stableResult"):
            warning = entry.get("error") or "Backtest result unavailable."
            results.append(
                ExpandedValidationResult(
                    strategy=strategy,
                    backtestReport=entry.get("stableResult"),
                    backtestSucceeded=False,
                    rawMetrics={},
                    slippageAdjustedMetrics={},
                    deltaVsBaseline={},
                    pairBreakdown=[],
                    monthlyBreakdown=[],
                    passedExpandedGate=False,
                    warnings=[warning],
                )
            )
            warnings.append(f"{strategy}: {warning}")
            continue

        result_path = Path(entry["stableResult"])
        result_sources.append(result_path)
        raw, adjusted, pair_rows, month_rows, metric_warnings = _metrics_from_result(result_path, strategy, slippage_rate)
        fields = [
            "slippageAdjustedTotalReturnPct",
            "slippageAdjustedProfitFactor",
            "maxDrawdownPct",
            "maxConsecutiveLosses",
            "tradeCount",
            "totalSlippageCost",
        ]
        delta = _delta(adjusted, baseline_adjusted, fields)
        passed = _passes_gate(adjusted, baseline_adjusted)
        results.append(
            ExpandedValidationResult(
                strategy=strategy,
                backtestReport=entry["stableResult"],
                backtestSucceeded=True,
                rawMetrics=raw,
                slippageAdjustedMetrics=adjusted,
                deltaVsBaseline=delta,
                pairBreakdown=pair_rows,
                monthlyBreakdown=month_rows,
                passedExpandedGate=passed,
                warnings=metric_warnings,
            )
        )
        warnings.extend(f"{strategy}: {warning}" for warning in metric_warnings)
        raw_table.append(_comparison_row(strategy, raw, adjusted=False))
        adjusted_table.append(_comparison_row(strategy, adjusted, adjusted=True, passed=passed))

    supported, excluded = _supported_pairs(manifest, result_sources)
    best_raw = _rank_raw(raw_table)
    best_adjusted = _rank_adjusted(adjusted_table)
    passed_count = sum(1 for row in adjusted_table if row.get("strategy") != BASELINE_STRATEGY and row.get("passedExpandedGate"))
    adjusted_candidate_returns = [
        row.get("slippageAdjustedTotalReturnPct")
        for row in adjusted_table
        if row.get("strategy") != BASELINE_STRATEGY
    ]
    if adjusted_candidate_returns and not any(
        isinstance(value, (int, float)) and value > 0 for value in adjusted_candidate_returns
    ):
        warnings.append("All candidates remain negative after slippage post-processing.")
    if any(
        isinstance(row.get("maxDrawdownPct"), (int, float)) and row["maxDrawdownPct"] > 100
        for row in adjusted_table
    ):
        warnings.append(
            "Post-processed drawdown can exceed 100% because slippage is applied after Freqtrade without a liquidation model."
        )
    if excluded:
        warnings.append("Some requested pairs were excluded by exchange compatibility or missing completed result coverage.")
    reasons = [
        "V13.4.5 is expanded validation and slippage post-processing only.",
        "Slippage is not applied by Freqtrade; it is applied by AlphaPilot report post-processing.",
        "Dry-run remains blocked regardless of expanded gate outcome.",
    ]
    if passed_count:
        reasons.append(f"{passed_count} candidate(s) passed the expanded research gate, but longer validation is still required.")
    else:
        reasons.append("No candidate passed the expanded research gate after slippage adjustment.")

    return ExpandedValidationReport(
        reportId="v13_4_5_expanded_validation",
        scope={
            "pairsMode": manifest.get("pairsMode", "fixed_top30"),
            "timerange": manifest.get("timerange", "20260101-"),
            "timeframe": manifest.get("timeframe", "15m"),
            "slippageRateOneWay": slippage_rate,
            "slippageAppliedByFreqtrade": False,
            "slippageAppliedByPostProcessing": True,
        },
        strategies=list(manifest.get("strategiesRequested", [])) or list(entries),
        baselineStrategy=BASELINE_STRATEGY,
        baseline=baseline,
        results=results,
        rawComparisonTable=raw_table,
        slippageAdjustedComparisonTable=adjusted_table,
        supportedPairs=supported,
        excludedPairs=excluded,
        warnings=warnings,
        bestRawCandidate=best_raw,
        bestSlippageAdjustedCandidate=best_adjusted,
        dryRunApproved=False,
        reasons=reasons,
        nextStepRecommendation=(
            "If expanded validation remains negative after slippage, move to V13.4.6 strategy direction review "
            "or V03 redesign. If one candidate improves materially, validate over longer timeranges before any Dry-run discussion."
        ),
        generatedAt=_utc_now(),
    )


def _write_summary(report: dict[str, Any], path: Path) -> None:
    lines = [
        "# V13.4.5 Expanded Validation Summary",
        "",
        "## Decision",
        "",
        f"- Dry-run approved: {report['dryRunApproved']}",
        f"- Best raw candidate: {report['bestRawCandidate']}",
        f"- Best slippage-adjusted candidate: {report['bestSlippageAdjustedCandidate']}",
        f"- Slippage by Freqtrade: {report['scope']['slippageAppliedByFreqtrade']}",
        f"- Slippage by post-processing: {report['scope']['slippageAppliedByPostProcessing']}",
        "",
        "## Scope",
        "",
        f"- Pairs mode: {report['scope']['pairsMode']}",
        f"- Timerange: {report['scope']['timerange']}",
        f"- Timeframe: {report['scope']['timeframe']}",
        f"- One-way slippage rate: {report['scope']['slippageRateOneWay']}",
        "",
        "## Raw Comparison",
        "",
        "| Strategy | Return % | Drawdown % | Profit Factor | Trades | Win Rate % | Max Loss Streak |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in report["rawComparisonTable"]:
        lines.append(
            f"| {row['strategy']} | {row.get('totalReturnPct')} | {row.get('maxDrawdownPct')} | "
            f"{row.get('profitFactor')} | {row.get('tradeCount')} | {row.get('winRate')} | "
            f"{row.get('maxConsecutiveLosses')} |"
        )
    lines.extend(
        [
            "",
            "## Slippage-Adjusted Comparison",
            "",
            "| Strategy | Adj Return % | Adj Drawdown % | Adj PF | Trades | Adj Win Rate % | Max Loss Streak | Slippage Cost | Gate |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---|",
        ]
    )
    for row in report["slippageAdjustedComparisonTable"]:
        lines.append(
            f"| {row['strategy']} | {row.get('slippageAdjustedTotalReturnPct')} | {row.get('maxDrawdownPct')} | "
            f"{row.get('slippageAdjustedProfitFactor')} | {row.get('tradeCount')} | "
            f"{row.get('slippageAdjustedWinRate')} | {row.get('maxConsecutiveLosses')} | "
            f"{row.get('totalSlippageCost')} | {row.get('passedExpandedGate')} |"
        )
    lines.extend(["", "## Supported Pairs", ""])
    lines.append(", ".join(report["supportedPairs"]) if report["supportedPairs"] else "None")
    lines.extend(["", "## Excluded Pairs", ""])
    if report["excludedPairs"]:
        lines.extend(f"- {item['pair']}: {item['reason']}" for item in report["excludedPairs"])
    else:
        lines.append("- None")
    lines.extend(["", "## Reasons", ""])
    lines.extend(f"- {item}" for item in report["reasons"])
    lines.extend(["", "## Warnings", ""])
    lines.extend(f"- {item}" for item in report["warnings"]) if report["warnings"] else lines.append("- None")
    lines.extend(
        [
            "",
            "## Safety",
            "",
            "V13.4.5 uses local Freqtrade backtesting artifacts and public historical data only. It does not enter Dry-run, approve live trading, use API keys, call Trade API or Withdraw API, read accounts, create orders, or auto trade.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def export_report(
    manifest: Path,
    output_json: Path,
    output_summary: Path,
    slippage_rate: float,
) -> tuple[Path, Path]:
    report = build_report(manifest, slippage_rate).to_dict()
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_summary(report, output_summary)
    return output_json, output_summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate V13.4.5 expanded validation report.")
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
    print(f"Exported expanded validation report: {output_json}")
    print(f"Exported expanded validation summary: {output_summary}")


if __name__ == "__main__":
    main()
