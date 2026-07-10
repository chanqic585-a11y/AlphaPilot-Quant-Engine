"""Quality checks for canonical OHLCV frames."""

from __future__ import annotations

from typing import Final

import pandas as pd

from .readers import ReadResult
from .types import FrameQuality


TIMEFRAME_MILLISECONDS: Final[dict[str, int]] = {
    "5m": 5 * 60 * 1000,
    "15m": 15 * 60 * 1000,
    "1h": 60 * 60 * 1000,
    "4h": 4 * 60 * 60 * 1000,
    "1d": 24 * 60 * 60 * 1000,
}


def inspect_quality(result: ReadResult, timeframe: str) -> FrameQuality:
    frame = result.frame
    errors: list[str] = []
    warnings: list[str] = []
    if timeframe not in TIMEFRAME_MILLISECONDS:
        errors.append(f"unsupported_timeframe:{timeframe}")
        interval = None
    else:
        interval = TIMEFRAME_MILLISECONDS[timeframe]
    if frame.empty:
        errors.append("empty_after_cleaning")
    timestamps = frame["timestamp_ms"] if "timestamp_ms" in frame else pd.Series(dtype="int64")
    differences = timestamps.diff().dropna()
    backward = int((differences < 0).sum())
    gap_events = 0
    missing_bars = 0
    if interval is not None and not differences.empty:
        gaps = differences[differences > interval]
        gap_events = len(gaps)
        missing_bars = int(sum(max(0, int(value // interval) - 1) for value in gaps))
    if backward:
        errors.append("timestamps_not_monotonic")
    if result.duplicateTimestampCount:
        warnings.append("duplicate_timestamps_removed")
    if gap_events:
        warnings.append("missing_intervals_present")
    if result.unconfirmedDroppedCount:
        warnings.append("unconfirmed_rows_removed")
    if result.invalidOhlcDroppedCount:
        warnings.append("invalid_ohlc_rows_removed")
    if result.negativeVolumeDroppedCount:
        warnings.append("negative_volume_rows_removed")
    return FrameQuality(
        rows=len(frame),
        startTime=frame["date"].min().isoformat() if not frame.empty else None,
        endTime=frame["date"].max().isoformat() if not frame.empty else None,
        duplicateTimestampCount=result.duplicateTimestampCount,
        backwardTimestampCount=backward,
        gapEventCount=gap_events,
        missingBarCount=missing_bars,
        invalidOhlcCount=result.invalidOhlcDroppedCount,
        negativeVolumeCount=result.negativeVolumeDroppedCount,
        unconfirmedDroppedCount=result.unconfirmedDroppedCount,
        sourceRows=result.sourceRows,
        errors=tuple(errors),
        warnings=tuple(warnings),
    )
