"""Generate V13.4.17 Dynamic Regime expanded validation report.

The report reads local Freqtrade backtest artifacts and local public OHLCV
files only. Slippage stress is post-processing research math. This module does
not enter Dry-run, call exchange APIs, read accounts, create orders, or auto
trade.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from alphapilot.reports.dynamic_regime_expanded_schema import DynamicRegimeExpandedReport
from alphapilot.reports.export_backtest_report import (
    _build_metrics,
    _find_latest_freqtrade_result,
    _read_freqtrade_result_payload,
    _select_strategy_payload,
)

REPORT_ID = "v13_4_17_dynamic_regime_expanded_report"
REPORT_VERSION = "V13.4.17"
STRATEGY_CLASS = "AlphaPilotDynamicRegimeV01"
STRATEGY_ID = "alpha_dynamic_regime_v01"
STRATEGY_NAME = "AlphaPilot Dynamic Regime V0.1"
STRATEGY_VERSION = "0.1-v13.4.15"
DEFAULT_TIMERANGE = "20260101-"
DEFAULT_TIMEFRAME = "1h"
DEFAULT_DATA_PATH = Path("user_data/data/okx/futures")
DEFAULT_UNIVERSE_PATH = Path("reports/v13_4_13_dynamic_universe_snapshots.json")
DEFAULT_PROBABILITY_PATH = Path("reports/v13_4_14_probability_score_table.json")
DEFAULT_OUTPUT_JSON = Path("reports/v13_4_17_dynamic_regime_expanded_report.json")
DEFAULT_OUTPUT_SUMMARY = Path("reports/v13_4_17_dynamic_regime_expanded_summary.md")
SLIPPAGE_STRESS_RATES = [0.0005, 0.001, 0.002, 0.003]
PRIMARY_SLIPPAGE_RATE = 0.001


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _round(value: Any, digits: int = 4) -> float | None:
    try:
        if value is None:
            return None
        return round(float(value), digits)
    except (TypeError, ValueError):
        return None


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _pair_stem(pair: str) -> str:
    return pair.replace("/", "_").replace(":", "_")


def _read_ohlcv(pair: str, timeframe: str, data_path: Path) -> pd.DataFrame:
    path = data_path / f"{_pair_stem(pair)}-{timeframe}-futures.feather"
    if not path.exists():
        return pd.DataFrame()
    frame = pd.read_feather(path).copy()
    frame["date"] = pd.to_datetime(frame["date"], utc=True, errors="coerce")
    return frame.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)


def _local_merge_informative_pair(
    dataframe: pd.DataFrame,
    informative: pd.DataFrame,
    timeframe: str,
    informative_timeframe: str,
    ffill: bool = True,
) -> pd.DataFrame:
    if dataframe.empty or informative.empty or "date" not in informative.columns:
        return dataframe
    left = dataframe.sort_values("date").copy()
    right = informative.sort_values("date").copy()
    rename = {column: f"{column}_{informative_timeframe}" for column in right.columns if column != "date"}
    right = right.rename(columns=rename)
    merged = pd.merge_asof(left, right, on="date", direction="backward")
    return merged.ffill() if ffill else merged


class _LocalDataProvider:
    def __init__(self, pairs: list[str], data_path: Path) -> None:
        self.pairs = pairs
        self.data_path = data_path
        self.cache: dict[tuple[str, str], pd.DataFrame] = {}

    def current_whitelist(self) -> list[str]:
        return self.pairs

    def get_pair_dataframe(self, pair: str, timeframe: str) -> pd.DataFrame:
        key = (pair, timeframe)
        if key not in self.cache:
            self.cache[key] = _read_ohlcv(pair, timeframe, self.data_path)
        return self.cache[key].copy()


def _load_strategy_class() -> type:
    path = Path("user_data/strategies/AlphaPilotDynamicRegimeV01.py")
    spec = importlib.util.spec_from_file_location("AlphaPilotDynamicRegimeV01", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to import strategy from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.merge_informative_pair = _local_merge_informative_pair
    return module.AlphaPilotDynamicRegimeV01


def _timerange_start(timerange: str) -> pd.Timestamp | None:
    start_raw = timerange.split("-", 1)[0]
    if not start_raw:
        return None
    return pd.Timestamp(datetime.strptime(start_raw, "%Y%m%d").replace(tzinfo=timezone.utc))


def _dynamic_pairs_from_snapshots(path: Path) -> list[str]:
    snapshots = _read_json(path) if path.exists() else []
    pairs: set[str] = set()
    for snapshot in snapshots if isinstance(snapshots, list) else []:
        for pair in snapshot.get("selectedPairs", []) or []:
            pairs.add(str(pair))
    return sorted(pairs)


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


def _max_consecutive_losses(values: list[float]) -> int:
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
    if not starting_balance or starting_balance <= 0:
        return 0.0 if not profits else None
    equity = starting_balance
    peak = starting_balance
    max_drawdown = 0.0
    for profit in profits:
        equity += profit
        peak = max(peak, equity)
        if peak > 0:
            max_drawdown = max(max_drawdown, (peak - equity) / peak * 100)
    return _round(max_drawdown, 4)


def _largest_abs_contribution(rows: list[dict[str, Any]], key: str) -> float | None:
    values = [abs(float(row.get(key) or 0.0)) for row in rows]
    total = sum(values)
    if total <= 0:
        return None
    return _round(max(values) / total * 100, 4)


def _adjust_trades(trades: list[dict[str, Any]], slippage_rate: float) -> tuple[list[dict[str, Any]], list[str]]:
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
        adjusted.append(
            {
                "pair": trade.get("pair") or "unknown",
                "month": _trade_month(trade),
                "rawProfitAbs": raw_profit_abs,
                "rawProfitRatio": raw_profit_ratio,
                "slippageCost": slippage_cost,
                "slippageCostEstimated": estimated,
                "adjustedProfitAbs": raw_profit_abs - slippage_cost,
                "adjustedProfitRatio": raw_profit_ratio - (slippage_rate * 2),
                "tradeDuration": trade.get("trade_duration"),
                "exitReason": trade.get("exit_reason"),
            }
        )
    if estimated_count:
        warnings.append(f"Slippage cost used estimated notional for {estimated_count} trade(s).")
    return adjusted, warnings


def _group_adjusted_trades(
    adjusted_trades: list[dict[str, Any]],
    group_key: str,
    output_key: str,
    starting_balance: float | None,
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for trade in adjusted_trades:
        grouped[str(trade.get(group_key) or "unknown")].append(trade)
    rows = []
    for label, trades in sorted(grouped.items()):
        profits = [float(trade["adjustedProfitAbs"]) for trade in trades]
        total_profit = sum(profits)
        rows.append(
            {
                output_key: label,
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


def _raw_metrics(source: dict[str, Any]) -> dict[str, Any]:
    metrics = _build_metrics(source)
    return {
        "tradeCount": metrics.tradeCount,
        "totalReturnPct": metrics.totalReturnPct,
        "maxDrawdownPct": metrics.maxDrawdownPct,
        "profitFactor": metrics.profitFactor,
        "winRate": metrics.winRate,
        "maxConsecutiveLosses": source.get("max_consecutive_losses"),
        "feesPaid": metrics.feesPaid,
        "averageHoldingMinutes": metrics.averageHoldingMinutes,
        "slippageAppliedByFreqtrade": False,
        "slippageAppliedByPostProcessing": False,
    }


def _slippage_stress(source: dict[str, Any], slippage_rates: list[float]) -> tuple[list[dict[str, Any]], list[str], list[dict[str, Any]], list[dict[str, Any]]]:
    trades = source.get("trades", []) if isinstance(source.get("trades"), list) else []
    starting_balance = float(source.get("starting_balance") or source.get("dry_run_wallet") or 0.0) or None
    stress_rows: list[dict[str, Any]] = []
    warnings: list[str] = []
    primary_pair_rows: list[dict[str, Any]] = []
    primary_month_rows: list[dict[str, Any]] = []

    for rate in slippage_rates:
        adjusted_trades, rate_warnings = _adjust_trades(trades, rate)
        warnings.extend(f"{rate:.4f}: {warning}" for warning in rate_warnings)
        adjusted_abs = [float(trade["adjustedProfitAbs"]) for trade in adjusted_trades]
        total_adjusted_abs = sum(adjusted_abs)
        pair_rows = _group_adjusted_trades(adjusted_trades, "pair", "pair", starting_balance)
        month_rows = _group_adjusted_trades(adjusted_trades, "month", "month", starting_balance)
        stress_rows.append(
            {
                "slippageRateOneWay": rate,
                "slippageCostPctRoundTrip": _round(rate * 2 * 100, 4),
                "slippageAppliedByFreqtrade": False,
                "slippageAppliedByPostProcessing": True,
                "tradeCount": len(trades),
                "totalSlippageCost": _round(sum(float(trade["slippageCost"]) for trade in adjusted_trades), 8),
                "slippageCostEstimated": any(bool(trade["slippageCostEstimated"]) for trade in adjusted_trades),
                "slippageAdjustedTotalProfitAbs": _round(total_adjusted_abs, 8),
                "slippageAdjustedReturnPct": _round(total_adjusted_abs / starting_balance * 100, 4)
                if starting_balance
                else None,
                "slippageAdjustedProfitFactor": _profit_factor(adjusted_abs),
                "slippageAdjustedWinRate": _win_rate(adjusted_abs),
                "maxDrawdownPct": _max_drawdown_pct(adjusted_abs, starting_balance),
                "maxConsecutiveLosses": _max_consecutive_losses(adjusted_abs),
                "largestPairAbsContributionPct": _largest_abs_contribution(pair_rows, "slippageAdjustedProfitAbs"),
                "largestMonthAbsContributionPct": _largest_abs_contribution(month_rows, "slippageAdjustedProfitAbs"),
            }
        )
        if rate == PRIMARY_SLIPPAGE_RATE:
            primary_pair_rows = pair_rows
            primary_month_rows = month_rows

    return stress_rows, warnings, primary_pair_rows, primary_month_rows


def _latest_strategy_result() -> tuple[Path | None, dict[str, Any]]:
    result = _find_latest_freqtrade_result()
    if result is None:
        return None, {}
    payload = _read_freqtrade_result_payload(result)
    strategy_name, source = _select_strategy_payload(payload)
    if strategy_name != STRATEGY_CLASS:
        return result, {}
    return result, source


def _audit_replay(pairs: list[str], timerange: str, data_path: Path) -> dict[str, Any]:
    strategy_class = _load_strategy_class()
    strategy = strategy_class()
    strategy.dp = _LocalDataProvider(pairs, data_path)
    start = _timerange_start(timerange)
    regime_counter: Counter[str] = Counter()
    skip_counter: Counter[str] = Counter()
    bucket_counter: dict[str, Counter[str]] = defaultdict(Counter)
    pair_counter: dict[str, Counter[str]] = defaultdict(Counter)
    totals = Counter()
    warnings: list[str] = []

    for pair in pairs:
        frame = _read_ohlcv(pair, DEFAULT_TIMEFRAME, data_path)
        if frame.empty:
            warnings.append(f"{pair}: missing {DEFAULT_TIMEFRAME} OHLCV for audit replay")
            continue
        if start is not None:
            frame = frame[frame["date"] >= start].copy()
        if frame.empty:
            warnings.append(f"{pair}: no rows inside timerange for audit replay")
            continue
        try:
            analyzed = strategy.populate_indicators(frame.copy(), {"pair": pair})
            analyzed = strategy.populate_entry_trend(analyzed, {"pair": pair})
        except Exception as exc:  # noqa: BLE001 - report replay failure without masking the real backtest artifact.
            warnings.append(f"{pair}: audit replay failed: {exc}")
            continue

        totals["rowsEvaluated"] += int(len(analyzed))
        pair_counter[pair]["rowsEvaluated"] += int(len(analyzed))
        column_map = {
            "inDynamicUniverseRows": "ap_dyn_audit_in_dynamic_universe",
            "trendModulePass": "ap_dyn_audit_trend_module_pass",
            "meanReversionModulePass": "ap_dyn_audit_mean_reversion_module_pass",
            "probabilityScoreAvailable": "ap_dyn_audit_probability_score_available",
            "probabilityScorePass": "ap_dyn_audit_probability_score_pass",
            "liquidityFallbackUsed": "ap_dyn_audit_liquidity_gate_pass",
            "finalEntrySignals": "ap_dyn_audit_final_entry",
        }
        for key, column in column_map.items():
            if column in analyzed.columns:
                totals[key] += int(analyzed[column].fillna(False).astype(bool).sum())
                pair_counter[pair][key] += int(analyzed[column].fillna(False).astype(bool).sum())
        if "ap_dyn_audit_probability_score_pass" in analyzed.columns:
            fail_count = int((~analyzed["ap_dyn_audit_probability_score_pass"].fillna(False).astype(bool)).sum())
            totals["probabilityScoreFail"] += fail_count
            pair_counter[pair]["probabilityScoreFail"] += fail_count
        if "ap_dyn_audit_regime" in analyzed.columns:
            regime_values = [str(value) for value in analyzed["ap_dyn_audit_regime"].fillna("unknown")]
            regime_counter.update(regime_values)
            pair_counter[pair].update(f"regime:{value}" for value in regime_values)
        if "ap_dyn_audit_skip_reason" in analyzed.columns:
            skip_counter.update(str(value) for value in analyzed["ap_dyn_audit_skip_reason"].fillna("unknown"))
        if "ap_dyn_probability_bucket" in analyzed.columns:
            for _, row in analyzed.iterrows():
                bucket = str(row.get("ap_dyn_probability_bucket") or "unknown")
                bucket_counter[bucket]["rows"] += 1
                if bool(row.get("ap_dyn_audit_probability_score_available")):
                    bucket_counter[bucket]["available"] += 1
                if bool(row.get("ap_dyn_audit_probability_score_pass")):
                    bucket_counter[bucket]["pass"] += 1
                if bool(row.get("ap_dyn_audit_final_entry")):
                    bucket_counter[bucket]["finalEntry"] += 1

    bucket_rows = [
        {
            "bucketId": bucket,
            "rows": counts["rows"],
            "available": counts["available"],
            "pass": counts["pass"],
            "fail": counts["rows"] - counts["pass"],
            "finalEntry": counts["finalEntry"],
        }
        for bucket, counts in bucket_counter.items()
    ]
    bucket_rows.sort(key=lambda item: (item["finalEntry"], item["pass"], item["rows"]), reverse=True)
    pair_rows = [
        {
            "pair": pair,
            "rowsEvaluated": counts["rowsEvaluated"],
            "inDynamicUniverseRows": counts["inDynamicUniverseRows"],
            "trendModulePass": counts["trendModulePass"],
            "meanReversionModulePass": counts["meanReversionModulePass"],
            "probabilityScorePass": counts["probabilityScorePass"],
            "finalEntrySignals": counts["finalEntrySignals"],
        }
        for pair, counts in sorted(pair_counter.items())
    ]

    return {
        "regimeBreakdown": dict(sorted(regime_counter.items())),
        "moduleBreakdown": {
            "trendModulePass": totals["trendModulePass"],
            "meanReversionModulePass": totals["meanReversionModulePass"],
            "finalEntrySignals": totals["finalEntrySignals"],
            "skipReasons": dict(skip_counter.most_common(20)),
        },
        "probabilityScoreSummary": {
            "rowsEvaluated": totals["rowsEvaluated"],
            "available": totals["probabilityScoreAvailable"],
            "pass": totals["probabilityScorePass"],
            "fail": totals["probabilityScoreFail"],
            "source": str(DEFAULT_PROBABILITY_PATH),
        },
        "probabilityBucketPerformance": bucket_rows[:50],
        "liquidityGateSummary": {
            "available": False,
            "fallbackUsedRows": totals["liquidityFallbackUsed"],
            "fallbackPolicy": "allowed for expanded validation research only; not a real liquidity approval",
        },
        "auditPairBreakdown": pair_rows,
        "warnings": warnings,
    }


def _quality_gate(raw_metrics: dict[str, Any], stress_rows: list[dict[str, Any]]) -> dict[str, Any]:
    primary = next((row for row in stress_rows if row["slippageRateOneWay"] == PRIMARY_SLIPPAGE_RATE), None)
    reasons: list[str] = []
    passed = True
    if not primary:
        return {"passed": False, "primarySlippageRateOneWay": PRIMARY_SLIPPAGE_RATE, "reasons": ["primary_slippage_missing"]}

    trade_count = int(primary.get("tradeCount") or 0)
    if trade_count < 30:
        passed = False
        reasons.append("trade_count_not_meaningful")
    if (primary.get("slippageAdjustedReturnPct") or 0) <= 0:
        passed = False
        reasons.append("slippage_adjusted_return_not_positive")
    if primary.get("slippageAdjustedProfitFactor") is None or primary["slippageAdjustedProfitFactor"] <= 1.15:
        passed = False
        reasons.append("slippage_adjusted_profit_factor_not_above_1_15")
    if primary.get("maxDrawdownPct") is None or primary["maxDrawdownPct"] > 25:
        passed = False
        reasons.append("max_drawdown_not_acceptable")
    if primary.get("maxConsecutiveLosses") is None or primary["maxConsecutiveLosses"] > 8:
        passed = False
        reasons.append("max_consecutive_losses_not_acceptable")
    pair_dom = primary.get("largestPairAbsContributionPct")
    if isinstance(pair_dom, (int, float)) and pair_dom > 50:
        passed = False
        reasons.append("pair_dominance_too_high")
    month_dom = primary.get("largestMonthAbsContributionPct")
    if isinstance(month_dom, (int, float)) and month_dom > 60:
        passed = False
        reasons.append("month_dominance_too_high")
    if not reasons:
        reasons.append("research_gate_passed_but_dry_run_still_blocked")

    return {
        "passed": passed,
        "primarySlippageRateOneWay": PRIMARY_SLIPPAGE_RATE,
        "rawTradeCount": raw_metrics.get("tradeCount"),
        "slippageAdjustedReturnPct": primary.get("slippageAdjustedReturnPct"),
        "slippageAdjustedProfitFactor": primary.get("slippageAdjustedProfitFactor"),
        "maxDrawdownPct": primary.get("maxDrawdownPct"),
        "maxConsecutiveLosses": primary.get("maxConsecutiveLosses"),
        "largestPairAbsContributionPct": primary.get("largestPairAbsContributionPct"),
        "largestMonthAbsContributionPct": primary.get("largestMonthAbsContributionPct"),
        "reasons": reasons,
    }


def build_report(pairs: list[str], timerange: str, data_path: Path, universe_path: Path) -> DynamicRegimeExpandedReport:
    result_path, source = _latest_strategy_result()
    audit = _audit_replay(pairs, timerange, data_path)
    warnings = list(audit.get("warnings", []))
    if result_path is None:
        warnings.append("No Freqtrade result found. Expanded validation is blocked and not taggable.")
    elif not source:
        warnings.append(f"Latest Freqtrade result is not for {STRATEGY_CLASS}: {result_path}")

    raw = _raw_metrics(source) if source else {
        "tradeCount": 0,
        "totalReturnPct": None,
        "maxDrawdownPct": None,
        "profitFactor": None,
        "winRate": None,
    }
    stress_rows, stress_warnings, pair_breakdown, monthly_breakdown = _slippage_stress(source, SLIPPAGE_STRESS_RATES) if source else ([], [], [], [])
    warnings.extend(stress_warnings)

    universe_payload = _read_json(universe_path) if universe_path.exists() else []
    dynamic_summary = {
        "source": str(universe_path),
        "snapshotCount": len(universe_payload) if isinstance(universe_payload, list) else 0,
        "pairUnionCount": len(pairs),
        "pairsMode": "historical_dynamic_universe_union_for_backtest_with_strategy_date_filter",
        "note": "Backtest pair list is the union of historical selectedPairs; strategy still filters rows by snapshot date.",
    }

    return DynamicRegimeExpandedReport(
        reportId=REPORT_ID,
        version=REPORT_VERSION,
        strategyId=STRATEGY_ID,
        strategyName=STRATEGY_NAME,
        strategyVersion=STRATEGY_VERSION,
        timerange=timerange,
        timeframe=DEFAULT_TIMEFRAME,
        pairs=pairs,
        isMock=False if source else True,
        dryRunApproved=False,
        liveTradingApproved=False,
        rawMetrics=raw,
        slippageStressMetrics=stress_rows,
        liquidityGateSummary=audit["liquidityGateSummary"],
        probabilityScoreSummary=audit["probabilityScoreSummary"],
        probabilityBucketPerformance=audit["probabilityBucketPerformance"],
        regimeBreakdown=audit["regimeBreakdown"],
        moduleBreakdown=audit["moduleBreakdown"],
        dynamicUniverseSummary=dynamic_summary,
        pairBreakdown=pair_breakdown or audit["auditPairBreakdown"],
        monthlyBreakdown=monthly_breakdown,
        qualityGate=_quality_gate(raw, stress_rows),
        backtestResultPath=str(result_path) if result_path else None,
        reportWarnings=warnings,
        generatedAt=_utc_now(),
    )


def write_summary(report: dict[str, Any], path: Path) -> None:
    lines = [
        "# V13.4.17 Dynamic Regime Expanded Validation Summary",
        "",
        "## Status",
        "",
        f"- strategyId: {report['strategyId']}",
        f"- isMock: {str(report['isMock']).lower()}",
        f"- dryRunApproved: {str(report['dryRunApproved']).lower()}",
        f"- liveTradingApproved: {str(report['liveTradingApproved']).lower()}",
        f"- timerange: {report['timerange']}",
        f"- timeframe: {report['timeframe']}",
        f"- pairCount: {len(report['pairs'])}",
        f"- backtestResultPath: {report['backtestResultPath']}",
        "",
        "## Raw Metrics",
        "",
    ]
    lines.extend(f"- {key}: {value}" for key, value in report["rawMetrics"].items())
    lines.extend(["", "## Slippage Stress", ""])
    lines.append("| One-way slippage | Adj return % | Adj PF | Drawdown % | Trades | Max loss streak | Slippage cost |")
    lines.append("|---:|---:|---:|---:|---:|---:|---:|")
    for row in report["slippageStressMetrics"]:
        lines.append(
            f"| {row['slippageRateOneWay']} | {row.get('slippageAdjustedReturnPct')} | "
            f"{row.get('slippageAdjustedProfitFactor')} | {row.get('maxDrawdownPct')} | "
            f"{row.get('tradeCount')} | {row.get('maxConsecutiveLosses')} | {row.get('totalSlippageCost')} |"
        )
    lines.extend(["", "## Quality Gate", ""])
    lines.append(f"- passed: {report['qualityGate'].get('passed')}")
    lines.extend(f"- reason: {reason}" for reason in report["qualityGate"].get("reasons", []))
    lines.extend(["", "## Regime Breakdown", ""])
    lines.extend(f"- {key}: {value}" for key, value in report["regimeBreakdown"].items()) if report["regimeBreakdown"] else lines.append("- unavailable")
    lines.extend(["", "## Module Breakdown", ""])
    for key, value in report["moduleBreakdown"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Probability Score Summary", ""])
    for key, value in report["probabilityScoreSummary"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Liquidity Gate Summary", ""])
    for key, value in report["liquidityGateSummary"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Dynamic Universe", ""])
    for key, value in report["dynamicUniverseSummary"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Warnings", ""])
    lines.extend(f"- {warning}" for warning in report["reportWarnings"]) if report["reportWarnings"] else lines.append("- none")
    lines.extend(
        [
            "",
            "## Safety",
            "",
            "This is a local expanded validation report only. It is not Dry-run approval and not live trading approval. No API key, Trade API, Withdraw API, account read, position read, order creation, or auto trading is used.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate V13.4.17 Dynamic Regime expanded validation report.")
    parser.add_argument("--pairs", default="")
    parser.add_argument("--timerange", default=DEFAULT_TIMERANGE)
    parser.add_argument("--data-path", type=Path, default=DEFAULT_DATA_PATH)
    parser.add_argument("--universe-path", type=Path, default=DEFAULT_UNIVERSE_PATH)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-summary", type=Path, default=DEFAULT_OUTPUT_SUMMARY)
    args = parser.parse_args()

    pairs = [part.strip() for part in args.pairs.split(",") if part.strip()]
    if not pairs:
        pairs = _dynamic_pairs_from_snapshots(args.universe_path)
    report = build_report(pairs, args.timerange, args.data_path, args.universe_path)
    payload = report.to_dict()
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_summary(payload, args.output_summary)
    print(f"Dynamic Regime expanded report: {args.output_json}")
    print(f"Summary: {args.output_summary}")
    print(f"isMock: {report.isMock}")
    print(f"tradeCount: {report.rawMetrics.get('tradeCount')}")
    print(f"qualityGatePassed: {report.qualityGate.get('passed')}")


if __name__ == "__main__":
    main()
