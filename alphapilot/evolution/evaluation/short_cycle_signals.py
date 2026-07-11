"""Convert frozen short-cycle rules into formal completed-candle signals."""

from __future__ import annotations

import math
from typing import Any

import pandas as pd

from alphapilot.short_cycle.parameter_search import (
    add_indicators,
    build_signal,
    merge_btc_context,
)


_INTERVAL_MS = {"5m": 300_000, "15m": 900_000}
_OUTPUT_COLUMNS = [
    "pair",
    "timeframe",
    "signalDate",
    "signalTimestampMs",
    "sourceTimestampMs",
    "signalIndex",
    "direction",
    "setupName",
    "stopLossPct",
]


def _ordered_completed_frame(
    frame: pd.DataFrame,
    *,
    instrument: str,
    timeframe: str,
) -> pd.DataFrame:
    required = {"timestamp_ms", "open", "high", "low", "close", "volume"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(
            f"short_cycle_signal_frame_missing:{instrument}:{','.join(missing)}"
        )
    ordered = frame.copy()
    if "confirmed" in ordered.columns:
        ordered = ordered.loc[pd.to_numeric(ordered["confirmed"], errors="coerce") == 1]
    if "timeframe" in ordered.columns:
        declared = {str(value) for value in ordered["timeframe"].dropna().unique()}
        if declared and declared != {timeframe}:
            raise ValueError(f"short_cycle_signal_timeframe_mismatch:{instrument}")
    ordered = (
        ordered.sort_values("timestamp_ms")
        .drop_duplicates("timestamp_ms", keep="last")
        .reset_index(drop=True)
    )
    if "date" not in ordered.columns:
        ordered["date"] = pd.to_datetime(
            ordered["timestamp_ms"], unit="ms", utc=True
        )
    else:
        ordered["date"] = pd.to_datetime(ordered["date"], utc=True)
    return ordered


def _pair(instrument: str) -> str:
    suffix = "-USDT-SWAP"
    if instrument.endswith(suffix):
        return f"{instrument.removesuffix(suffix)}/USDT:USDT"
    return instrument.replace("-", "/")


def build_short_cycle_formal_signals(
    signal_frames: dict[str, pd.DataFrame],
    *,
    signal_timeframe: str,
    family: str,
    expected_direction: str,
    parameters: dict[str, Any],
) -> pd.DataFrame:
    """Build deterministic signals at the close of each completed source bar."""

    interval_ms = _INTERVAL_MS.get(signal_timeframe)
    if interval_ms is None:
        raise ValueError(f"short_cycle_signal_timeframe_not_supported:{signal_timeframe}")
    btc_source = signal_frames.get("BTC-USDT-SWAP")
    if btc_source is None or btc_source.empty:
        raise ValueError("short_cycle_btc_context_missing")
    btc = _ordered_completed_frame(
        btc_source,
        instrument="BTC-USDT-SWAP",
        timeframe=signal_timeframe,
    )

    rows: list[dict[str, Any]] = []
    for instrument in sorted(signal_frames):
        source = signal_frames[instrument]
        if source.empty:
            continue
        ordered = _ordered_completed_frame(
            source,
            instrument=instrument,
            timeframe=signal_timeframe,
        )
        enriched = merge_btc_context(add_indicators(ordered), btc)
        try:
            signal, direction = build_signal(enriched, family, parameters)
        except ValueError as error:
            if str(error).startswith("Unknown signal family"):
                raise ValueError(
                    f"short_cycle_signal_family_not_supported:{family}"
                ) from error
            raise
        except KeyError as error:
            raise ValueError(
                f"short_cycle_signal_parameter_missing:{error.args[0]}"
            ) from error
        if direction != expected_direction:
            raise ValueError(
                f"short_cycle_signal_direction_mismatch:{direction}:{expected_direction}"
            )
        for signal_index in signal[signal].index:
            row = enriched.loc[signal_index]
            close = float(row["close"])
            atr = float(row["atr14"])
            stop_loss_pct = atr * float(parameters.get("stop_atr") or 0) / close
            if not math.isfinite(stop_loss_pct) or stop_loss_pct <= 0:
                continue
            source_timestamp = int(row["timestamp_ms"])
            decision_timestamp = source_timestamp + interval_ms - 1
            rows.append(
                {
                    "pair": _pair(instrument),
                    "timeframe": signal_timeframe,
                    "signalDate": pd.Timestamp(
                        decision_timestamp, unit="ms", tz="UTC"
                    ).isoformat(),
                    "signalTimestampMs": decision_timestamp,
                    "sourceTimestampMs": source_timestamp,
                    "signalIndex": int(signal_index),
                    "direction": direction,
                    "setupName": family,
                    "stopLossPct": stop_loss_pct,
                }
            )
    if not rows:
        return pd.DataFrame(columns=_OUTPUT_COLUMNS)
    return (
        pd.DataFrame(rows, columns=_OUTPUT_COLUMNS)
        .sort_values(["signalTimestampMs", "pair"])
        .reset_index(drop=True)
    )
