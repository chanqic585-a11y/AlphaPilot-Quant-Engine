"""Point-in-time ranking evidence for the frozen V36 TSMOM candidates."""

from __future__ import annotations

import math
from statistics import median
from typing import Any, Mapping, Sequence

import pandas as pd

from alphapilot.evolution.registry.hashing import stable_hash

from .tsmom_engine import atr, normalize_tsmom_frame


def _utc_iso(value: object) -> str:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize("UTC")
    else:
        timestamp = timestamp.tz_convert("UTC")
    return timestamp.isoformat().replace("+00:00", "Z")


def _prior_daily_liquidity(
    frame: pd.DataFrame,
    signal_timestamp: object,
) -> tuple[float | None, list[dict[str, Any]]]:
    signal_day = pd.Timestamp(signal_timestamp).tz_convert("UTC").floor("D")
    daily = (
        frame.assign(day=frame["date"].dt.floor("D"))
        .groupby("day", as_index=False)["volume"]
        .sum()
    )
    prior = daily[daily["day"] < signal_day].tail(30)
    rows = [
        {
            "timestamp": _utc_iso(row.day),
            "quoteVolume": float(row.volume),
        }
        for row in prior.itertuples(index=False)
    ]
    values = [
        float(row["quoteVolume"])
        for row in rows
        if math.isfinite(float(row["quoteVolume"]))
        and float(row["quoteVolume"]) > 0.0
    ]
    return (float(median(values)) if len(values) >= 24 else None), rows


def _source_hashes(
    *,
    frame: pd.DataFrame,
    signal_index: int,
    lookback: int,
    liquidity_rows: Sequence[Mapping[str, Any]],
) -> list[str]:
    source_rows = []
    for row in frame.iloc[max(0, signal_index - lookback + 1) : signal_index + 1][
        ["date", "open", "high", "low", "close", "volume", "fundingRate"]
    ].itertuples(index=False):
        source_rows.append(
            {
                "date": _utc_iso(row.date),
                "open": float(row.open),
                "high": float(row.high),
                "low": float(row.low),
                "close": float(row.close),
                "volume": float(row.volume),
                "fundingRate": float(row.fundingRate),
            }
        )
    return [
        "sha256:" + stable_hash(source_rows),
        "sha256:" + stable_hash([dict(row) for row in liquidity_rows]),
    ]


def build_tsmom_formal_ranking_evidence(
    *,
    events: Sequence[Mapping[str, Any]],
    frames: Mapping[str, pd.DataFrame],
    candidate: Mapping[str, Any],
    include_source_bar_hashes: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Project causal TSMOM features into the frozen formal ranking fields."""

    definition = dict(candidate["definition"])
    momentum_bars = int(definition["lookbackBars"])
    donchian_bars = int(definition["entryDonchianBars"])
    atr_bars = int(definition["atrBars"])
    evidence_lookback = max(momentum_bars + 1, donchian_bars + 1, atr_bars + 1)
    ordered = {
        symbol: normalize_tsmom_frame(frame, symbol=symbol)
        for symbol, frame in frames.items()
    }
    features: dict[str, pd.DataFrame] = {}
    for symbol, frame in ordered.items():
        momentum = frame["close"] / frame["close"].shift(momentum_bars) - 1.0
        atr_values = atr(frame, atr_bars)
        prior_high = frame["high"].shift(1).rolling(
            donchian_bars, min_periods=donchian_bars
        ).max()
        prior_low = frame["low"].shift(1).rolling(
            donchian_bars, min_periods=donchian_bars
        ).min()
        features[symbol] = pd.DataFrame(
            {
                "date": frame["date"],
                "momentum": momentum,
                "atr": atr_values,
                "priorHigh": prior_high,
                "priorLow": prior_low,
            }
        )

    rows: list[dict[str, Any]] = []
    missing: list[dict[str, str]] = []
    for source in events:
        event = dict(source)
        symbol = str(event.get("symbol") or event.get("instrumentId") or "")
        frame = ordered.get(symbol)
        feature = features.get(symbol)
        signal_timestamp = pd.Timestamp(event.get("signalTimestamp"))
        if signal_timestamp.tzinfo is None:
            signal_timestamp = signal_timestamp.tz_localize("UTC")
        else:
            signal_timestamp = signal_timestamp.tz_convert("UTC")

        signal_index: int | None = None
        if frame is not None:
            matches = frame.index[frame["date"] == signal_timestamp]
            if len(matches) == 1:
                signal_index = int(matches[0])

        trend_strength: float | None = None
        breakout_strength: float | None = None
        liquidity: float | None = None
        liquidity_rows: list[dict[str, Any]] = []
        if frame is not None and feature is not None and signal_index is not None:
            feature_row = feature.iloc[signal_index]
            momentum = feature_row["momentum"]
            atr_value = feature_row["atr"]
            direction = str(event.get("direction") or event.get("side") or "")
            boundary = (
                feature_row["priorHigh"]
                if direction == "long"
                else feature_row["priorLow"]
            )
            if pd.notna(momentum):
                trend_strength = -abs(float(momentum))
            if pd.notna(atr_value) and float(atr_value) > 0.0 and pd.notna(boundary):
                close = float(frame.iloc[signal_index]["close"])
                breakout_strength = (
                    (close - float(boundary)) / float(atr_value)
                    if direction == "long"
                    else (float(boundary) - close) / float(atr_value)
                )
            liquidity, liquidity_rows = _prior_daily_liquidity(
                frame,
                signal_timestamp,
            )

        values = {
            "eventExtremeResidualZ": trend_strength,
            "recoverySizeZ": breakout_strength,
            "liquidity30d": liquidity,
        }
        for field, value in values.items():
            if value is None or not math.isfinite(float(value)):
                missing.append(
                    {
                        "signalId": str(event.get("signalId") or ""),
                        "field": field,
                    }
                )
        source_hashes = (
            _source_hashes(
                frame=frame,
                signal_index=signal_index,
                lookback=evidence_lookback,
                liquidity_rows=liquidity_rows,
            )
            if include_source_bar_hashes
            and frame is not None
            and signal_index is not None
            else []
        )
        rows.append(
            {
                **event,
                **values,
                "instrumentId": symbol,
                "sourceTimestamp": _utc_iso(signal_timestamp),
                "availableAt": _utc_iso(signal_timestamp),
                "dailyLiquidity": liquidity_rows,
                "sourceBarHashes": source_hashes,
                "lookaheadReadCount": 0,
            }
        )

    return rows, {
        "schemaVersion": "v36_tsmom_formal_ranking_evidence_v1",
        "eventCount": len(events),
        "missingRankingFieldCount": len(missing),
        "missing": missing,
        "rankingProjection": {
            "eventExtremeResidualZ": "negative_absolute_momentum",
            "recoverySizeZ": "directional_donchian_breakout_distance_atr",
            "liquidity30d": "prior_completed_utc_day_quote_volume_median",
        },
        "liquidityLookbackCompletedUtcDays": 30,
        "liquidityMinimumCompletedUtcDays": 24,
        "lookaheadReadCount": 0,
    }


__all__ = ["build_tsmom_formal_ranking_evidence"]
