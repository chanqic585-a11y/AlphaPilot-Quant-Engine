"""Independent translated TSMOM replay used for exact Formal parity."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

from .tsmom_engine import TsmomReplayError, atr, normalize_tsmom_frame


def _translated_trade(
    *,
    candidate: Mapping[str, Any],
    frame: pd.DataFrame,
    symbol: str,
    signal_index: int,
    direction: int,
    volatility: float,
    exit_mask: pd.Series,
    round_trip_cost_rate: float,
) -> tuple[dict[str, Any] | None, int]:
    definition = dict(candidate["definition"])
    entry_index = signal_index + 1
    if entry_index >= len(frame) - 1 or not np.isfinite(volatility) or volatility <= 0:
        return None, signal_index + 1
    entry = float(frame.iloc[entry_index]["open"])
    risk = volatility * float(definition["stopAtr"])
    if risk <= 0 or risk / entry > 0.25:
        return None, entry_index + 1
    stop = entry - direction * risk
    terminal = min(
        len(frame) - 1,
        entry_index + int(definition["maximumHoldBars"]),
    )
    exit_index = terminal
    trigger_index = terminal
    exit_price = float(frame.iloc[terminal]["close"])
    reason = "maximum_hold"
    mfe = 0.0
    mae = 0.0
    for cursor in range(entry_index, terminal + 1):
        high = float(frame.iloc[cursor]["high"])
        low = float(frame.iloc[cursor]["low"])
        favorable = high - entry if direction > 0 else entry - low
        adverse = low - entry if direction > 0 else entry - high
        mfe = max(mfe, favorable / risk)
        mae = min(mae, adverse / risk)
        if (direction > 0 and low <= stop) or (direction < 0 and high >= stop):
            exit_index = cursor
            trigger_index = cursor
            exit_price = stop
            reason = "initial_stop"
            break
        if bool(exit_mask.iloc[cursor]):
            trigger_index = cursor
            exit_index = min(cursor + 1, len(frame) - 1)
            exit_price = float(frame.iloc[exit_index]["open"])
            reason = "donchian_reversal"
            break
    gross_r = direction * (exit_price - entry) / risk
    fee_r = float(round_trip_cost_rate) * entry / risk
    funding_r = (
        -direction
        * float(frame.loc[entry_index:exit_index, "fundingRate"].sum())
        * entry
        / risk
    )
    timestamp = lambda index: pd.Timestamp(frame.iloc[index]["date"]).isoformat()
    return (
        {
            "candidateId": str(candidate["candidateId"]),
            "instrumentId": symbol,
            "symbol": symbol,
            "direction": "long" if direction > 0 else "short",
            "signalTimestamp": timestamp(signal_index),
            "signalIndex": int(signal_index),
            "entryTimestamp": timestamp(entry_index),
            "entryIndex": int(entry_index),
            "expectedEntryTimestamp": timestamp(entry_index),
            "exitTriggerTimestamp": timestamp(trigger_index),
            "exitTimestamp": timestamp(exit_index),
            "exitIndex": int(exit_index),
            "entryPrice": entry,
            "exitPrice": exit_price,
            "riskDistance": float(risk),
            "initialStop": stop,
            "initialStopPrice": stop,
            "stopPrice": stop,
            "grossR": float(gross_r),
            "costR": float(fee_r),
            "fundingR": float(funding_r),
            "netR": float(gross_r - fee_r + funding_r),
            "mfeR": float(mfe),
            "maeR": float(mae),
            "exitReason": reason,
            "signalBarIndex": int(signal_index),
            "setupId": "tsmom_turtle",
            "exitPolicyHash": str(candidate["exitPolicyHash"]),
        },
        exit_index + 1,
    )


def translated_replay_tsmom_events(
    *,
    candidate: Mapping[str, Any],
    frames: Mapping[str, pd.DataFrame],
    round_trip_cost_rate: float,
) -> Sequence[Mapping[str, Any]]:
    """Replay via an independent signal loop while preserving frozen semantics."""

    if not np.isfinite(round_trip_cost_rate) or round_trip_cost_rate < 0:
        raise TsmomReplayError("round_trip_cost_invalid")
    definition = dict(candidate["definition"])
    events: list[dict[str, Any]] = []
    for symbol in tuple(str(value) for value in candidate["universe"]):
        if symbol not in frames:
            raise TsmomReplayError(f"market_frame_missing:{symbol}")
        frame = normalize_tsmom_frame(frames[symbol], symbol=symbol)
        momentum = (
            frame["close"]
            .pct_change(int(definition["lookbackBars"]))
        )
        entry_window = int(definition["entryDonchianBars"])
        exit_window = int(definition["exitDonchianBars"])
        prior_high = frame["high"].shift(1).rolling(entry_window).max()
        prior_low = frame["low"].shift(1).rolling(entry_window).min()
        exit_high = frame["high"].shift(1).rolling(exit_window).max()
        exit_low = frame["low"].shift(1).rolling(exit_window).min()
        threshold = float(definition["minimumMomentum"])
        long_entries = ((momentum >= threshold) & (frame["close"] > prior_high)).fillna(False)
        short_entries = ((momentum <= -threshold) & (frame["close"] < prior_low)).fillna(False)
        volatility = atr(frame, int(definition["atrBars"]))
        available_from = 0
        for signal_index in range(len(frame)):
            if signal_index < available_from:
                continue
            if not bool(long_entries.iloc[signal_index]) and not bool(
                short_entries.iloc[signal_index]
            ):
                continue
            direction = 1 if bool(long_entries.iloc[signal_index]) else -1
            exit_mask = (
                frame["close"] < exit_low
                if direction > 0
                else frame["close"] > exit_high
            ).fillna(False)
            event, available_from = _translated_trade(
                candidate=candidate,
                frame=frame,
                symbol=symbol,
                signal_index=signal_index,
                direction=direction,
                volatility=float(volatility.iloc[signal_index]),
                exit_mask=exit_mask,
                round_trip_cost_rate=float(round_trip_cost_rate),
            )
            if event is not None:
                events.append(event)
    return sorted(
        events,
        key=lambda row: (
            str(row["signalTimestamp"]),
            str(row["symbol"]),
            str(row["direction"]),
        ),
    )


__all__ = ["translated_replay_tsmom_events"]
