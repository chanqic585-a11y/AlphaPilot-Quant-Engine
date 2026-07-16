"""Single frozen event implementation for idiosyncratic selloff recovery."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .execution import simulate_long_event


def _atr(frame: pd.DataFrame, window: int = 14) -> pd.Series:
    previous_close = frame["close"].shift(1)
    true_range = pd.concat(
        [
            frame["high"] - frame["low"],
            (frame["high"] - previous_close).abs(),
            (frame["low"] - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return true_range.rolling(window, min_periods=window).mean()


def _rolling_z(values: pd.Series, window: int) -> pd.Series:
    mean = values.rolling(window, min_periods=window).mean()
    std = values.rolling(window, min_periods=window).std(ddof=0).replace(0, np.nan)
    return (values - mean) / std


def _market_state(market_return: pd.Series, index: int) -> str:
    trailing = float(market_return.iloc[max(0, index - 41) : index + 1].sum())
    if trailing >= 0.10:
        return "bull"
    if trailing <= -0.10:
        return "bear"
    return "range"


def replay_selloff_recovery_events(
    frame: pd.DataFrame,
    *,
    market_return: pd.Series,
    symbol: str,
    residual_z_threshold: float,
    residual_recovery_delta: float,
    market_crash_floor: float,
    atr_stop_multiple: float,
    target_r: float,
    maximum_hold_bars: int,
    round_trip_cost_rate: float,
) -> list[dict[str, Any]]:
    ordered = frame.copy().sort_values("date").reset_index(drop=True)
    ordered = ordered[ordered.get("confirmed", 1).astype(int) == 1].reset_index(
        drop=True
    )
    aligned_market = pd.Series(market_return).reset_index(drop=True).reindex(
        ordered.index
    )
    asset_return = ordered["close"].pct_change()
    residual = asset_return - aligned_market
    residual_z = _rolling_z(residual, 42)
    atr = _atr(ordered, 14)
    market_trailing = aligned_market.rolling(6, min_periods=6).sum()
    market_volatility = aligned_market.rolling(42, min_periods=20).std(ddof=0)
    volatility_threshold = float(market_volatility.dropna().median())
    events: list[dict[str, Any]] = []
    next_available_index = 0
    for index in range(43, len(ordered) - 1):
        if index < next_available_index:
            continue
        previous_z = residual_z.iloc[index - 1]
        current_z = residual_z.iloc[index]
        if pd.isna(previous_z) or pd.isna(current_z) or pd.isna(atr.iloc[index]):
            continue
        previous_midpoint = (
            float(ordered.iloc[index - 1]["high"])
            + float(ordered.iloc[index - 1]["low"])
        ) / 2
        conditions = (
            float(previous_z) <= residual_z_threshold,
            float(current_z - previous_z) >= residual_recovery_delta,
            float(ordered.iloc[index]["close"]) > previous_midpoint,
            float(market_trailing.iloc[index]) > market_crash_floor,
        )
        if not all(conditions):
            continue
        initial_stop = float(ordered.iloc[index]["low"]) - (
            atr_stop_multiple * float(atr.iloc[index])
        )
        try:
            trade = simulate_long_event(
                ordered,
                signal_index=index,
                initial_stop=initial_stop,
                target_r=target_r,
                maximum_hold_bars=maximum_hold_bars,
                round_trip_cost_rate=round_trip_cost_rate,
            )
        except ValueError:
            continue
        volatility_state = (
            "high"
            if float(market_volatility.iloc[index] or 0.0) > volatility_threshold
            else "low"
        )
        events.append(
            {
                **trade,
                "entryTimestamp": pd.Timestamp(
                    ordered.iloc[trade["entryIndex"]]["date"]
                ).isoformat(),
                "exitTimestamp": pd.Timestamp(
                    ordered.iloc[trade["exitIndex"]]["date"]
                ).isoformat(),
                "symbol": symbol,
                "grossR": trade["grossR"],
                "feesR": trade["costR"] * 0.5,
                "spreadProxyR": trade["costR"] * 0.25,
                "slippageR": trade["costR"] * 0.25,
                "fundingR": None,
                "netR": trade["netR"],
                "marketState": _market_state(aligned_market, index),
                "volatilityState": volatility_state,
                "signalScore": abs(float(previous_z)),
            }
        )
        next_available_index = int(trade["exitIndex"]) + 1
    return events

