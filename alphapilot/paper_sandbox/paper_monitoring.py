"""Local paper monitoring analytics.

This module reads local paper sandbox ledger rows and produces monitoring
metrics. It is local-only: no exchange API, no account reads, no orders, and no
automatic trading.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pandas as pd


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _round(value: float | None, digits: int = 6) -> float | None:
    if value is None:
        return None
    return round(float(value), digits)


def _to_timestamp(value: Any) -> pd.Timestamp | None:
    if value is None:
        return None
    timestamp = pd.to_datetime(value, utc=True, errors="coerce")
    if pd.isna(timestamp):
        return None
    return timestamp


def _max_drawdown_pct(equity_values: list[float]) -> float:
    if not equity_values:
        return 0.0
    peak = equity_values[0]
    max_drawdown = 0.0
    for value in equity_values:
        peak = max(peak, value)
        if peak <= 0:
            continue
        max_drawdown = max(max_drawdown, (peak - value) / peak * 100)
    return round(max_drawdown, 6)


def _max_consecutive_losses(fills: list[dict[str, Any]]) -> int:
    longest = 0
    current = 0
    for fill in fills:
        pnl = float(fill.get("pnl") or 0)
        if pnl < 0:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest


def metrics_from_fills(fills: list[dict[str, Any]], initial_equity: float = 10_000.0) -> dict[str, Any]:
    closed = [fill for fill in fills if fill.get("status") == "closed"]
    wins = [fill for fill in closed if float(fill.get("pnl") or 0) > 0]
    losses = [fill for fill in closed if float(fill.get("pnl") or 0) < 0]
    total_pnl = sum(float(fill.get("pnl") or 0) for fill in closed)
    average_win = sum(float(fill.get("pnl") or 0) for fill in wins) / len(wins) if wins else None
    average_loss = sum(float(fill.get("pnl") or 0) for fill in losses) / len(losses) if losses else None
    reward_risk = (average_win / abs(average_loss)) if average_win is not None and average_loss and average_loss < 0 else None
    gross_profit = sum(float(fill.get("pnl") or 0) for fill in wins)
    gross_loss = abs(sum(float(fill.get("pnl") or 0) for fill in losses))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else None
    equity = initial_equity
    equity_values = [equity]
    for fill in closed:
        equity += float(fill.get("pnl") or 0)
        equity_values.append(equity)
    return {
        "tradeCount": len(closed),
        "winCount": len(wins),
        "lossCount": len(losses),
        "winRatePct": _round(len(wins) / len(closed) * 100, 4) if closed else None,
        "averageWin": _round(average_win),
        "averageLoss": _round(average_loss),
        "rewardRiskRatio": _round(reward_risk, 4),
        "profitFactor": _round(profit_factor, 4),
        "totalPnl": _round(total_pnl),
        "totalReturnPct": _round(total_pnl / initial_equity * 100, 4) if initial_equity > 0 else None,
        "maxDrawdownPct": _max_drawdown_pct(equity_values),
        "maxConsecutiveLosses": _max_consecutive_losses(closed),
    }


def rolling_trade_windows(fills: list[dict[str, Any]], windows: list[int] | None = None) -> list[dict[str, Any]]:
    ordered = sorted(
        [fill for fill in fills if fill.get("status") == "closed"],
        key=lambda fill: str(fill.get("closedAt") or fill.get("exitDate") or ""),
    )
    result = []
    for window in windows or [5, 10, 20, 30, 40]:
        sample = ordered[-window:] if len(ordered) >= window else ordered[:]
        result.append(
            {
                "windowTradeCount": window,
                "availableTradeCount": len(sample),
                "metrics": metrics_from_fills(sample),
            }
        )
    return result


def monthly_fill_breakdown(fills: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = {}
    for fill in fills:
        closed_at = _to_timestamp(fill.get("closedAt") or fill.get("exitDate"))
        if closed_at is None:
            continue
        buckets.setdefault(closed_at.strftime("%Y-%m"), []).append(fill)
    return [
        {"month": month, **metrics_from_fills(rows)}
        for month, rows in sorted(buckets.items(), key=lambda item: item[0])
    ]


def pair_breakdown(fills: list[dict[str, Any]], limit: int = 20) -> list[dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = {}
    for fill in fills:
        pair = str(fill.get("pair") or "unknown")
        buckets.setdefault(pair, []).append(fill)
    rows = [{"pair": pair, **metrics_from_fills(group)} for pair, group in buckets.items()]
    return sorted(rows, key=lambda row: (row.get("tradeCount") or 0, row.get("totalPnl") or 0), reverse=True)[:limit]


def skip_reason_breakdown(skipped_signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for row in skipped_signals:
        reason = str(row.get("reason") or "unknown")
        counts[reason] = counts.get(reason, 0) + 1
    return [{"reason": reason, "count": count} for reason, count in sorted(counts.items())]


def freshness_summary(
    signal_rows: list[dict[str, Any]],
    fills: list[dict[str, Any]],
    generated_at: str | None = None,
) -> dict[str, Any]:
    now = _to_timestamp(generated_at) or pd.Timestamp.now(tz=UTC)
    signal_times = [
        timestamp
        for timestamp in (_to_timestamp(row.get("entryDate") or row.get("signalDate")) for row in signal_rows)
        if timestamp is not None
    ]
    fill_times = [
        timestamp
        for timestamp in (_to_timestamp(row.get("closedAt") or row.get("exitDate")) for row in fills)
        if timestamp is not None
    ]
    latest_signal = max(signal_times) if signal_times else None
    latest_fill = max(fill_times) if fill_times else None
    signal_age_days = (now - latest_signal).total_seconds() / 86400 if latest_signal is not None else None
    fill_age_days = (now - latest_fill).total_seconds() / 86400 if latest_fill is not None else None
    fill_lag_days = (
        (latest_signal - latest_fill).total_seconds() / 86400
        if latest_signal is not None and latest_fill is not None
        else None
    )
    return {
        "latestSignalAt": latest_signal.isoformat() if latest_signal is not None else None,
        "latestClosedFillAt": latest_fill.isoformat() if latest_fill is not None else None,
        "signalAgeDays": _round(signal_age_days, 3),
        "closedFillAgeDays": _round(fill_age_days, 3),
        "signalToClosedFillLagDays": _round(fill_lag_days, 3),
        "signalFresh": signal_age_days is not None and signal_age_days <= 5,
        "closedFillFresh": fill_age_days is not None and fill_age_days <= 5,
    }


def monitoring_decision(
    full_metrics: dict[str, Any],
    rolling_windows: list[dict[str, Any]],
    freshness: dict[str, Any],
    skipped_breakdown: list[dict[str, Any]],
) -> dict[str, Any]:
    fail_reasons: list[str] = []
    warning_reasons: list[str] = []

    if (full_metrics.get("tradeCount") or 0) < 40:
        fail_reasons.append("total_trade_count_below_40")
    if (full_metrics.get("winRatePct") or 0) < 55:
        fail_reasons.append("total_win_rate_below_55")
    if (full_metrics.get("rewardRiskRatio") or 0) < 1.5:
        fail_reasons.append("total_reward_risk_below_1_5")
    if (full_metrics.get("profitFactor") or 0) < 1.35:
        fail_reasons.append("total_profit_factor_below_1_35")
    if (full_metrics.get("maxDrawdownPct") or 999) > 20:
        fail_reasons.append("total_drawdown_above_20")

    latest_20 = next((item for item in rolling_windows if item.get("windowTradeCount") == 20), None)
    latest_10 = next((item for item in rolling_windows if item.get("windowTradeCount") == 10), None)
    if latest_20 and (latest_20.get("availableTradeCount") or 0) >= 20:
        metrics = latest_20.get("metrics") or {}
        if (metrics.get("winRatePct") or 0) < 55:
            warning_reasons.append("recent_20_win_rate_below_55")
        if (metrics.get("rewardRiskRatio") or 0) < 1.5:
            warning_reasons.append("recent_20_reward_risk_below_1_5")
        if (metrics.get("profitFactor") or 0) < 1.35:
            warning_reasons.append("recent_20_profit_factor_below_1_35")
    if latest_10 and (latest_10.get("availableTradeCount") or 0) >= 10:
        metrics = latest_10.get("metrics") or {}
        if (metrics.get("winRatePct") or 0) < 50:
            warning_reasons.append("recent_10_win_rate_below_50")
        if (metrics.get("profitFactor") or 0) < 1.1:
            warning_reasons.append("recent_10_profit_factor_below_1_1")

    if not freshness.get("signalFresh"):
        warning_reasons.append("signal_log_not_fresh")
    if not freshness.get("closedFillFresh"):
        warning_reasons.append("closed_fill_not_fresh")
    if (freshness.get("signalToClosedFillLagDays") or 0) > 5:
        warning_reasons.append("approved_signal_to_fill_lag_above_5_days")
    if any(row.get("reason") == "max_concurrent_positions_reached" for row in skipped_breakdown):
        warning_reasons.append("some_approved_signals_skipped_by_concurrency")

    health = "healthy"
    if fail_reasons:
        health = "blocked"
    elif warning_reasons:
        health = "watch"

    return {
        "localPaperMonitoringActive": len(fail_reasons) == 0,
        "monitoringHealth": health,
        "continueLocalPaperMonitoring": len(fail_reasons) == 0,
        "exchangeDryRunReviewReady": False,
        "liveTradingApproved": False,
        "failReasons": fail_reasons,
        "warningReasons": warning_reasons,
        "reason": (
            "local_paper_monitoring_continues_with_decay_warnings"
            if health == "watch"
            else "local_paper_monitoring_healthy"
            if health == "healthy"
            else "local_paper_monitoring_blocked"
        ),
    }
