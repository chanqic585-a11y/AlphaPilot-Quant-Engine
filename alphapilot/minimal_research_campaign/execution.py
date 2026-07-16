"""Conservative next-bar event execution with frozen initial risk."""

from __future__ import annotations

from typing import Any

import pandas as pd


def simulate_long_event(
    frame: pd.DataFrame,
    *,
    signal_index: int,
    initial_stop: float,
    target_r: float,
    maximum_hold_bars: int,
    round_trip_cost_rate: float,
) -> dict[str, Any]:
    if round_trip_cost_rate <= 0:
        raise ValueError("round-trip cost assumption must be positive")
    if target_r < 2:
        raise ValueError("target_r must be at least 2R")
    entry_index = signal_index + 1
    if entry_index >= len(frame):
        raise ValueError("signal has no next bar for execution")
    entry = float(frame.iloc[entry_index]["open"])
    risk = entry - float(initial_stop)
    if risk <= 0:
        raise ValueError("long initial stop must be below next-bar entry")
    target = entry + target_r * risk
    partial_target = entry + risk
    last_index = min(len(frame) - 1, entry_index + maximum_hold_bars - 1)
    partial_fraction = 0.0
    gross_r = 0.0
    exit_price = float(frame.iloc[last_index]["close"])
    exit_reason = "time_exit"
    for index in range(entry_index, last_index + 1):
        row = frame.iloc[index]
        low = float(row["low"])
        high = float(row["high"])
        if low <= initial_stop:
            remaining = 1.0 - partial_fraction
            gross_r += remaining * -1.0
            exit_price = float(initial_stop)
            exit_reason = "initial_stop"
            last_index = index
            break
        if partial_fraction == 0.0 and high >= partial_target:
            partial_fraction = 0.5
            gross_r += 0.5
        if high >= target:
            remaining = 1.0 - partial_fraction
            gross_r += remaining * target_r
            exit_price = target
            exit_reason = "target"
            last_index = index
            break
    else:
        remaining = 1.0 - partial_fraction
        gross_r += remaining * ((exit_price - entry) / risk)
    cost_r = entry * round_trip_cost_rate / risk
    return {
        "signalIndex": signal_index,
        "entryIndex": entry_index,
        "exitIndex": last_index,
        "entryPrice": entry,
        "exitPrice": exit_price,
        "initialStop": float(initial_stop),
        "stopHistory": [float(initial_stop)] * (last_index - entry_index + 1),
        "targetPrice": target,
        "targetR": target_r,
        "partialExitFraction": partial_fraction,
        "grossR": gross_r,
        "costR": cost_r,
        "netR": gross_r - cost_r,
        "exitReason": exit_reason,
        "nextBarExecution": True,
        "initialStopMayWiden": False,
    }
