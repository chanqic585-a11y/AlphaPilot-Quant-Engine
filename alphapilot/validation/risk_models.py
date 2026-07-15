from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Iterable


def _period(timestamp_ms: int, pattern: str) -> str:
    return datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc).strftime(pattern)


def simulate_account_path(
    trades: Iterable[dict[str, Any]],
    *,
    model: dict[str, Any],
    initial_equity: float = 100.0,
) -> dict[str, Any]:
    ordered = sorted(
        (dict(row) for row in trades),
        key=lambda row: (int(row.get("entryTimestampMs") or 0), str(row.get("instrumentId") or "")),
    )
    risk_pct = float(model["riskPerTradePct"])
    max_open = float(model.get("maximumOpenRiskPct", risk_pct))
    max_positions = int(model.get("maximumConcurrentPositions", 1))
    max_symbol = float(model.get("maximumSymbolRiskPct", risk_pct))
    max_cluster = float(model.get("maximumDirectionalClusterRiskPct", max_open))
    daily_pause = float(model.get("dailyNewRiskPausePct", -100.0))
    stop_pct = float(model.get("drawdownResearchStopPct", 100.0))

    equity = peak = float(initial_equity)
    maximum_drawdown_pct = maximum_drawdown_value = 0.0
    maximum_drawdown_duration_ms = 0
    peak_timestamp = int(ordered[0].get("entryTimestampMs") or 0) if ordered else 0
    open_positions: list[dict[str, Any]] = []
    skip_reasons: Counter[str] = Counter()
    realised_by_day: dict[str, float] = defaultdict(float)
    realised_by_week: dict[str, float] = defaultdict(float)
    realised_by_month: dict[str, float] = defaultdict(float)
    maximum_open_risk = maximum_cluster_risk = 0.0
    maximum_concurrent = 0
    risk_stop_active = False
    risk_stop_trigger_count = 0
    accepted = 0
    closed_values: list[float] = []

    def close_due(timestamp: int, *, close_all: bool = False) -> None:
        nonlocal equity, peak, peak_timestamp
        nonlocal maximum_drawdown_pct, maximum_drawdown_value
        nonlocal maximum_drawdown_duration_ms, risk_stop_active
        nonlocal risk_stop_trigger_count
        remaining: list[dict[str, Any]] = []
        for position in sorted(open_positions, key=lambda item: item["exitTimestampMs"]):
            if not close_all and position["exitTimestampMs"] > timestamp:
                remaining.append(position)
                continue
            pnl = position["riskAmount"] * position["netR"]
            equity += pnl
            closed_values.append(position["netR"])
            exit_time = position["exitTimestampMs"]
            realised_by_day[_period(exit_time, "%Y-%m-%d")] += pnl
            realised_by_week[_period(exit_time, "%G-W%V")] += pnl
            realised_by_month[_period(exit_time, "%Y-%m")] += pnl
            if equity > peak:
                peak = equity
                peak_timestamp = exit_time
            drawdown_value = peak - equity
            drawdown_pct = drawdown_value / peak * 100 if peak else 0.0
            if drawdown_pct > maximum_drawdown_pct:
                maximum_drawdown_pct = drawdown_pct
                maximum_drawdown_value = drawdown_value
                maximum_drawdown_duration_ms = max(
                    maximum_drawdown_duration_ms, exit_time - peak_timestamp
                )
            if drawdown_pct >= stop_pct and not risk_stop_active:
                risk_stop_active = True
                risk_stop_trigger_count += 1
        open_positions[:] = remaining

    for row in ordered:
        entry_time = int(row.get("entryTimestampMs") or 0)
        close_due(entry_time)
        if risk_stop_active:
            skip_reasons["drawdown_research_stop"] += 1
            continue
        day = _period(entry_time, "%Y-%m-%d")
        if realised_by_day[day] / initial_equity * 100 <= daily_pause:
            skip_reasons["daily_new_risk_pause"] += 1
            continue
        instrument = str(row.get("instrumentId") or "unknown")
        direction = str(row.get("direction") or "unknown")
        applied_risk_pct = risk_pct
        if model.get("highBetaRiskDiscount") and not instrument.startswith(
            ("BTC-", "ETH-", "SOL-")
        ):
            applied_risk_pct *= 0.5
        current_open = sum(float(item["riskPct"]) for item in open_positions)
        symbol_open = sum(
            float(item["riskPct"])
            for item in open_positions
            if item["instrumentId"] == instrument
        )
        cluster_open = sum(
            float(item["riskPct"])
            for item in open_positions
            if item["direction"] == direction
        )
        if len(open_positions) >= max_positions:
            skip_reasons["maximum_concurrent_positions"] += 1
            continue
        if current_open + applied_risk_pct > max_open + 1e-12:
            skip_reasons["maximum_open_risk"] += 1
            continue
        if symbol_open + applied_risk_pct > max_symbol + 1e-12:
            skip_reasons["maximum_symbol_risk"] += 1
            continue
        if cluster_open + applied_risk_pct > max_cluster + 1e-12:
            skip_reasons["maximum_directional_cluster_risk"] += 1
            continue
        open_positions.append(
            {
                "instrumentId": instrument,
                "direction": direction,
                "riskPct": applied_risk_pct,
                "riskAmount": equity * applied_risk_pct / 100,
                "netR": float(row.get("netR") or 0),
                "exitTimestampMs": int(row.get("exitTimestampMs") or entry_time),
            }
        )
        accepted += 1
        maximum_open_risk = max(maximum_open_risk, current_open + applied_risk_pct)
        maximum_cluster_risk = max(
            maximum_cluster_risk, cluster_open + applied_risk_pct
        )
        maximum_concurrent = max(maximum_concurrent, len(open_positions))

    close_due(2**63 - 1, close_all=True)

    def maximum_loss(values: dict[str, float]) -> float:
        return min(values.values(), default=0.0) / initial_equity * 100

    losses = current_loss_run = maximum_loss_run = 0
    for value in closed_values:
        current_loss_run = current_loss_run + 1 if value < 0 else 0
        maximum_loss_run = max(maximum_loss_run, current_loss_run)
        losses += int(value < 0)
    return {
        "initialEquity": initial_equity,
        "finalEquity": round(equity, 10),
        "totalReturnPct": round((equity / initial_equity - 1) * 100, 10),
        "acceptedTradeCount": accepted,
        "skippedTradeCount": sum(skip_reasons.values()),
        "skipReasons": dict(sorted(skip_reasons.items())),
        "maximumDrawdownPct": round(maximum_drawdown_pct, 10),
        "maximumDrawdownR": (
            round(maximum_drawdown_value / (initial_equity * risk_pct / 100), 10)
            if risk_pct
            else None
        ),
        "maximumDrawdownDurationDays": round(
            maximum_drawdown_duration_ms / 86_400_000, 6
        ),
        "longestRecoveryDays": round(
            maximum_drawdown_duration_ms / 86_400_000, 6
        ),
        "maximumConsecutiveLosses": maximum_loss_run,
        "lossTradeCount": losses,
        "maximumConcurrentPositions": maximum_concurrent,
        "maximumOpenRiskPct": round(maximum_open_risk, 10),
        "maximumDirectionalClusterRiskPct": round(maximum_cluster_risk, 10),
        "maximumDailyLossPct": round(maximum_loss(realised_by_day), 10),
        "maximumWeeklyLossPct": round(maximum_loss(realised_by_week), 10),
        "maximumMonthlyLossPct": round(maximum_loss(realised_by_month), 10),
        "riskStopTriggerCount": risk_stop_trigger_count,
        "leverageCanIncreaseAllowedLoss": False,
        "averagingDown": False,
        "martingale": False,
        "grid": False,
    }
