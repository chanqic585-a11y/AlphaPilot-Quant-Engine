"""Low-frequency OHLCV data quality checks for V13.4.32.

The checker reads local public Freqtrade OHLCV files only. It does not download
data, run Freqtrade backtests, use API keys, call private endpoints, create
orders, or auto trade.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from alphapilot.factors.ohlcv_loader import _read_ohlcv_file, pair_to_freqtrade_stem, parse_timerange
from alphapilot.low_frequency.low_frequency_data_schema import (
    TIMEFRAME_MINUTES,
    LowFrequencyDataCheckConfig,
    LowFrequencyDataReport,
    PairTimeframeDataQuality,
)


REPORT_ID = "v13_4_32_low_frequency_data_report"
VERSION = "V13.4.32"
REQUIRED_COLUMNS = ("date", "open", "high", "low", "close", "volume")


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _round(value: Any, digits: int = 4) -> float | None:
    try:
        if value is None:
            return None
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return round(number, digits)


def _to_iso(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None
    return pd.Timestamp(value).isoformat()


def _candidate_path(data_path: str | Path, pair: str, timeframe: str) -> Path:
    return Path(data_path) / f"{pair_to_freqtrade_stem(pair)}-{timeframe}-futures.feather"


def _normalize_frame(raw: pd.DataFrame) -> pd.DataFrame:
    frame = raw.copy()
    frame["date"] = pd.to_datetime(frame["date"], utc=True, errors="coerce")
    for column in ("open", "high", "low", "close", "volume"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame


def _count_zero_volume_streaks(volume: pd.Series) -> int:
    max_streak = 0
    current = 0
    for value in volume.fillna(0):
        if value == 0:
            current += 1
            max_streak = max(max_streak, current)
        else:
            current = 0
    return int(max_streak)


def _expected_candle_count(first_timestamp: pd.Timestamp, last_timestamp: pd.Timestamp, timeframe: str) -> int:
    minutes = TIMEFRAME_MINUTES.get(timeframe)
    if minutes is None:
        return 0
    delta_minutes = (last_timestamp - first_timestamp).total_seconds() / 60
    if delta_minutes < 0:
        return 0
    return int(delta_minutes // minutes) + 1


def _quality_status(
    *,
    actual_count: int,
    missing_rate_pct: float | None,
    invalid_ohlc_rows: int,
    zero_price_rows: int,
    negative_volume_rows: int,
    config: LowFrequencyDataCheckConfig,
) -> str:
    if actual_count == 0:
        return "unavailable"
    if (
        missing_rate_pct is not None
        and missing_rate_pct > config.missingRateInvalidPct
        or actual_count < config.minimumCandles
        or invalid_ohlc_rows > 0
        or zero_price_rows > 0
        or negative_volume_rows > 0
    ):
        return "invalid"
    if missing_rate_pct is not None and missing_rate_pct > config.missingRateWarningPct:
        return "warning"
    return "valid"


def _check_pair_timeframe(
    pair: str,
    timeframe: str,
    config: LowFrequencyDataCheckConfig,
) -> PairTimeframeDataQuality:
    path = _candidate_path(config.dataPath, pair, timeframe)
    warnings: list[str] = []
    if not path.exists():
        return PairTimeframeDataQuality(
            pair=pair,
            timeframe=timeframe,
            path=path.as_posix(),
            status="unavailable",
            firstTimestamp=None,
            lastTimestamp=None,
            actualCandleCount=0,
            expectedCandleCount=0,
            missingCandleCount=0,
            missingRatePct=None,
            duplicateTimestampCount=0,
            invalidOhlcRows=0,
            zeroPriceRows=0,
            negativeVolumeRows=0,
            extremeReturnRows=0,
            maxZeroVolumeStreak=0,
            dataQualityStatus="unavailable",
            warnings=[f"Missing local OHLCV file for {pair} {timeframe}."],
        )

    try:
        raw = _read_ohlcv_file(path)
    except Exception as exc:  # noqa: BLE001 - reported as data quality status.
        return PairTimeframeDataQuality(
            pair=pair,
            timeframe=timeframe,
            path=path.as_posix(),
            status="unavailable",
            firstTimestamp=None,
            lastTimestamp=None,
            actualCandleCount=0,
            expectedCandleCount=0,
            missingCandleCount=0,
            missingRatePct=None,
            duplicateTimestampCount=0,
            invalidOhlcRows=0,
            zeroPriceRows=0,
            negativeVolumeRows=0,
            extremeReturnRows=0,
            maxZeroVolumeStreak=0,
            dataQualityStatus="unavailable",
            warnings=[f"Could not read local OHLCV file: {exc}"],
        )

    missing_columns = sorted(set(REQUIRED_COLUMNS).difference(raw.columns))
    if missing_columns:
        return PairTimeframeDataQuality(
            pair=pair,
            timeframe=timeframe,
            path=path.as_posix(),
            status="invalid",
            firstTimestamp=None,
            lastTimestamp=None,
            actualCandleCount=0,
            expectedCandleCount=0,
            missingCandleCount=0,
            missingRatePct=None,
            duplicateTimestampCount=0,
            invalidOhlcRows=0,
            zeroPriceRows=0,
            negativeVolumeRows=0,
            extremeReturnRows=0,
            maxZeroVolumeStreak=0,
            dataQualityStatus="invalid",
            warnings=[f"Missing required columns: {', '.join(missing_columns)}."],
        )

    frame = _normalize_frame(raw)
    duplicate_count = int(frame["date"].duplicated().sum())
    frame = frame.dropna(subset=["date"]).sort_values("date").drop_duplicates(subset=["date"], keep="last")

    start, end = parse_timerange(config.timerange)
    if start is not None:
        frame = frame[frame["date"] >= start]
    if end is not None:
        frame = frame[frame["date"] < end]

    actual_count = int(len(frame))
    if actual_count == 0:
        warnings.append("No rows remain after timerange filtering.")
        return PairTimeframeDataQuality(
            pair=pair,
            timeframe=timeframe,
            path=path.as_posix(),
            status="unavailable",
            firstTimestamp=None,
            lastTimestamp=None,
            actualCandleCount=0,
            expectedCandleCount=0,
            missingCandleCount=0,
            missingRatePct=None,
            duplicateTimestampCount=duplicate_count,
            invalidOhlcRows=0,
            zeroPriceRows=0,
            negativeVolumeRows=0,
            extremeReturnRows=0,
            maxZeroVolumeStreak=0,
            dataQualityStatus="unavailable",
            warnings=warnings,
        )

    first_timestamp = frame["date"].iloc[0]
    last_timestamp = frame["date"].iloc[-1]
    expected_count = _expected_candle_count(first_timestamp, last_timestamp, timeframe)
    missing_count = max(expected_count - actual_count, 0)
    missing_rate_pct = (missing_count / expected_count * 100) if expected_count else None

    invalid_ohlc_rows = int(
        (
            frame[["open", "high", "low", "close"]].isna().any(axis=1)
            | (frame["high"] < frame[["open", "close"]].max(axis=1))
            | (frame["low"] > frame[["open", "close"]].min(axis=1))
        ).sum()
    )
    zero_price_rows = int((frame[["open", "high", "low", "close"]] <= 0).any(axis=1).sum())
    negative_volume_rows = int((frame["volume"] < 0).sum())
    returns = frame["close"].pct_change().abs()
    extreme_return_rows = int((returns > 0.5).sum())
    max_zero_volume_streak = _count_zero_volume_streaks(frame["volume"])

    if start is not None and first_timestamp > start:
        warnings.append(f"Coverage starts after requested timerange start: {first_timestamp.isoformat()}.")
    if duplicate_count:
        warnings.append(f"Duplicate timestamps were found and deduplicated: {duplicate_count}.")
    if extreme_return_rows:
        warnings.append(f"Extreme close-to-close return rows detected: {extreme_return_rows}.")
    if max_zero_volume_streak >= 3:
        warnings.append(f"Zero-volume streak detected: {max_zero_volume_streak} candles.")

    status = _quality_status(
        actual_count=actual_count,
        missing_rate_pct=missing_rate_pct,
        invalid_ohlc_rows=invalid_ohlc_rows,
        zero_price_rows=zero_price_rows,
        negative_volume_rows=negative_volume_rows,
        config=config,
    )

    return PairTimeframeDataQuality(
        pair=pair,
        timeframe=timeframe,
        path=path.as_posix(),
        status=status,
        firstTimestamp=_to_iso(first_timestamp),
        lastTimestamp=_to_iso(last_timestamp),
        actualCandleCount=actual_count,
        expectedCandleCount=expected_count,
        missingCandleCount=missing_count,
        missingRatePct=_round(missing_rate_pct),
        duplicateTimestampCount=duplicate_count,
        invalidOhlcRows=invalid_ohlc_rows,
        zeroPriceRows=zero_price_rows,
        negativeVolumeRows=negative_volume_rows,
        extremeReturnRows=extreme_return_rows,
        maxZeroVolumeStreak=max_zero_volume_streak,
        dataQualityStatus=status,
        warnings=warnings,
    )


def build_low_frequency_data_report(config: LowFrequencyDataCheckConfig) -> LowFrequencyDataReport:
    checks = [
        _check_pair_timeframe(pair, timeframe, config)
        for pair in config.pairs
        for timeframe in config.timeframes
    ]
    counts = {
        "valid": sum(1 for item in checks if item.status == "valid"),
        "warning": sum(1 for item in checks if item.status == "warning"),
        "invalid": sum(1 for item in checks if item.status == "invalid"),
        "unavailable": sum(1 for item in checks if item.status == "unavailable"),
    }
    warnings: list[str] = []
    for item in checks:
        warnings.extend([f"{item.pair} {item.timeframe}: {warning}" for warning in item.warnings])
    status = "valid"
    if counts["invalid"] or counts["unavailable"]:
        status = "insufficient_data"
    elif counts["warning"]:
        status = "warning"

    summary = {
        "pairCount": len(config.pairs),
        "timeframeCount": len(config.timeframes),
        "pairTimeframeCount": len(checks),
        "validCount": counts["valid"],
        "warningCount": counts["warning"],
        "invalidCount": counts["invalid"],
        "unavailableCount": counts["unavailable"],
        "minimumCandles": config.minimumCandles,
    }
    return LowFrequencyDataReport(
        reportId=REPORT_ID,
        version=VERSION,
        status=status,
        timerange=config.timerange,
        dataPath=config.dataPath,
        pairs=config.pairs,
        timeframes=config.timeframes,
        optionalTimeframes=config.optionalTimeframes,
        summary=summary,
        pairTimeframeQuality=checks,
        warnings=warnings,
        generatedAt=utc_now(),
    )
