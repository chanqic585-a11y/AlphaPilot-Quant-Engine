"""Causal BTC downside-spillover research for the bounded V36.6 campaign."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd


BTC_SYMBOL = "BTC-USDT-SWAP"


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


def build_btc_downside_signal_table(
    frame: pd.DataFrame,
    *,
    shock_lookback_bars: int,
    shock_quantile: float,
    minimum_shock_return: float,
) -> pd.DataFrame:
    """Detect BTC shocks against a threshold learned only from prior bars."""

    if shock_lookback_bars < 100:
        raise ValueError("shock_lookback_too_short")
    if not 0.0 < shock_quantile < 0.5:
        raise ValueError("shock_quantile_invalid")
    if minimum_shock_return >= 0:
        raise ValueError("minimum_shock_return_must_be_negative")
    bars = frame.copy().sort_values("date").reset_index(drop=True)
    bars["date"] = pd.to_datetime(bars["date"], utc=True, errors="coerce")
    if bars["date"].isna().any():
        raise ValueError("btc_spillover_timestamp_invalid")
    bars["btcReturn"] = bars["close"].pct_change()
    bars["shockThreshold"] = (
        bars["btcReturn"]
        .shift(1)
        .rolling(shock_lookback_bars, min_periods=shock_lookback_bars)
        .quantile(shock_quantile)
    )
    effective_threshold = bars["shockThreshold"].clip(upper=minimum_shock_return)
    bars["shockSignal"] = (
        bars["btcReturn"].le(effective_threshold) & effective_threshold.notna()
    )
    return bars[["date", "btcReturn", "shockThreshold", "shockSignal"]]


def _simulate_short_trade(
    *,
    frame: pd.DataFrame,
    signal_index: int,
    atr_value: float,
    stop_atr: float,
    maximum_hold_bars: int,
    round_trip_cost_rate: float,
) -> tuple[dict[str, Any] | None, int]:
    entry_index = signal_index + 1
    if entry_index >= len(frame):
        return None, entry_index
    if frame.iloc[entry_index]["date"] - frame.iloc[signal_index]["date"] > pd.Timedelta(
        hours=1, minutes=5
    ):
        return None, entry_index
    if not np.isfinite(atr_value) or atr_value <= 0:
        return None, entry_index
    entry_price = float(frame.iloc[entry_index]["open"])
    risk_distance = float(atr_value * stop_atr)
    if risk_distance <= 0 or risk_distance / entry_price > 0.25:
        return None, entry_index
    stop_price = entry_price + risk_distance
    last_index = min(entry_index + maximum_hold_bars - 1, len(frame) - 1)
    exit_index = last_index
    exit_price = float(frame.iloc[last_index]["close"])
    exit_reason = "time_exit"
    maximum_favorable = 0.0
    maximum_adverse = 0.0
    for position in range(entry_index, last_index + 1):
        row = frame.iloc[position]
        maximum_favorable = max(
            maximum_favorable,
            (entry_price - float(row["low"])) / risk_distance,
        )
        maximum_adverse = min(
            maximum_adverse,
            (entry_price - float(row["high"])) / risk_distance,
        )
        if float(row["high"]) >= stop_price:
            exit_index = position
            exit_price = stop_price
            exit_reason = "initial_stop"
            break
    gross_r = (entry_price - exit_price) / risk_distance
    cost_r = round_trip_cost_rate * entry_price / risk_distance
    return (
        {
            "entryTimestampMs": int(frame.iloc[entry_index]["date"].timestamp() * 1000),
            "exitTimestampMs": int(frame.iloc[exit_index]["date"].timestamp() * 1000),
            "direction": "short",
            "grossR": float(gross_r),
            "costR": float(cost_r),
            "netR": float(gross_r - cost_r),
            "mfeR": float(maximum_favorable),
            "maeR": float(maximum_adverse),
            "exitReason": exit_reason,
        },
        exit_index + 1,
    )


def _metrics(events: Sequence[Mapping[str, object]]) -> dict[str, Any]:
    values = [float(row["netR"]) for row in events]
    symbol_counts: dict[str, int] = {}
    for row in events:
        symbol = str(row["instrumentId"])
        symbol_counts[symbol] = symbol_counts.get(symbol, 0) + 1
    count = len(events)
    average = float(np.mean(values)) if values else 0.0
    return {
        "eventCount": count,
        "profitFactor": _profit_factor(values),
        "averageNetR": average,
        "totalNetR": float(sum(values)),
        "mfe": float(np.mean([float(row["mfeR"]) for row in events]))
        if events
        else 0.0,
        "mae": float(np.mean([float(row["maeR"]) for row in events]))
        if events
        else 0.0,
        "totalCostR": float(sum(float(row["costR"]) for row in events)),
        "benchmarkIncrementNetR": average,
        "maxDrawdownR": _drawdown(values),
        "concentration": max(symbol_counts.values()) / count if count else 1.0,
    }


def build_spillover_prefilter(
    *,
    metrics: Mapping[str, object],
    events: Sequence[Mapping[str, object]],
    minimum_event_count: int,
    maximum_concentration: float,
) -> dict[str, Any]:
    ordered = sorted(events, key=lambda row: int(row["entryTimestampMs"]))
    chunks = np.array_split(np.asarray([float(row["netR"]) for row in ordered]), 3)
    subperiods = [float(chunk.mean()) if len(chunk) else 0.0 for chunk in chunks]
    positive_subperiods = sum(value > 0 for value in subperiods)
    gates = {
        "minimumEventCount": int(metrics.get("eventCount") or 0) >= minimum_event_count,
        "positiveAverageNetR": float(metrics.get("averageNetR") or 0.0) > 0.0,
        "minimumProfitFactor": float(metrics.get("profitFactor") or 0.0) >= 1.02,
        "subperiodStability": positive_subperiods >= 2,
        "maximumConcentration": float(metrics.get("concentration") or 1.0)
        <= maximum_concentration,
    }
    return {
        "schemaVersion": "v36_6_btc_downside_spillover_prefilter_v1",
        "passed": all(gates.values()),
        "gates": gates,
        "positiveSubperiodCount": positive_subperiods,
        "subperiodAverageNetR": subperiods,
        "lockedOosReadCount": 0,
    }


def replay_btc_downside_spillover(
    *,
    frames: Mapping[tuple[str, str], pd.DataFrame],
    definition: Mapping[str, Any],
    round_trip_cost_rate: float,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    """Replay one frozen spillover definition on Development-only frames."""

    timeframe = str(definition["timeframe"])
    btc = frames[(BTC_SYMBOL, timeframe)].copy().sort_values("date").reset_index(drop=True)
    shocks = build_btc_downside_signal_table(
        btc,
        shock_lookback_bars=int(definition["shockLookbackBars"]),
        shock_quantile=float(definition["shockQuantile"]),
        minimum_shock_return=float(definition["minimumShockReturn"]),
    )
    events: list[dict[str, Any]] = []
    for symbol in tuple(str(value) for value in definition["targetSymbols"]):
        target = frames[(symbol, timeframe)].copy().sort_values("date").reset_index(drop=True)
        aligned = target.merge(shocks, on="date", how="inner", validate="one_to_one")
        aligned["targetReturn"] = aligned["close"].pct_change()
        lagged_btc = aligned["btcReturn"].shift(1)
        lagged_target = aligned["targetReturn"].shift(1)
        beta_window = int(definition.get("betaLookbackBars", 336))
        aligned["beta"] = (
            lagged_target.rolling(beta_window, min_periods=beta_window).cov(lagged_btc)
            / lagged_btc.rolling(beta_window, min_periods=beta_window).var().replace(0.0, np.nan)
        )
        aligned["volumeRatio"] = (
            aligned["volume"].rolling(24, min_periods=24).mean()
            / aligned["volume"].rolling(24 * 7, min_periods=24 * 7).mean().replace(0.0, np.nan)
        )
        adaptation_gate = pd.Series(True, index=aligned.index)
        if bool(definition.get("adaptation")):
            adaptation_gate = (
                aligned["beta"].ge(float(definition.get("minimumBeta", 0.5)))
                & aligned["volumeRatio"].between(
                    float(definition.get("minimumVolumeRatio", 0.5)),
                    float(definition.get("maximumVolumeRatio", 3.0)),
                    inclusive="both",
                )
            ).fillna(False)
        signals = aligned["shockSignal"].fillna(False) & adaptation_gate
        atr = _atr(aligned, int(definition["atrBars"]))
        next_available = 0
        for signal_index in np.flatnonzero(signals.to_numpy()):
            signal_index = int(signal_index)
            if signal_index < next_available:
                continue
            event, next_available = _simulate_short_trade(
                frame=aligned,
                signal_index=signal_index,
                atr_value=float(atr.iloc[signal_index]),
                stop_atr=float(definition["stopAtr"]),
                maximum_hold_bars=int(definition["maximumHoldBars"]),
                round_trip_cost_rate=round_trip_cost_rate,
            )
            if event is not None:
                event.update(
                    {
                        "instrumentId": symbol,
                        "setupName": "btc_downside_spillover",
                        "btcShockReturn": float(aligned.iloc[signal_index]["btcReturn"]),
                        "laggedBeta": (
                            float(aligned.iloc[signal_index]["beta"])
                            if np.isfinite(aligned.iloc[signal_index]["beta"])
                            else None
                        ),
                    }
                )
                events.append(event)
    metrics = _metrics(events)
    prefilter = build_spillover_prefilter(
        metrics=metrics,
        events=events,
        minimum_event_count=int(definition["minimumEventCount"]),
        maximum_concentration=float(definition.get("maximumConcentration", 0.45)),
    )
    return metrics, events, prefilter
