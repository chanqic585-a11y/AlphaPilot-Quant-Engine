"""Local OHLCV integrity checker for V13.4.27.

The checker reads local public Freqtrade OHLCV files only. It does not download
data, call exchange APIs, read accounts, create orders, run backtests, or auto
trade.
"""

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any

import pandas as pd

from alphapilot.data_quality.data_quality_schema import (
    DataIntegrityResult,
    DataIntegritySummary,
    PairTimeframeQuality,
)
from alphapilot.factors.ohlcv_loader import discover_ohlcv_files, parse_timerange
from alphapilot.universe.top30_usdt_swap import get_top30_usdt_swap_pairs

PAIR_FORMAT_RE = re.compile(r"^[A-Z0-9]+/USDT:USDT$")
TIMEFRAME_MINUTES = {
    "15m": 15,
    "1h": 60,
    "4h": 240,
    "1d": 1440,
}
EXTREME_RETURN_THRESHOLDS = {
    "15m": 0.20,
    "1h": 0.30,
    "4h": 0.50,
    "1d": 0.80,
}


def _read_ohlcv_file(path: Path) -> pd.DataFrame:
    suffixes = "".join(path.suffixes)
    if path.suffix == ".feather":
        return pd.read_feather(path)
    if path.suffix == ".parquet":
        return pd.read_parquet(path)
    if suffixes.endswith(".json.gz") or path.suffix == ".json":
        return pd.read_json(path)
    raise ValueError(f"unsupported_file_format:{path.name}")


def _safe_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def _round_pct(value: float | int | None) -> float:
    if value is None:
        return 0.0
    return round(float(value), 4)


def _iso(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize("UTC")
    else:
        timestamp = timestamp.tz_convert("UTC")
    return timestamp.isoformat()


def _max_consecutive_true(values: list[bool]) -> int:
    best = 0
    current = 0
    for value in values:
        if value:
            current += 1
            best = max(best, current)
        else:
            current = 0
    return best


def _detect_market_type(path: Path | None) -> str:
    if path is None:
        return "unknown"
    name = path.name.lower()
    if "futures" in name or "swap" in name:
        return "futures"
    if "spot" in name:
        return "spot"
    return "unknown"


def _missing_file_quality(pair: str, timeframe: str) -> PairTimeframeQuality:
    return PairTimeframeQuality(
        pair=pair,
        timeframe=timeframe,
        path=None,
        status="missing_file",
        rowCount=0,
        uniqueTimestampCount=0,
        firstTimestamp=None,
        lastTimestamp=None,
        expectedCandles=0,
        missingCandleCount=0,
        missingRatePct=100.0,
        duplicateTimestampCount=0,
        nonMonotonicTimestampCount=0,
        gapCount=0,
        maxGapMinutes=None,
        invalidOhlcCount=0,
        nanPriceCount=0,
        negativeVolumeCount=0,
        zeroVolumeCount=0,
        maxConsecutiveZeroVolume=0,
        volumeSpikeCount=0,
        extremeReturnCount=0,
        maxAbsReturnPct=None,
        quoteVolumeAvailable=False,
        quoteVolumeEstimated=False,
        pairFormatValid=bool(PAIR_FORMAT_RE.match(pair)),
        marketType="unknown",
        warnings=[f"Missing local {timeframe} futures OHLCV file."],
    )


def _error_quality(pair: str, timeframe: str, path: Path, error: Exception) -> PairTimeframeQuality:
    return PairTimeframeQuality(
        pair=pair,
        timeframe=timeframe,
        path=path.as_posix(),
        status="invalid",
        rowCount=0,
        uniqueTimestampCount=0,
        firstTimestamp=None,
        lastTimestamp=None,
        expectedCandles=0,
        missingCandleCount=0,
        missingRatePct=100.0,
        duplicateTimestampCount=0,
        nonMonotonicTimestampCount=0,
        gapCount=0,
        maxGapMinutes=None,
        invalidOhlcCount=0,
        nanPriceCount=0,
        negativeVolumeCount=0,
        zeroVolumeCount=0,
        maxConsecutiveZeroVolume=0,
        volumeSpikeCount=0,
        extremeReturnCount=0,
        maxAbsReturnPct=None,
        quoteVolumeAvailable=False,
        quoteVolumeEstimated=False,
        pairFormatValid=bool(PAIR_FORMAT_RE.match(pair)),
        marketType=_detect_market_type(path),
        warnings=[f"Could not read OHLCV file: {error}"],
    )


def _quality_for_frame(pair: str, timeframe: str, path: Path, raw: pd.DataFrame, timerange: str) -> PairTimeframeQuality:
    warnings: list[str] = []
    pair_format_valid = bool(PAIR_FORMAT_RE.match(pair))
    if not pair_format_valid:
        warnings.append("Pair format is not XXX/USDT:USDT.")

    market_type = _detect_market_type(path)
    if market_type != "futures":
        warnings.append(f"File market type is {market_type}; expected futures/swap.")

    required = {"date", "open", "high", "low", "close", "volume"}
    missing_columns = sorted(required.difference(raw.columns))
    if missing_columns:
        return PairTimeframeQuality(
            pair=pair,
            timeframe=timeframe,
            path=path.as_posix(),
            status="invalid",
            rowCount=len(raw),
            uniqueTimestampCount=0,
            firstTimestamp=None,
            lastTimestamp=None,
            expectedCandles=0,
            missingCandleCount=0,
            missingRatePct=100.0,
            duplicateTimestampCount=0,
            nonMonotonicTimestampCount=0,
            gapCount=0,
            maxGapMinutes=None,
            invalidOhlcCount=0,
            nanPriceCount=0,
            negativeVolumeCount=0,
            zeroVolumeCount=0,
            maxConsecutiveZeroVolume=0,
            volumeSpikeCount=0,
            extremeReturnCount=0,
            maxAbsReturnPct=None,
            quoteVolumeAvailable="quoteVolume" in raw.columns,
            quoteVolumeEstimated="quoteVolume" not in raw.columns,
            pairFormatValid=pair_format_valid,
            marketType=market_type,
            warnings=warnings + [f"Missing columns: {', '.join(missing_columns)}."],
        )

    frame = raw.loc[:, ["date", "open", "high", "low", "close", "volume"]].copy()
    frame["date"] = pd.to_datetime(frame["date"], utc=True, errors="coerce")
    for column in ("open", "high", "low", "close", "volume"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")

    start, end = parse_timerange(timerange)
    if start is not None:
        frame = frame[frame["date"] >= start]
    if end is not None:
        frame = frame[frame["date"] < end]
    if frame.empty:
        return PairTimeframeQuality(
            pair=pair,
            timeframe=timeframe,
            path=path.as_posix(),
            status="invalid",
            rowCount=0,
            uniqueTimestampCount=0,
            firstTimestamp=None,
            lastTimestamp=None,
            expectedCandles=0,
            missingCandleCount=0,
            missingRatePct=100.0,
            duplicateTimestampCount=0,
            nonMonotonicTimestampCount=0,
            gapCount=0,
            maxGapMinutes=None,
            invalidOhlcCount=0,
            nanPriceCount=0,
            negativeVolumeCount=0,
            zeroVolumeCount=0,
            maxConsecutiveZeroVolume=0,
            volumeSpikeCount=0,
            extremeReturnCount=0,
            maxAbsReturnPct=None,
            quoteVolumeAvailable="quoteVolume" in raw.columns,
            quoteVolumeEstimated="quoteVolume" not in raw.columns,
            pairFormatValid=pair_format_valid,
            marketType=market_type,
            warnings=warnings + ["No rows remain after timerange filter."],
        )

    original_dates = frame["date"].dropna()
    original_diff = original_dates.diff().dt.total_seconds()
    non_monotonic_count = int((original_diff < 0).sum())
    duplicate_count = int(frame["date"].duplicated(keep=False).sum())

    sorted_frame = frame.dropna(subset=["date"]).sort_values("date").drop_duplicates(subset=["date"], keep="last")
    unique_count = len(sorted_frame)
    timeframe_minutes = TIMEFRAME_MINUTES.get(timeframe)
    if timeframe_minutes is None:
        warnings.append(f"Unknown timeframe interval for {timeframe}; gap math limited.")
        expected_candles = unique_count
        missing_count = 0
        missing_rate_pct = 0.0
        gap_count = 0
        max_gap_minutes = None
    else:
        expected_delta = pd.Timedelta(minutes=timeframe_minutes)
        first_timestamp = sorted_frame["date"].iloc[0]
        last_timestamp = sorted_frame["date"].iloc[-1]
        expected_candles = int(((last_timestamp - first_timestamp) / expected_delta)) + 1
        diffs = sorted_frame["date"].diff().dropna()
        gap_diffs = diffs[diffs > expected_delta]
        gap_count = int(len(gap_diffs))
        missing_count = int(sum(max(int(diff / expected_delta) - 1, 0) for diff in gap_diffs))
        missing_rate_pct = (missing_count / max(expected_candles, 1)) * 100.0
        max_gap_minutes = _safe_float(gap_diffs.max() / pd.Timedelta(minutes=1)) if not gap_diffs.empty else None

    price_columns = ["open", "high", "low", "close"]
    nan_price_count = int(sorted_frame[price_columns].isna().any(axis=1).sum())
    invalid_ohlc_mask = (
        sorted_frame[price_columns].isna().any(axis=1)
        | (sorted_frame[price_columns] <= 0).any(axis=1)
        | (sorted_frame["high"] < sorted_frame[["open", "close", "low"]].max(axis=1))
        | (sorted_frame["low"] > sorted_frame[["open", "close", "high"]].min(axis=1))
        | (sorted_frame["high"] < sorted_frame["low"])
    )
    invalid_ohlc_count = int(invalid_ohlc_mask.sum())

    negative_volume_count = int((sorted_frame["volume"] < 0).sum())
    zero_volume_mask = (sorted_frame["volume"] == 0).fillna(False)
    zero_volume_count = int(zero_volume_mask.sum())
    max_zero_run = _max_consecutive_true([bool(value) for value in zero_volume_mask.tolist()])

    rolling_median = sorted_frame["volume"].rolling(48, min_periods=12).median()
    spike_mask = (rolling_median > 0) & (sorted_frame["volume"] > rolling_median * 20)
    volume_spike_count = int(spike_mask.sum())

    returns = sorted_frame["close"].pct_change()
    threshold = EXTREME_RETURN_THRESHOLDS.get(timeframe, 0.50)
    extreme_mask = returns.abs() > threshold
    extreme_return_count = int(extreme_mask.sum())
    max_abs_return = _safe_float(returns.abs().max() * 100)

    if missing_rate_pct > 5:
        warnings.append(f"Missing candle rate above 5% warning threshold: {missing_rate_pct:.2f}%.")
    if missing_rate_pct > 20:
        warnings.append(f"Missing candle rate above 20% invalid threshold: {missing_rate_pct:.2f}%.")
    if duplicate_count:
        warnings.append(f"Duplicate timestamps detected: {duplicate_count}.")
    if non_monotonic_count:
        warnings.append(f"Original timestamps are not monotonic in {non_monotonic_count} rows.")
    if invalid_ohlc_count:
        warnings.append(f"Invalid OHLC rows detected: {invalid_ohlc_count}.")
    if negative_volume_count:
        warnings.append(f"Negative volume rows detected: {negative_volume_count}.")
    if extreme_return_count:
        warnings.append(f"Extreme close-to-close returns detected: {extreme_return_count}.")
    if "quoteVolume" not in raw.columns:
        warnings.append("quoteVolume is not present in raw OHLCV; research layers estimate it when needed.")

    status = "valid"
    if missing_rate_pct > 20 or invalid_ohlc_count > 0 or nan_price_count > 0 or negative_volume_count > 0:
        status = "invalid"
    elif missing_rate_pct > 5 or duplicate_count > 0 or non_monotonic_count > 0 or extreme_return_count > 0:
        status = "warning"

    return PairTimeframeQuality(
        pair=pair,
        timeframe=timeframe,
        path=path.as_posix(),
        status=status,
        rowCount=len(frame),
        uniqueTimestampCount=unique_count,
        firstTimestamp=_iso(sorted_frame["date"].iloc[0]) if unique_count else None,
        lastTimestamp=_iso(sorted_frame["date"].iloc[-1]) if unique_count else None,
        expectedCandles=expected_candles,
        missingCandleCount=missing_count,
        missingRatePct=_round_pct(missing_rate_pct),
        duplicateTimestampCount=duplicate_count,
        nonMonotonicTimestampCount=non_monotonic_count,
        gapCount=gap_count,
        maxGapMinutes=_safe_float(max_gap_minutes),
        invalidOhlcCount=invalid_ohlc_count,
        nanPriceCount=nan_price_count,
        negativeVolumeCount=negative_volume_count,
        zeroVolumeCount=zero_volume_count,
        maxConsecutiveZeroVolume=max_zero_run,
        volumeSpikeCount=volume_spike_count,
        extremeReturnCount=extreme_return_count,
        maxAbsReturnPct=_round_pct(max_abs_return) if max_abs_return is not None else None,
        quoteVolumeAvailable="quoteVolume" in raw.columns,
        quoteVolumeEstimated="quoteVolume" not in raw.columns,
        pairFormatValid=pair_format_valid,
        marketType=market_type,
        warnings=warnings,
    )


def check_ohlcv_integrity(
    data_path: str | Path = "user_data/data/okx/futures",
    timerange: str = "20260101-",
    timeframes: list[str] | tuple[str, ...] = ("1h", "4h"),
    pairs: list[str] | None = None,
) -> DataIntegrityResult:
    data_root = Path(data_path)
    requested_pairs = set(pairs or get_top30_usdt_swap_pairs())
    discovered_by_timeframe = {timeframe: discover_ohlcv_files(data_root, timeframe) for timeframe in timeframes}
    for discovered in discovered_by_timeframe.values():
        requested_pairs.update(discovered.keys())

    quality_rows: list[PairTimeframeQuality] = []
    for pair in sorted(requested_pairs):
        for timeframe in timeframes:
            path = discovered_by_timeframe.get(timeframe, {}).get(pair)
            if path is None:
                quality_rows.append(_missing_file_quality(pair, timeframe))
                continue
            try:
                raw = _read_ohlcv_file(path)
                quality_rows.append(_quality_for_frame(pair, timeframe, path, raw, timerange))
            except Exception as exc:  # noqa: BLE001 - diagnostics report the error safely.
                quality_rows.append(_error_quality(pair, timeframe, path, exc))

    missing_rates = [row.missingRatePct for row in quality_rows if row.status != "missing_file"]
    warnings: list[str] = []
    pair_format_issues = sum(1 for row in quality_rows if not row.pairFormatValid)
    spot_swap_mismatches = sum(1 for row in quality_rows if row.path and row.marketType != "futures")
    missing_file_count = sum(1 for row in quality_rows if row.status == "missing_file")
    invalid_count = sum(1 for row in quality_rows if row.status == "invalid")
    warning_count = sum(1 for row in quality_rows if row.status == "warning")
    valid_count = sum(1 for row in quality_rows if row.status == "valid")

    if missing_file_count:
        warnings.append(f"{missing_file_count} pair/timeframe files are missing locally.")
    if pair_format_issues:
        warnings.append(f"{pair_format_issues} pair/timeframe rows have pair format issues.")
    if spot_swap_mismatches:
        warnings.append(f"{spot_swap_mismatches} rows are not clearly futures/swap files.")
    if invalid_count:
        warnings.append("At least one pair/timeframe failed integrity checks.")

    status = "valid"
    if invalid_count:
        status = "invalid"
    elif warning_count or missing_file_count:
        status = "warning"

    summary = DataIntegritySummary(
        status=status,
        timerange=timerange,
        dataPath=str(data_root),
        timeframesChecked=list(timeframes),
        pairCount=len(requested_pairs),
        pairTimeframeCount=len(quality_rows),
        validCount=valid_count,
        warningCount=warning_count,
        invalidCount=invalid_count,
        missingFileCount=missing_file_count,
        averageMissingRatePct=_round_pct(sum(missing_rates) / len(missing_rates)) if missing_rates else 0.0,
        maxMissingRatePct=_round_pct(max(missing_rates)) if missing_rates else 0.0,
        totalDuplicateTimestamps=sum(row.duplicateTimestampCount for row in quality_rows),
        totalInvalidOhlcRows=sum(row.invalidOhlcCount for row in quality_rows),
        totalExtremeReturnRows=sum(row.extremeReturnCount for row in quality_rows),
        pairFormatIssueCount=pair_format_issues,
        spotSwapMismatchCount=spot_swap_mismatches,
        warnings=warnings,
    )
    return DataIntegrityResult(summary=summary, pairTimeframeQuality=quality_rows)


def result_to_pair_index(result: DataIntegrityResult) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for row in result.pairTimeframeQuality:
        item = indexed.setdefault(row.pair, {"pair": row.pair, "timeframes": {}, "worstStatus": "valid", "warnings": []})
        item["timeframes"][row.timeframe] = row.to_dict()
        item["warnings"].extend(row.warnings)
        if row.status == "invalid":
            item["worstStatus"] = "invalid"
        elif row.status in {"warning", "missing_file"} and item["worstStatus"] != "invalid":
            item["worstStatus"] = "warning"
    return indexed
