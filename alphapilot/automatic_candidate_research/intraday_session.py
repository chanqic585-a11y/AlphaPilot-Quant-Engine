"""Causal intraday-session research for the bounded V36.5 campaign."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd


_SYMBOLS = ("BTC-USDT-SWAP", "ETH-USDT-SWAP", "SOL-USDT-SWAP")


def _profit_factor(values: Sequence[float]) -> float:
    positive = sum(value for value in values if value > 0)
    negative = abs(sum(value for value in values if value < 0))
    if negative > 0:
        return float(positive / negative)
    return 10.0 if positive > 0 else 0.0


def _drawdown(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    equity = np.cumsum(np.asarray(values, dtype=float))
    peaks = np.maximum.accumulate(np.concatenate(([0.0], equity)))[:-1]
    return float(np.max(peaks - equity))


def _atr(frame: pd.DataFrame, window: int) -> pd.Series:
    previous = frame["close"].shift(1)
    true_range = pd.concat(
        [
            frame["high"] - frame["low"],
            (frame["high"] - previous).abs(),
            (frame["low"] - previous).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return true_range.rolling(window, min_periods=window).mean()


def build_session_signal_table(
    frame: pd.DataFrame,
    *,
    lookback_sessions: int,
    minimum_session_mean: float,
    adaptation: bool,
    session_hours: int = 8,
    minimum_volume_ratio: float = 0.8,
    maximum_volume_ratio: float = 2.5,
    maximum_realized_volatility: float = 0.04,
) -> pd.DataFrame:
    """Build signals from prior completed occurrences of three fixed UTC sessions."""

    if session_hours <= 0 or 24 % session_hours:
        raise ValueError("session_hours_must_divide_day")
    if lookback_sessions < 3:
        raise ValueError("lookback_sessions_too_short")
    required = {"date", "open", "high", "low", "close", "volume"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"intraday_frame_column_missing:{missing[0]}")

    bars = frame.copy().sort_values("date").reset_index(drop=True)
    bars["date"] = pd.to_datetime(bars["date"], utc=True, errors="coerce")
    if bars["date"].isna().any():
        raise ValueError("intraday_frame_timestamp_invalid")
    bars["rowIndex"] = np.arange(len(bars), dtype=int)
    bars["sessionStart"] = bars["date"].dt.floor(f"{session_hours}h")
    bars["sessionId"] = (bars["date"].dt.hour // session_hours).astype(int)

    sessions = (
        bars.groupby(["sessionStart", "sessionId"], as_index=False)
        .agg(
            startIndex=("rowIndex", "min"),
            endIndex=("rowIndex", "max"),
            barCount=("rowIndex", "count"),
            sessionOpen=("open", "first"),
            sessionClose=("close", "last"),
        )
        .sort_values("sessionStart")
        .reset_index(drop=True)
    )
    sessions["sessionReturn"] = (
        sessions["sessionClose"] / sessions["sessionOpen"] - 1.0
    )
    sessions["historicalMean"] = np.nan
    for _session_id, indices in sessions.groupby("sessionId", sort=True).groups.items():
        ordered_indices = list(indices)
        historical = (
            sessions.loc[ordered_indices, "sessionReturn"]
            .shift(1)
            .rolling(lookback_sessions, min_periods=lookback_sessions)
            .mean()
        )
        sessions.loc[ordered_indices, "historicalMean"] = historical.to_numpy()

    side = np.sign(sessions["historicalMean"].fillna(0.0)).astype(int)
    side = side.where(
        sessions["historicalMean"].abs() >= float(minimum_session_mean),
        0,
    )
    sessions["predictedSide"] = side
    sessions["volumeRatio"] = np.nan
    sessions["realizedVolatility"] = np.nan
    sessions["adaptationGate"] = True

    if adaptation:
        prior_volume = bars["volume"].rolling(24, min_periods=24).mean()
        baseline_volume = bars["volume"].rolling(24 * 7, min_periods=24 * 7).mean()
        volume_ratio = prior_volume / baseline_volume.replace(0.0, np.nan)
        realized_volatility = (
            bars["close"].pct_change().rolling(24, min_periods=24).std(ddof=0)
        )
        signal_indices = (sessions["startIndex"] - 1).clip(lower=0).astype(int)
        sessions["volumeRatio"] = volume_ratio.iloc[signal_indices].to_numpy()
        sessions["realizedVolatility"] = realized_volatility.iloc[
            signal_indices
        ].to_numpy()
        sessions["adaptationGate"] = (
            sessions["volumeRatio"].between(
                minimum_volume_ratio,
                maximum_volume_ratio,
                inclusive="both",
            )
            & (sessions["realizedVolatility"] <= maximum_realized_volatility)
        ).fillna(False)

    sessions["eligible"] = (
        sessions["predictedSide"].ne(0)
        & sessions["adaptationGate"]
        & sessions["barCount"].eq(session_hours)
        & sessions["startIndex"].gt(0)
    )
    return sessions


def _simulate_session_trade(
    *,
    frame: pd.DataFrame,
    start_index: int,
    end_index: int,
    side: int,
    atr_value: float,
    stop_atr: float,
    maximum_hold_bars: int,
    round_trip_cost_rate: float,
) -> dict[str, Any] | None:
    if start_index <= 0 or start_index >= len(frame):
        return None
    if not np.isfinite(atr_value) or atr_value <= 0:
        return None
    entry_price = float(frame.iloc[start_index]["open"])
    risk_distance = float(atr_value * stop_atr)
    if risk_distance <= 0 or risk_distance / entry_price > 0.25:
        return None
    stop_price = entry_price - side * risk_distance
    last_index = min(end_index, start_index + maximum_hold_bars, len(frame) - 1)
    exit_index = last_index
    exit_price = float(frame.iloc[last_index]["close"])
    exit_reason = "session_close"
    maximum_favorable = 0.0
    maximum_adverse = 0.0
    for position in range(start_index, last_index + 1):
        row = frame.iloc[position]
        favorable = (
            float(row["high"]) - entry_price
            if side > 0
            else entry_price - float(row["low"])
        )
        adverse = (
            float(row["low"]) - entry_price
            if side > 0
            else entry_price - float(row["high"])
        )
        maximum_favorable = max(maximum_favorable, favorable / risk_distance)
        maximum_adverse = min(maximum_adverse, adverse / risk_distance)
        stopped = (
            float(row["low"]) <= stop_price
            if side > 0
            else float(row["high"]) >= stop_price
        )
        if stopped:
            exit_index = position
            exit_price = stop_price
            exit_reason = "initial_stop"
            break

    gross_r = side * (exit_price - entry_price) / risk_distance
    cost_r = round_trip_cost_rate * entry_price / risk_distance
    return {
        "entryTimestampMs": int(frame.iloc[start_index]["date"].timestamp() * 1000),
        "exitTimestampMs": int(frame.iloc[exit_index]["date"].timestamp() * 1000),
        "direction": "long" if side > 0 else "short",
        "grossR": float(gross_r),
        "costR": float(cost_r),
        "netR": float(gross_r - cost_r),
        "mfeR": float(maximum_favorable),
        "maeR": float(maximum_adverse),
        "exitReason": exit_reason,
    }


def _directional_metrics(events: Sequence[Mapping[str, object]]) -> dict[str, Any]:
    values = [float(row["netR"]) for row in events]
    symbols: dict[str, int] = {}
    for row in events:
        symbol = str(row["instrumentId"])
        symbols[symbol] = symbols.get(symbol, 0) + 1
    event_count = len(events)
    average_net_r = float(np.mean(values)) if values else 0.0
    return {
        "eventCount": event_count,
        "profitFactor": _profit_factor(values),
        "averageNetR": average_net_r,
        "totalNetR": float(sum(values)),
        "mfe": float(np.mean([float(row["mfeR"]) for row in events]))
        if events
        else 0.0,
        "mae": float(np.mean([float(row["maeR"]) for row in events]))
        if events
        else 0.0,
        "totalCostR": float(sum(float(row["costR"]) for row in events)),
        "benchmarkIncrementNetR": average_net_r,
        "maxDrawdownR": _drawdown(values),
        "concentration": max(symbols.values()) / event_count if event_count else 1.0,
    }


def build_intraday_prefilter(
    *,
    metrics: Mapping[str, object],
    events: Sequence[Mapping[str, object]],
) -> dict[str, Any]:
    """Apply cheap Development-only gates before any Formal consideration."""

    ordered = sorted(events, key=lambda row: int(row["entryTimestampMs"]))
    chunks = np.array_split(np.asarray([float(row["netR"]) for row in ordered]), 3)
    subperiod_net_r = [float(chunk.mean()) if len(chunk) else 0.0 for chunk in chunks]
    positive_subperiod_count = sum(value > 0 for value in subperiod_net_r)
    gates = {
        "minimumEventCount": int(metrics.get("eventCount") or 0) >= 90,
        "positiveAverageNetR": float(metrics.get("averageNetR") or 0.0) > 0.0,
        "minimumProfitFactor": float(metrics.get("profitFactor") or 0.0) >= 1.02,
        "subperiodStability": positive_subperiod_count >= 2,
        "maximumConcentration": float(metrics.get("concentration") or 1.0) <= 0.60,
    }
    return {
        "schemaVersion": "v36_5_intraday_cheap_prefilter_v1",
        "passed": all(gates.values()),
        "gates": gates,
        "positiveSubperiodCount": positive_subperiod_count,
        "subperiodAverageNetR": subperiod_net_r,
        "lockedOosReadCount": 0,
    }


def replay_intraday_session(
    *,
    frames: Mapping[tuple[str, str], pd.DataFrame],
    definition: Mapping[str, Any],
    round_trip_cost_rate: float,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    """Replay one frozen intraday definition on Development-only frames."""

    timeframe = str(definition["timeframe"])
    events: list[dict[str, Any]] = []
    for symbol in _SYMBOLS:
        frame = frames[(symbol, timeframe)].copy().sort_values("date").reset_index(drop=True)
        atr = _atr(frame, int(definition["atrBars"]))
        signals = build_session_signal_table(
            frame,
            lookback_sessions=int(definition["lookbackSessions"]),
            minimum_session_mean=float(definition["minimumSessionMean"]),
            adaptation=bool(definition.get("adaptation")),
            session_hours=int(definition["sessionHours"]),
            minimum_volume_ratio=float(definition.get("minimumVolumeRatio", 0.8)),
            maximum_volume_ratio=float(definition.get("maximumVolumeRatio", 2.5)),
            maximum_realized_volatility=float(
                definition.get("maximumRealizedVolatility", 0.04)
            ),
        )
        for signal in signals[signals["eligible"]].itertuples(index=False):
            signal_index = int(signal.startIndex) - 1
            event = _simulate_session_trade(
                frame=frame,
                start_index=int(signal.startIndex),
                end_index=int(signal.endIndex),
                side=int(signal.predictedSide),
                atr_value=float(atr.iloc[signal_index]),
                stop_atr=float(definition["stopAtr"]),
                maximum_hold_bars=int(definition["maximumHoldBars"]),
                round_trip_cost_rate=round_trip_cost_rate,
            )
            if event is not None:
                event.update(
                    {
                        "instrumentId": symbol,
                        "setupName": "intraday_session_predictability",
                        "sessionId": int(signal.sessionId),
                    }
                )
                events.append(event)
    metrics = _directional_metrics(events)
    prefilter = build_intraday_prefilter(metrics=metrics, events=events)
    return metrics, events, prefilter
