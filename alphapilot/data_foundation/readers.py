"""Canonical OHLCV readers for local CSV and XLSX datasets."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class ReadResult:
    frame: pd.DataFrame
    sourceRows: int
    unconfirmedDroppedCount: int
    duplicateTimestampCount: int
    invalidOhlcDroppedCount: int
    negativeVolumeDroppedCount: int


def _parse_time(raw: pd.DataFrame) -> pd.Series:
    if "timestamp_ms" in raw.columns:
        values = pd.to_numeric(raw["timestamp_ms"], errors="coerce")
        return pd.to_datetime(values, unit="ms", utc=True, errors="coerce")
    if "timestamp" in raw.columns:
        values = pd.to_numeric(raw["timestamp"], errors="coerce")
        return pd.to_datetime(values, unit="ms", utc=True, errors="coerce")
    if "utc_time" not in raw.columns:
        raise ValueError("Missing timestamp_ms, timestamp, or utc_time")
    values = raw["utc_time"]
    numeric = pd.to_numeric(values, errors="coerce")
    valid_numeric = numeric.dropna()
    if not valid_numeric.empty and len(valid_numeric) >= max(1, int(len(values) * 0.9)):
        median = float(valid_numeric.median())
        if 20_000 <= median <= 100_000:
            return pd.to_datetime(numeric, unit="D", origin="1899-12-30", utc=True, errors="coerce")
        if median >= 100_000_000_000:
            return pd.to_datetime(numeric, unit="ms", utc=True, errors="coerce")
        if median >= 100_000_000:
            return pd.to_datetime(numeric, unit="s", utc=True, errors="coerce")
    return pd.to_datetime(values, utc=True, errors="coerce")


def _confirmed_mask(raw: pd.DataFrame) -> pd.Series:
    column = "confirmed" if "confirmed" in raw.columns else "confirm" if "confirm" in raw.columns else None
    if column is None:
        return pd.Series(True, index=raw.index)
    values = raw[column]
    numeric = pd.to_numeric(values, errors="coerce")
    return numeric.fillna(1).astype(int) == 1


def _volume_column(raw: pd.DataFrame) -> str:
    for column in (
        "volume_quote_currency",
        "volCcyQuote",
        "volume_base_or_contracts",
        "vol",
        "volume",
    ):
        if column in raw.columns:
            return column
    raise ValueError("Missing supported volume column")


def clean_ohlcv_frame(raw: pd.DataFrame) -> ReadResult:
    required = {"open", "high", "low", "close"}
    missing = required - set(raw.columns)
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(sorted(missing))}")
    source_rows = len(raw)
    confirmed = _confirmed_mask(raw)
    unconfirmed_dropped = int((~confirmed).sum())
    selected = raw.loc[confirmed].copy()
    frame = pd.DataFrame(
        {
            "date": _parse_time(selected),
            "open": pd.to_numeric(selected["open"], errors="coerce"),
            "high": pd.to_numeric(selected["high"], errors="coerce"),
            "low": pd.to_numeric(selected["low"], errors="coerce"),
            "close": pd.to_numeric(selected["close"], errors="coerce"),
            "volume": pd.to_numeric(selected[_volume_column(selected)], errors="coerce"),
        }
    )
    frame = frame.dropna(subset=["date", "open", "high", "low", "close", "volume"])
    frame["date"] = pd.to_datetime(frame["date"], utc=True).dt.floor("ms")
    duplicate_count = int(frame.duplicated(subset=["date"]).sum())
    frame = frame.drop_duplicates(subset=["date"], keep="last").sort_values("date").reset_index(drop=True)
    invalid_ohlc = (
        (frame["low"] > frame["high"])
        | (frame["open"] < frame["low"])
        | (frame["open"] > frame["high"])
        | (frame["close"] < frame["low"])
        | (frame["close"] > frame["high"])
    )
    negative_volume = frame["volume"] < 0
    invalid_count = int(invalid_ohlc.sum())
    negative_count = int(negative_volume.sum())
    frame = frame.loc[~invalid_ohlc & ~negative_volume].copy().reset_index(drop=True)
    frame["timestamp_ms"] = frame["date"].dt.as_unit("ms").astype("int64")
    frame["confirmed"] = 1
    return ReadResult(
        frame=frame[["timestamp_ms", "date", "open", "high", "low", "close", "volume", "confirmed"]],
        sourceRows=source_rows,
        unconfirmedDroppedCount=unconfirmed_dropped,
        duplicateTimestampCount=duplicate_count,
        invalidOhlcDroppedCount=invalid_count,
        negativeVolumeDroppedCount=negative_count,
    )


def read_ohlcv(path: Path | str) -> ReadResult:
    source = Path(path)
    suffix = source.suffix.lower()
    if suffix == ".csv":
        raw = pd.read_csv(source)
    elif suffix == ".xlsx":
        raw = pd.read_excel(source)
    else:
        raise ValueError(f"Unsupported OHLCV file format: {source.suffix}")
    return clean_ohlcv_frame(raw)


def frame_metadata(frame: pd.DataFrame) -> dict[str, Any]:
    return {
        "rows": len(frame),
        "startTime": frame["date"].min().isoformat() if not frame.empty else None,
        "endTime": frame["date"].max().isoformat() if not frame.empty else None,
    }
