"""Independent candidate-neutral translation used by the Freqtrade adapter."""

from __future__ import annotations

from typing import Any, Mapping

import numpy as np
import pandas as pd

from alphapilot.evolution.registry.hashing import stable_hash


def _normalize(value: pd.DataFrame) -> pd.DataFrame:
    frame = value.copy()
    if "date" not in frame:
        frame["date"] = frame.index
    frame["date"] = pd.to_datetime(frame["date"], utc=True, errors="coerce")
    frame = frame.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    for column in ("open", "high", "low", "close", "volume"):
        if column not in frame:
            frame[column] = 0.0 if column == "volume" else frame.get("close", 0.0)
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame.dropna(subset=["open", "high", "low", "close"])


def _average_true_range(frame: pd.DataFrame, window: int = 14) -> pd.Series:
    previous = frame["close"].shift(1)
    ranges = pd.concat(
        [
            frame["high"] - frame["low"],
            (frame["high"] - previous).abs(),
            (frame["low"] - previous).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return ranges.rolling(window, min_periods=window).mean()


def _return_panel(frames: Mapping[str, pd.DataFrame]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            symbol: _normalize(raw).set_index("date")["close"].pct_change()
            for symbol, raw in frames.items()
        }
    ).sort_index()


def _translated_mask(
    *,
    setup_id: str,
    frame: pd.DataFrame,
    symbol: str,
    direction: str,
    all_frames: Mapping[str, pd.DataFrame],
) -> pd.Series:
    close = frame["close"]
    returns = close.pct_change()
    ema_fast = close.ewm(span=20, adjust=False).mean()
    ema_slow = close.ewm(span=80, adjust=False).mean()
    rolling_high = close.rolling(20, min_periods=20).max().shift(1)
    rolling_low = close.rolling(20, min_periods=20).min().shift(1)
    volatility_fast = returns.rolling(12, min_periods=12).std()
    volatility_slow = returns.rolling(48, min_periods=24).std()
    atr = _average_true_range(frame)
    prior_atr = atr.shift(1)
    long = direction == "long"

    if setup_id == "trend_pullback_continuation":
        trend = ema_fast > ema_slow if long else ema_fast < ema_slow
        reclaim = (
            (close > ema_fast) & (close.shift(1) <= ema_fast.shift(1))
            if long
            else (close < ema_fast) & (close.shift(1) >= ema_fast.shift(1))
        )
        return trend & reclaim
    if setup_id == "volatility_compression_release":
        compressed = volatility_fast.shift(1) < volatility_slow.shift(1) * 0.75
        breakout = close > rolling_high if long else close < rolling_low
        return compressed & breakout
    if setup_id == "btc_shock_lag":
        btc_raw = all_frames.get("BTC-USDT-SWAP")
        if btc_raw is None or symbol == "BTC-USDT-SWAP":
            return pd.Series(False, index=frame.index)
        btc = _normalize(btc_raw).set_index("date")["close"].pct_change()
        aligned = btc.reindex(frame["date"]).reset_index(drop=True)
        shock = aligned.shift(1) < -0.018 if long else aligned.shift(1) > 0.018
        response = returns > 0 if long else returns < 0
        return shock.fillna(False) & response.fillna(False)
    if setup_id == "volatility_shock_asymmetry":
        threshold = returns.rolling(48, min_periods=24).std().shift(1) * 2.2
        shock = returns.shift(1) < -threshold if long else returns.shift(1) > threshold
        reversal = returns > 0 if long else returns < 0
        return shock & reversal
    if setup_id == "cross_session_liquidity_transition":
        transition = frame["date"].dt.hour.isin([0, 8, 16])
        impulse = close > close.shift(4) if long else close < close.shift(4)
        return transition & impulse
    if setup_id == "residual_extreme_causal_recovery":
        panel = _return_panel(all_frames)
        if symbol not in panel or "BTC-USDT-SWAP" not in panel:
            return pd.Series(False, index=frame.index)
        residual = panel[symbol] - panel["BTC-USDT-SWAP"]
        scale = residual.rolling(72, min_periods=36).std().shift(1)
        event = residual.shift(1) < -2.0 * scale if long else residual.shift(1) > 2.0 * scale
        recovery = residual > 0 if long else residual < 0
        aligned = (event & recovery).reindex(frame["date"]).fillna(False)
        return pd.Series(aligned.to_numpy(), index=frame.index)
    if setup_id == "trend_failure_reversal":
        prior = ema_fast.shift(1) < ema_slow.shift(1) if long else ema_fast.shift(1) > ema_slow.shift(1)
        failure = (
            (close > ema_fast) & (close.shift(1) <= ema_fast.shift(1))
            if long
            else (close < ema_fast) & (close.shift(1) >= ema_fast.shift(1))
        )
        return prior & failure
    if setup_id == "breadth_correlation_directional_filter":
        panel = _return_panel(all_frames)
        breadth = (panel > 0).mean(axis=1)
        regime = breadth >= 0.75 if long else breadth <= 0.25
        aligned = regime.reindex(frame["date"]).fillna(False).reset_index(drop=True)
        local = returns > 0 if long else returns < 0
        return pd.Series(aligned.to_numpy(), index=frame.index) & local
    if setup_id == "range_expansion_close_followthrough":
        bar_range = (frame["high"] - frame["low"]).clip(lower=1e-12)
        close_location = (close - frame["low"]) / bar_range
        expanded = bar_range > prior_atr * 1.4
        directional_close = close_location >= 0.68 if long else close_location <= 0.32
        return expanded & directional_close
    if setup_id == "liquidity_gap_reentry":
        gap = frame["open"] - close.shift(1)
        material_gap = gap < -prior_atr * 0.8 if long else gap > prior_atr * 0.8
        reentry = close > frame["open"] if long else close < frame["open"]
        return material_gap & reentry
    if setup_id == "cross_section_dispersion_leader_followthrough":
        panel = _return_panel(all_frames)
        mean = panel.mean(axis=1)
        scale = panel.std(axis=1, ddof=0).replace(0.0, np.nan)
        z_score = panel.sub(mean, axis=0).div(scale, axis=0)
        if symbol not in z_score:
            return pd.Series(False, index=frame.index)
        event = z_score[symbol] >= 0.8 if long else z_score[symbol] <= -0.8
        aligned = event.reindex(frame["date"]).fillna(False)
        return pd.Series(aligned.to_numpy(), index=frame.index)
    if setup_id == "opening_range_failure_reversal":
        prior_high = frame["high"].rolling(12, min_periods=12).max().shift(2)
        prior_low = frame["low"].rolling(12, min_periods=12).min().shift(2)
        if long:
            return (frame["low"].shift(1) < prior_low) & (close > prior_low)
        return (frame["high"].shift(1) > prior_high) & (close < prior_high)
    raise ValueError(f"unknown_generated_setup:{setup_id}")


def _signal_id(row: Mapping[str, Any]) -> str:
    return stable_hash(
        {
            "candidateId": row["candidateId"],
            "symbol": row["symbol"],
            "direction": row["direction"],
            "signalTimestamp": row["signalTimestamp"],
            "expectedEntryTimestamp": row["expectedEntryTimestamp"],
        },
        prefix="generated_directional_event_signal",
    )


def translated_load_signals(
    *, candidate: Mapping[str, Any], frames: Mapping[str, pd.DataFrame]
) -> list[dict[str, Any]]:
    setup_id = str(candidate["entryDefinition"]["setupId"])
    direction = str(candidate["direction"])
    rows: list[dict[str, Any]] = []
    for symbol in sorted(frames):
        frame = _normalize(frames[symbol])
        mask = _translated_mask(
            setup_id=setup_id,
            frame=frame,
            symbol=symbol,
            direction=direction,
            all_frames=frames,
        ).fillna(False)
        minimum_index = int(candidate.get("rankingLookbackBars") or 0)
        for index in frame.index[mask]:
            if index < minimum_index:
                continue
            if index + 1 >= len(frame):
                continue
            signal_time = frame.at[index, "date"].isoformat()
            entry_time = frame.at[index + 1, "date"].isoformat()
            row = {
                "candidateId": str(candidate["candidateId"]),
                "symbol": symbol,
                "instrumentId": symbol,
                "direction": direction,
                "signalTimestamp": signal_time,
                "entryTimestamp": entry_time,
                "expectedEntryTimestamp": entry_time,
                "entryPrice": float(frame.at[index + 1, "open"]),
                "signalBarIndex": int(index),
                "structuralOnly": True,
                "economicResultComputationDisabled": True,
                "exitReplayDisabled": True,
                "setupId": setup_id,
            }
            row["signalId"] = _signal_id(row)
            rows.append(row)
    return rows


def translated_replay(
    *,
    candidate: Mapping[str, Any],
    frames: Mapping[str, pd.DataFrame],
    round_trip_cost_rate: float,
) -> list[dict[str, Any]]:
    signals = translated_load_signals(candidate=candidate, frames=frames)
    maximum_hold = int(candidate["maximumHoldBars"])
    stop_multiple = float(candidate["initialStop"]["atrMultiple"])
    target_multiple = float(candidate["exitPolicy"].get("targetR", 1.5))
    direction = str(candidate["direction"])
    normalized = {symbol: _normalize(frame) for symbol, frame in frames.items()}
    rows: list[dict[str, Any]] = []
    for signal in signals:
        frame = normalized[str(signal["symbol"])]
        entry_index = int(signal["signalBarIndex"]) + 1
        if entry_index >= len(frame) - 1:
            continue
        atr = _average_true_range(frame).iloc[entry_index]
        if not np.isfinite(atr) or atr <= 0:
            continue
        entry = float(frame.at[entry_index, "open"])
        risk = float(atr) * stop_multiple
        stop = entry - risk if direction == "long" else entry + risk
        target = entry + target_multiple * risk if direction == "long" else entry - target_multiple * risk
        final_index = min(entry_index + maximum_hold, len(frame) - 1)
        exit_index = final_index
        exit_price = float(frame.at[final_index, "close"])
        exit_reason = "maximum_hold"
        for cursor in range(entry_index, final_index + 1):
            high = float(frame.at[cursor, "high"])
            low = float(frame.at[cursor, "low"])
            if (direction == "long" and low <= stop) or (direction == "short" and high >= stop):
                exit_index, exit_price, exit_reason = cursor, stop, "initial_stop"
                break
            if (direction == "long" and high >= target) or (direction == "short" and low <= target):
                exit_index, exit_price, exit_reason = cursor, target, "advisory_r_target"
                break
        gross_r = (exit_price - entry) / risk * (1.0 if direction == "long" else -1.0)
        cost_r = entry * float(round_trip_cost_rate) / risk
        observed = frame.iloc[entry_index : exit_index + 1]
        if direction == "long":
            mfe_r = (float(observed["high"].max()) - entry) / risk
            mae_r = (float(observed["low"].min()) - entry) / risk
        else:
            mfe_r = (entry - float(observed["low"].min())) / risk
            mae_r = (entry - float(observed["high"].max())) / risk
        rows.append(
            {
                **signal,
                "exitTimestamp": frame.at[exit_index, "date"].isoformat(),
                "exitPrice": exit_price,
                "exitReason": exit_reason,
                "initialStopPrice": stop,
                "grossR": gross_r,
                "costR": cost_r,
                "netR": gross_r - cost_r,
                "mfeR": mfe_r,
                "maeR": mae_r,
            }
        )
    return rows


__all__ = ["translated_load_signals", "translated_replay"]
