"""Diagnose the V13.4 real smoke backtest result.

This module reads local backtest artifacts only. It does not tune strategy
parameters, call exchanges, place orders, or enter dry-run.
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zipfile import ZipFile

from alphapilot.reports.diagnosis_schema import BacktestDiagnosisReport

DEFAULT_SOURCE_REPORT = Path("reports/v13_4_smoke_backtest_report.json")
DEFAULT_OUTPUT_REPORT = Path("reports/v13_4_1_diagnosis_report.json")
DEFAULT_OUTPUT_SUMMARY = Path("reports/v13_4_1_diagnosis_summary.md")

FILTERS_REVIEWED = [
    "BTC crash filter",
    "4h trend filter",
    "RSI 30-55 filter",
    "volumeRatio >= 1.5",
    "MACD histogram improving",
    "close >= EMA20 * 0.995",
    "pullback / no chase filter",
]

DO_NOT_CHANGE_YET = [
    "Do not modify stoploss yet.",
    "Do not modify take profit yet.",
    "Do not modify RSI range yet.",
    "Do not modify volumeRatio threshold yet.",
    "Do not modify BTC crash filter yet.",
    "Do not enter Dry-run.",
    "Do not expand to Top30 full backtest before diagnosis is reviewed.",
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _round(value: float | int | None, digits: int = 4) -> float | None:
    if value is None:
        return None
    return round(float(value), digits)


def _sum(values: list[float]) -> float:
    return float(sum(values))


def _mean(values: list[float]) -> float | None:
    return statistics.mean(values) if values else None


def _median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def _profit_factor(profits: list[float]) -> float | None:
    gross_win = sum(value for value in profits if value > 0)
    gross_loss = abs(sum(value for value in profits if value < 0))
    if gross_loss == 0:
        return None if gross_win == 0 else 0.0
    return gross_win / gross_loss


def _win_rate(trades: list[dict[str, Any]]) -> float | None:
    if not trades:
        return None
    wins = sum(1 for trade in trades if float(trade.get("profit_abs", 0) or 0) > 0)
    return wins / len(trades) * 100


def _trade_sort_key(trade: dict[str, Any]) -> int:
    return int(trade.get("close_timestamp") or trade.get("open_timestamp") or 0)


def _duration_bucket(minutes: float) -> str:
    if minutes < 60:
        return "0-1h"
    if minutes < 180:
        return "1-3h"
    if minutes < 360:
        return "3-6h"
    if minutes < 720:
        return "6-12h"
    return "12h+"


def _parse_source_result(path: Path) -> dict[str, Any]:
    if path.suffix.lower() != ".zip":
        payload = _read_json(path)
    else:
        with ZipFile(path) as archive:
            result_members = [
                name
                for name in archive.namelist()
                if name.lower().endswith(".json")
                and not name.lower().endswith("_config.json")
                and not name.lower().endswith(".meta.json")
            ]
            if not result_members:
                raise ValueError(f"No Freqtrade result JSON found inside {path}")
            payload = json.loads(archive.read(result_members[0]).decode("utf-8"))

    strategy = payload.get("strategy", {})
    if "AlphaPilotVolumeReboundV01" in strategy:
        return strategy["AlphaPilotVolumeReboundV01"]
    if isinstance(strategy, dict) and strategy:
        first = next(iter(strategy.values()))
        if isinstance(first, dict):
            return first
    return payload


def _trade_stats(trades: list[dict[str, Any]]) -> dict[str, Any]:
    profits_abs = [float(trade.get("profit_abs", 0) or 0) for trade in trades]
    profits_pct = [float(trade.get("profit_ratio", 0) or 0) * 100 for trade in trades]
    wins = [value for value in profits_abs if value > 0]
    losses = [value for value in profits_abs if value < 0]
    durations = [float(trade.get("trade_duration", 0) or 0) for trade in trades]
    best = max(trades, key=lambda trade: float(trade.get("profit_abs", 0) or 0), default=None)
    worst = min(trades, key=lambda trade: float(trade.get("profit_abs", 0) or 0), default=None)

    return {
        "tradeCount": len(trades),
        "winningTrades": len(wins),
        "losingTrades": len(losses),
        "winRate": _round(_win_rate(trades)),
        "netProfit": _round(_sum(profits_abs), 8),
        "averageProfitPct": _round(_mean(profits_pct)),
        "averageWin": _round(_mean(wins), 8),
        "averageLoss": _round(_mean(losses), 8),
        "profitFactor": _round(_profit_factor(profits_abs)),
        "averageHoldingMinutes": _round(_mean(durations)),
        "medianHoldingMinutes": _round(_median(durations)),
        "bestTrade": _format_trade(best),
        "worstTrade": _format_trade(worst),
    }


def _format_trade(trade: dict[str, Any] | None) -> dict[str, Any] | None:
    if not trade:
        return None
    return {
        "pair": trade.get("pair"),
        "openDate": trade.get("open_date"),
        "closeDate": trade.get("close_date"),
        "profitAbs": _round(float(trade.get("profit_abs", 0) or 0), 8),
        "profitRatioPct": _round(float(trade.get("profit_ratio", 0) or 0) * 100),
        "exitReason": trade.get("exit_reason"),
        "durationMinutes": trade.get("trade_duration"),
    }


def _max_consecutive_losses(trades: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = sorted(trades, key=_trade_sort_key)
    streaks: list[dict[str, Any]] = []
    current: list[dict[str, Any]] = []

    for trade in ordered:
        if float(trade.get("profit_abs", 0) or 0) < 0:
            current.append(trade)
            continue
        if current:
            streaks.append(_streak_summary(current))
            current = []
    if current:
        streaks.append(_streak_summary(current))

    worst_by_count = max(streaks, key=lambda item: item["count"], default=None)
    worst_by_loss = min(streaks, key=lambda item: item["netProfit"], default=None)
    return {
        "maxConsecutiveLosses": worst_by_count["count"] if worst_by_count else 0,
        "worstLossStreakStart": worst_by_count["start"] if worst_by_count else None,
        "worstLossStreakEnd": worst_by_count["end"] if worst_by_count else None,
        "symbolsInWorstLossStreak": worst_by_count["symbols"] if worst_by_count else [],
        "largestLossStreakByNetLoss": worst_by_loss,
        "lossStreaks": streaks[:20],
        "lossStreakCount": len(streaks),
    }


def _streak_summary(streak: list[dict[str, Any]]) -> dict[str, Any]:
    profits = [float(trade.get("profit_abs", 0) or 0) for trade in streak]
    return {
        "count": len(streak),
        "start": streak[0].get("close_date") or streak[0].get("open_date"),
        "end": streak[-1].get("close_date") or streak[-1].get("open_date"),
        "netProfit": _round(_sum(profits), 8),
        "symbols": sorted({str(trade.get("pair")) for trade in streak}),
    }


def _pair_breakdown(source: dict[str, Any], trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for trade in trades:
        grouped[str(trade.get("pair"))].append(trade)

    source_rows = {
        row.get("key"): row
        for row in source.get("results_per_pair", [])
        if isinstance(row, dict) and row.get("key") != "TOTAL"
    }
    rows = []
    for pair, pair_trades in sorted(grouped.items()):
        stats = _trade_stats(pair_trades)
        source_row = source_rows.get(pair, {})
        streak = _max_consecutive_losses(pair_trades)
        rows.append(
            {
                "pair": pair,
                "tradeCount": stats["tradeCount"],
                "winRate": stats["winRate"],
                "netProfitPct": _round(source_row.get("profit_total_pct")),
                "totalProfit": stats["netProfit"],
                "averageWin": stats["averageWin"],
                "averageLoss": stats["averageLoss"],
                "profitFactor": _round(source_row.get("profit_factor") or stats["profitFactor"]),
                "maxDrawdownPct": _round((source_row.get("max_drawdown_account") or 0) * 100),
                "maxConsecutiveLosses": streak["maxConsecutiveLosses"],
                "averageHoldingMinutes": stats["averageHoldingMinutes"],
                "bestTrade": stats["bestTrade"],
                "worstTrade": stats["worstTrade"],
            }
        )
    return rows


def _period_breakdown(source: dict[str, Any], trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    month_rows = source.get("periodic_breakdown", {}).get("month", [])
    if isinstance(month_rows, list) and month_rows:
        return [
            {
                "period": row.get("date"),
                "tradeCount": row.get("trades"),
                "netProfit": _round(row.get("profit_abs"), 8),
                "winRate": _round(
                    (float(row.get("wins", 0) or 0) / float(row.get("trades", 0) or 1)) * 100
                    if row.get("trades")
                    else None
                ),
                "profitFactor": _round(row.get("profit_factor")),
                "wins": row.get("wins"),
                "losses": row.get("losses"),
            }
            for row in month_rows
        ]

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for trade in trades:
        month = str(trade.get("close_date", ""))[:7] or "unknown"
        grouped[month].append(trade)
    return [
        {"period": month, **_trade_stats(month_trades)}
        for month, month_trades in sorted(grouped.items())
    ]


def _exit_reason_breakdown(source: dict[str, Any], trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for trade in trades:
        grouped[str(trade.get("exit_reason", "unknown"))].append(trade)

    source_rows = source.get("exit_reason_summary", [])
    if isinstance(source_rows, list) and source_rows:
        rows = []
        for row in source_rows:
            exit_reason = str(row.get("key"))
            if exit_reason == "TOTAL":
                continue
            grouped_stats = _trade_stats(grouped.get(exit_reason, []))
            rows.append({
                "exitReason": row.get("key"),
                "tradeCount": row.get("trades"),
                "winRate": _round(float(row.get("winrate", 0) or 0) * 100),
                "netProfit": _round(row.get("profit_total_abs"), 8),
                "netProfitPct": _round(row.get("profit_total_pct")),
                "averageProfitPct": _round(row.get("profit_mean_pct")),
                "averageWin": grouped_stats["averageWin"],
                "averageLoss": grouped_stats["averageLoss"],
                "profitFactor": _round(row.get("profit_factor")),
                "durationAvg": row.get("duration_avg"),
            })
        return rows

    return [
        {"exitReason": reason, **_trade_stats(reason_trades)}
        for reason, reason_trades in sorted(grouped.items())
    ]


def _holding_time_breakdown(trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {bucket: [] for bucket in ["0-1h", "1-3h", "3-6h", "6-12h", "12h+"]}
    for trade in trades:
        grouped[_duration_bucket(float(trade.get("trade_duration", 0) or 0))].append(trade)
    return [
        {
            "bucket": bucket,
            "tradeCount": stats["tradeCount"],
            "winRate": stats["winRate"],
            "netProfit": stats["netProfit"],
            "averageProfitPct": stats["averageProfitPct"],
        }
        for bucket, bucket_trades in grouped.items()
        for stats in [_trade_stats(bucket_trades)]
    ]


def _cost_analysis(source: dict[str, Any], trades: list[dict[str, Any]], metrics: dict[str, Any]) -> dict[str, Any]:
    estimated_fees = 0.0
    for trade in trades:
        for order in trade.get("orders", []) or []:
            cost = float(order.get("cost", 0) or 0)
            fee_rate = float(trade.get("fee_open" if order.get("ft_is_entry") else "fee_close", 0) or 0)
            estimated_fees += cost * fee_rate

    profits = [float(trade.get("profit_abs", 0) or 0) for trade in trades]
    gross_profit = sum(value for value in profits if value > 0)
    absolute_pnl = sum(abs(value) for value in profits)

    return {
        "feesAvailable": bool(trades),
        "feesAppliedByFreqtrade": True,
        "estimatedFeesPaidFromOrders": _round(estimated_fees, 8),
        "feesToGrossProfitRatio": _round(estimated_fees / gross_profit if gross_profit else None),
        "feesToAbsolutePnlRatio": _round(estimated_fees / absolute_pnl if absolute_pnl else None),
        "slippageApplied": False,
        "slippageAvailable": False,
        "slippageCost": metrics.get("slippageCost"),
        "netReturnAfterCosts": metrics.get("netReturnAfterCosts"),
        "note": "Freqtrade applied --fee 0.0005. Slippage is documented in the report schema but was not applied by the V13.4 command.",
        "totalVolume": _round(source.get("total_volume"), 8),
    }


def _trade_quality_review(trades: list[dict[str, Any]]) -> dict[str, Any]:
    favorable: list[float] = []
    adverse: list[float] = []
    quick_stop_losses = 0
    near_tp_then_loss = 0
    loss_trades = 0

    for trade in trades:
        open_rate = float(trade.get("open_rate", 0) or 0)
        if open_rate <= 0:
            continue
        max_rate = float(trade.get("max_rate", open_rate) or open_rate)
        min_rate = float(trade.get("min_rate", open_rate) or open_rate)
        favorable_pct = (max_rate - open_rate) / open_rate * 100
        adverse_pct = (min_rate - open_rate) / open_rate * 100
        favorable.append(favorable_pct)
        adverse.append(adverse_pct)
        if float(trade.get("profit_abs", 0) or 0) < 0:
            loss_trades += 1
            if favorable_pct >= 0.5:
                near_tp_then_loss += 1
            if trade.get("exit_reason") == "stop_loss" and float(trade.get("trade_duration", 0) or 0) <= 60:
                quick_stop_losses += 1

    return {
        "mfeMaeAvailable": bool(favorable),
        "averageFavorableExcursionPct": _round(_mean(favorable)),
        "averageAdverseExcursionPct": _round(_mean(adverse)),
        "maxFavorableExcursionPct": _round(max(favorable) if favorable else None),
        "maxAdverseExcursionPct": _round(min(adverse) if adverse else None),
        "lossTradesWithAtLeastHalfPercentFavorableMove": near_tp_then_loss,
        "quickStopLossesWithinOneHour": quick_stop_losses,
        "lossTradeCount": loss_trades,
        "note": "MFE/MAE are approximated from Freqtrade min_rate/max_rate. Exact intratrade path and slippage are unavailable.",
    }


def _build_findings(
    metrics: dict[str, Any],
    pairs: list[dict[str, Any]],
    months: list[dict[str, Any]],
    exits: list[dict[str, Any]],
    holding: list[dict[str, Any]],
    costs: dict[str, Any],
    streaks: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    worst_pair = min(pairs, key=lambda row: row.get("totalProfit") or 0)
    best_pair = max(pairs, key=lambda row: row.get("totalProfit") or 0)
    worst_month = min(months, key=lambda row: row.get("netProfit") or 0)
    worst_exit = min(exits, key=lambda row: row.get("netProfit") or 0)
    worst_holding = min(holding, key=lambda row: row.get("netProfit") or 0)

    findings = [
        {
            "id": "dry_run_blocked",
            "severity": "critical",
            "evidence": {
                "totalReturnPct": metrics.get("totalReturnPct"),
                "profitFactor": metrics.get("profitFactor"),
                "maxDrawdownPct": metrics.get("maxDrawdownPct"),
            },
            "finding": "Current V0.1 smoke backtest is negative and must not enter Dry-run.",
        },
        {
            "id": "loss_concentration_pair",
            "severity": "high",
            "evidence": worst_pair,
            "finding": f"Largest pair-level loss came from {worst_pair['pair']}.",
        },
        {
            "id": "relative_best_pair",
            "severity": "info",
            "evidence": best_pair,
            "finding": f"Best relative pair was {best_pair['pair']}, but it was still negative in this smoke run.",
        },
        {
            "id": "loss_concentration_month",
            "severity": "high",
            "evidence": worst_month,
            "finding": f"Largest monthly loss occurred in period {worst_month['period']}.",
        },
        {
            "id": "exit_reason_loss",
            "severity": "high",
            "evidence": worst_exit,
            "finding": f"Exit reason {worst_exit['exitReason']} contributed the largest net loss.",
        },
        {
            "id": "holding_time_loss",
            "severity": "medium",
            "evidence": worst_holding,
            "finding": f"Holding bucket {worst_holding['bucket']} had the weakest net result.",
        },
        {
            "id": "fees_not_primary_but_material",
            "severity": "medium",
            "evidence": costs,
            "finding": "Fees were applied by Freqtrade and are material for a 15m high-frequency sample; slippage was not applied.",
        },
        {
            "id": "loss_streak_risk",
            "severity": "high",
            "evidence": {
                "maxConsecutiveLosses": streaks.get("maxConsecutiveLosses"),
                "symbols": streaks.get("symbolsInWorstLossStreak"),
            },
            "finding": "Loss streak risk is significant and should be considered before any larger backtest or dry-run.",
        },
    ]

    hypotheses = [
        {
            "id": "macd_exit_may_be_late_or_low_quality",
            "classification": "needs_more_backtest",
            "evidence": [row for row in exits if row.get("exitReason") == "macd_histogram_two_candle_weakness"],
            "hypothesis": "MACD weakness exit may be cutting many trades after damage is already done, or may be too noisy.",
        },
        {
            "id": "stoploss_loss_size_may_overwhelm_roi",
            "classification": "needs_more_backtest",
            "evidence": [row for row in exits if row.get("exitReason") == "stop_loss"],
            "hypothesis": "-3% stoploss losses may be too large relative to +3% ROI and current win rate.",
        },
        {
            "id": "volume_rebound_entry_too_broad",
            "classification": "hypothesis_only",
            "evidence": "Skipped signal instrumentation is unavailable, so filter selectivity cannot be measured yet.",
            "hypothesis": "Entry filters may be admitting too many weak rebound attempts.",
        },
        {
            "id": "pair_specific_behavior",
            "classification": "data_supported",
            "evidence": worst_pair,
            "hypothesis": "SOL was the largest drag in the smoke sample and should be diagnosed separately before Top30 expansion.",
        },
    ]

    v02_ideas = [
        {
            "idea": "Diagnose and possibly strengthen the 4h trend filter.",
            "classification": "needs_more_backtest",
            "evidence": "Filter skip counts are unavailable in V13.4.",
        },
        {
            "idea": "Evaluate a higher volumeRatio threshold or a scored volume confirmation.",
            "classification": "hypothesis_only",
            "evidence": "Entry selectivity cannot be measured without signal audit instrumentation.",
        },
        {
            "idea": "Add a stronger no-chase filter after sharp candles.",
            "classification": "needs_more_backtest",
            "evidence": "Trade quality review has approximate favorable/adverse excursion only.",
        },
        {
            "idea": "Review MACD weakness exit timing against actual loss distribution.",
            "classification": "data_supported",
            "evidence": [row for row in exits if row.get("exitReason") == "macd_histogram_two_candle_weakness"],
        },
        {
            "idea": "Analyze whether -3% stoploss and +3% ROI produce poor payoff at current win rate.",
            "classification": "data_supported",
            "evidence": {"winRate": metrics.get("winRate"), "profitFactor": metrics.get("profitFactor")},
        },
        {
            "idea": "Add signal audit instrumentation before parameter tuning.",
            "classification": "data_supported",
            "evidence": "Filter effectiveness is unavailable in the V13.4 report.",
        },
    ]
    return findings, hypotheses, v02_ideas


def build_diagnosis(source_report_path: Path) -> BacktestDiagnosisReport:
    source_report = _read_json(source_report_path)
    if source_report.get("isMock") is not False:
        raise ValueError(f"Diagnosis requires isMock=false source report: {source_report_path}")

    source_result_value = source_report.get("config", {}).get("sourceResult")
    source_result = Path(source_result_value) if source_result_value else None
    if source_result is None or not source_result.exists():
        raise FileNotFoundError(f"Freqtrade source result not found: {source_result_value}")

    raw_source = _parse_source_result(source_result)
    trades = list(raw_source.get("trades", []))
    metrics = source_report.get("metrics", {})

    trade_stats = _trade_stats(trades)
    overall = {
        "totalTrades": metrics.get("tradeCount") or trade_stats["tradeCount"],
        "winningTrades": trade_stats["winningTrades"],
        "losingTrades": trade_stats["losingTrades"],
        "winRate": metrics.get("winRate") or trade_stats["winRate"],
        "totalReturnPct": metrics.get("totalReturnPct"),
        "maxDrawdownPct": metrics.get("maxDrawdownPct"),
        "profitFactor": metrics.get("profitFactor") or trade_stats["profitFactor"],
        "averageProfitPct": trade_stats["averageProfitPct"],
        "averageWin": trade_stats["averageWin"],
        "averageLoss": trade_stats["averageLoss"],
        "expectancy": _round(raw_source.get("expectancy"), 8),
        "maxConsecutiveLosses": metrics.get("maxConsecutiveLosses") or raw_source.get("max_consecutive_losses"),
        "averageHoldingMinutes": metrics.get("averageHoldingMinutes") or trade_stats["averageHoldingMinutes"],
        "medianHoldingMinutes": trade_stats["medianHoldingMinutes"],
    }

    pairs = _pair_breakdown(raw_source, trades)
    months = _period_breakdown(raw_source, trades)
    exits = _exit_reason_breakdown(raw_source, trades)
    holding = _holding_time_breakdown(trades)
    costs = _cost_analysis(raw_source, trades, metrics)
    streaks = _max_consecutive_losses(trades)
    quality = _trade_quality_review(trades)

    findings, hypotheses, ideas = _build_findings(metrics, pairs, months, exits, holding, costs, streaks)
    warnings = list(source_report.get("reportWarnings", []))
    warnings.extend(
        [
            "Filter effectiveness is unavailable because skipped-signal instrumentation was not present in V13.4.",
            "Slippage was not applied by the V13.4 Freqtrade command.",
            "MFE/MAE values are approximate because only min_rate/max_rate are available.",
        ]
    )

    return BacktestDiagnosisReport(
        reportId="v13_4_1_diagnosis",
        sourceReport=str(source_report_path),
        sourceResult=str(source_result),
        isMock=False,
        strategyId=str(source_report.get("strategyId", "alpha_volume_rebound_v01")),
        timerange=str(source_report.get("timerange", "unknown")),
        pairs=[row["pair"] for row in pairs],
        overall=overall,
        pairBreakdown=pairs,
        monthlyBreakdown=months,
        exitReasonBreakdown=exits,
        holdingTimeBreakdown=holding,
        costAnalysis=costs,
        consecutiveLossAnalysis=streaks,
        filterEffectiveness={
            "filterEffectivenessAvailable": False,
            "reason": "skipped signal instrumentation not available in V13.4",
            "filtersReviewed": FILTERS_REVIEWED,
            "recommendedInstrumentation": [
                "pre-filter signal count",
                "post-filter signal count",
                "skip reason count",
                "per-pair skip reason count",
            ],
        },
        tradeQualityReview=quality,
        diagnosisFindings=findings,
        hypotheses=hypotheses,
        v02CandidateIdeas=ideas,
        doNotChangeYet=DO_NOT_CHANGE_YET,
        warnings=warnings,
        generatedAt=_utc_now(),
    )


def write_summary(report: dict[str, Any], path: Path) -> None:
    overall = report["overall"]
    pairs = report["pairBreakdown"]
    exits = report["exitReasonBreakdown"]
    holding = report["holdingTimeBreakdown"]
    worst_pair = min(pairs, key=lambda row: row.get("totalProfit") or 0)
    worst_exit = min(exits, key=lambda row: row.get("netProfit") or 0)
    worst_holding = min(holding, key=lambda row: row.get("netProfit") or 0)

    lines = [
        "# V13.4.1 Backtest Result Diagnosis Summary",
        "",
        "## Conclusion",
        "",
        "V13.4 pipeline passed, but AlphaPilot Volume Rebound V0.1 must not enter Dry-run.",
        "",
        "## Overall Metrics",
        "",
        f"- Total trades: {overall.get('totalTrades')}",
        f"- Win rate: {overall.get('winRate')}%",
        f"- Total return: {overall.get('totalReturnPct')}%",
        f"- Max drawdown: {overall.get('maxDrawdownPct')}%",
        f"- Profit factor: {overall.get('profitFactor')}",
        f"- Max consecutive losses: {overall.get('maxConsecutiveLosses')}",
        "",
        "## Main Loss Sources",
        "",
        f"- Worst pair: {worst_pair['pair']} ({worst_pair['totalProfit']} USDT, {worst_pair['netProfitPct']}%)",
        f"- Worst exit reason: {worst_exit['exitReason']} ({worst_exit['netProfit']} USDT)",
        f"- Weakest holding bucket: {worst_holding['bucket']} ({worst_holding['netProfit']} USDT)",
        "",
        "## Filter Effectiveness",
        "",
        "Filter effectiveness is unavailable because V13.4 did not include skipped-signal instrumentation.",
        "",
        "## V0.2 Candidate Ideas",
        "",
    ]
    lines.extend(f"- {idea['classification']}: {idea['idea']}" for idea in report["v02CandidateIdeas"])
    lines.extend(
        [
            "",
            "## Do Not Change Yet",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in report["doNotChangeYet"])
    lines.extend(
        [
            "",
            "## Safety",
            "",
            "This diagnosis reads local backtest artifacts only. It does not use API keys, does not call Trade API or Withdraw API, does not read a real account, does not create orders, and does not auto trade.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def export_diagnosis(source_report: Path, output_report: Path, output_summary: Path) -> tuple[Path, Path]:
    diagnosis = build_diagnosis(source_report).to_dict()
    output_report.parent.mkdir(parents=True, exist_ok=True)
    output_report.write_text(json.dumps(diagnosis, ensure_ascii=False, indent=2), encoding="utf-8")
    write_summary(diagnosis, output_summary)
    return output_report, output_summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Diagnose AlphaPilot V13.4 smoke backtest result.")
    parser.add_argument("--report", type=Path, default=DEFAULT_SOURCE_REPORT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_REPORT)
    parser.add_argument("--summary", type=Path, default=DEFAULT_OUTPUT_SUMMARY)
    args = parser.parse_args()

    output_report, output_summary = export_diagnosis(args.report, args.output, args.summary)
    print(f"Exported diagnosis report: {output_report}")
    print(f"Exported diagnosis summary: {output_summary}")


if __name__ == "__main__":
    main()
