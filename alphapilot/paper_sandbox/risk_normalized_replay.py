"""Risk-normalized historical replay utilities.

The replay consumes historical signal logs and evaluates fixed portfolio
throttles in R-multiple space. It does not create orders, request exchange
data, use API keys, read accounts, or auto trade.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class RiskPolicy:
    policy_id: str
    description: str
    pair_cooldown_days: int = 0
    exchange_cooldown_hours: int = 0
    global_cooldown_hours: int = 0
    loss_pair_cooldown_days: int = 0
    drawdown_pause_r: float | None = None
    drawdown_pause_days: int = 0


DEFAULT_RISK_POLICIES = [
    RiskPolicy("raw_all_signals", "No portfolio throttling. Diagnostic baseline."),
    RiskPolicy("pair_7d_cooldown", "At most one selected signal per pair every seven days.", pair_cooldown_days=7),
    RiskPolicy("pair_14d_cooldown", "At most one selected signal per pair every fourteen days.", pair_cooldown_days=14),
    RiskPolicy(
        "exchange_24h_pair_7d",
        "At most one signal per exchange per 24 hours and one per pair every seven days.",
        exchange_cooldown_hours=24,
        pair_cooldown_days=7,
    ),
    RiskPolicy(
        "exchange_24h_pair_14d",
        "At most one signal per exchange per 24 hours and one per pair every fourteen days.",
        exchange_cooldown_hours=24,
        pair_cooldown_days=14,
    ),
    RiskPolicy(
        "global_24h_pair_14d",
        "At most one global signal per 24 hours and one per pair every fourteen days.",
        global_cooldown_hours=24,
        pair_cooldown_days=14,
    ),
    RiskPolicy(
        "loss_guard_pair_21d",
        "Seven-day pair cooldown, extended to 21 days after a losing selected trade.",
        pair_cooldown_days=7,
        loss_pair_cooldown_days=21,
    ),
    RiskPolicy(
        "drawdown_guard_12r_pause_14d",
        "Pair seven-day cooldown plus a 14-day global pause after 12R drawdown from equity peak.",
        pair_cooldown_days=7,
        drawdown_pause_r=12.0,
        drawdown_pause_days=14,
    ),
]


def _round(value: Any, digits: int = 6) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return round(number, digits)


def prepare_signal_frame(signals: list[dict[str, Any]]) -> pd.DataFrame:
    frame = pd.DataFrame(signals)
    if frame.empty:
        return frame
    frame["entryDate"] = pd.to_datetime(frame["entryDate"], utc=True, errors="coerce")
    frame["exitDate"] = pd.to_datetime(frame["exitDate"], utc=True, errors="coerce")
    frame["rMultiple"] = pd.to_numeric(frame["rMultiple"], errors="coerce")
    frame = frame.dropna(subset=["entryDate", "rMultiple"]).copy()
    return frame.sort_values(["entryDate", "exchange", "pair"]).reset_index(drop=True)


def _allowed(row: pd.Series, state: dict[str, Any], policy: RiskPolicy) -> bool:
    entry_date = row["entryDate"]
    pair = str(row.get("pair"))
    exchange = str(row.get("exchange"))
    if state.get("global_locked_until") and entry_date < state["global_locked_until"]:
        return False
    if policy.global_cooldown_hours and state.get("last_global") is not None:
        if entry_date < state["last_global"] + timedelta(hours=policy.global_cooldown_hours):
            return False
    if policy.exchange_cooldown_hours:
        last_exchange = state["last_by_exchange"].get(exchange)
        if last_exchange is not None and entry_date < last_exchange + timedelta(hours=policy.exchange_cooldown_hours):
            return False
    last_pair = state["last_by_pair"].get(pair)
    if policy.pair_cooldown_days and last_pair is not None:
        if entry_date < last_pair + timedelta(days=policy.pair_cooldown_days):
            return False
    pair_locked_until = state["pair_locked_until"].get(pair)
    if pair_locked_until is not None and entry_date < pair_locked_until:
        return False
    return True


def _update_state(row: pd.Series, state: dict[str, Any], policy: RiskPolicy, equity_r: float, peak_r: float) -> None:
    entry_date = row["entryDate"]
    pair = str(row.get("pair"))
    exchange = str(row.get("exchange"))
    state["last_global"] = entry_date
    state["last_by_exchange"][exchange] = entry_date
    state["last_by_pair"][pair] = entry_date
    if policy.loss_pair_cooldown_days and float(row["rMultiple"]) <= 0:
        state["pair_locked_until"][pair] = entry_date + timedelta(days=policy.loss_pair_cooldown_days)
    if policy.drawdown_pause_r is not None and policy.drawdown_pause_days > 0:
        drawdown_r = peak_r - equity_r
        if drawdown_r >= policy.drawdown_pause_r:
            state["global_locked_until"] = entry_date + timedelta(days=policy.drawdown_pause_days)


def _metrics(selected: pd.DataFrame) -> dict[str, Any]:
    if selected.empty:
        return {
            "tradeCount": 0,
            "winRatePct": None,
            "profitFactor": None,
            "rewardRiskRatio": None,
            "totalR": 0.0,
            "maxDrawdownR": 0.0,
            "maxConsecutiveLosses": 0,
            "uniquePairs": 0,
            "uniqueExchanges": 0,
        }
    r_values = pd.to_numeric(selected["rMultiple"], errors="coerce").fillna(0.0)
    wins = r_values[r_values > 0]
    losses = r_values[r_values <= 0]
    equity = r_values.cumsum()
    peak = equity.cummax()
    drawdown = peak - equity
    max_consecutive_losses = 0
    current_losses = 0
    for value in r_values:
        if value <= 0:
            current_losses += 1
            max_consecutive_losses = max(max_consecutive_losses, current_losses)
        else:
            current_losses = 0
    return {
        "tradeCount": int(len(selected)),
        "winRatePct": _round((wins.count() / len(selected)) * 100, 4),
        "averageWinR": _round(wins.mean()) if not wins.empty else None,
        "averageLossR": _round(losses.mean()) if not losses.empty else None,
        "profitFactor": _round(wins.sum() / abs(losses.sum())) if abs(losses.sum()) > 0 else None,
        "rewardRiskRatio": _round(wins.mean() / abs(losses.mean())) if not wins.empty and abs(losses.mean()) > 0 else None,
        "totalR": _round(r_values.sum(), 4),
        "maxDrawdownR": _round(drawdown.max(), 4),
        "maxConsecutiveLosses": int(max_consecutive_losses),
        "uniquePairs": int(selected["pair"].nunique()) if "pair" in selected else 0,
        "uniqueExchanges": int(selected["exchange"].nunique()) if "exchange" in selected else 0,
    }


def replay_policy(signals: pd.DataFrame, policy: RiskPolicy) -> tuple[pd.DataFrame, dict[str, Any]]:
    if signals.empty:
        return signals.copy(), _metrics(signals)
    state: dict[str, Any] = {
        "last_global": None,
        "last_by_exchange": {},
        "last_by_pair": {},
        "pair_locked_until": {},
        "global_locked_until": None,
    }
    selected_rows: list[pd.Series] = []
    equity_r = 0.0
    peak_r = 0.0
    for _, row in signals.iterrows():
        if not _allowed(row, state, policy):
            continue
        selected_rows.append(row)
        equity_r += float(row["rMultiple"])
        peak_r = max(peak_r, equity_r)
        _update_state(row, state, policy, equity_r, peak_r)
    selected = pd.DataFrame(selected_rows).reset_index(drop=True) if selected_rows else pd.DataFrame(columns=signals.columns)
    return selected, _metrics(selected)


def evaluate_risk_policies(signals: pd.DataFrame, policies: list[RiskPolicy] | None = None) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for policy in policies or DEFAULT_RISK_POLICIES:
        selected, metrics = replay_policy(signals, policy)
        by_exchange = []
        if not selected.empty and "exchange" in selected:
            for exchange, group in selected.groupby("exchange"):
                row = _metrics(group)
                row["exchange"] = str(exchange)
                by_exchange.append(row)
        output.append(
            {
                "policyId": policy.policy_id,
                "description": policy.description,
                "metrics": metrics,
                "byExchange": sorted(by_exchange, key=lambda item: item.get("tradeCount") or 0, reverse=True),
                "selectedSignals": selected,
            }
        )
    return output
