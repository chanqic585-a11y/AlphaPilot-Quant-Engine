"""Load only frozen catalog partitions required by the automatic program."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from alphapilot.evolution.registry.hashing import sha256_file


@dataclass(frozen=True)
class CatalogWindow:
    """Frames and access evidence returned by one bounded catalog read."""

    frames: dict[str, dict[str, pd.DataFrame]]
    funding: dict[str, pd.DataFrame]
    access_report: dict[str, Any]


def load_catalog_frames(
    catalog_path: Path,
    *,
    timeframes: Iterable[str] = ("1h", "4h"),
    verify_hashes: bool = True,
) -> dict[str, dict[str, pd.DataFrame]]:
    """Return timeframe -> symbol -> OHLCV frame from the frozen catalog."""

    payload: dict[str, Any] = json.loads(Path(catalog_path).read_text(encoding="utf-8"))
    allowed = {str(value) for value in timeframes}
    result: dict[str, dict[str, pd.DataFrame]] = {timeframe: {} for timeframe in allowed}
    for row in payload.get("datasets", []):
        timeframe = str(row.get("timeframe") or "")
        if timeframe not in allowed or str(row.get("dataType") or "") not in {
            "ohlcv",
            "market_ohlcv",
        }:
            continue
        symbols = [str(value) for value in row.get("symbols", [])]
        if len(symbols) != 1:
            continue
        path = Path(str(row.get("sourcePath") or ""))
        if not path.is_file():
            raise FileNotFoundError(path)
        expected_hash = str(row.get("contentHash") or "")
        if verify_hashes and expected_hash and sha256_file(path) != expected_hash:
            raise ValueError(f"catalog_partition_hash_mismatch:{row.get('datasetId')}")
        frame = pd.read_parquet(
            path,
            columns=["date", "open", "high", "low", "close", "volume"],
        )
        result[timeframe][symbols[0]] = frame
    missing = sorted(timeframe for timeframe, frames in result.items() if not frames)
    if missing:
        raise ValueError("catalog_timeframes_missing:" + ",".join(missing))
    return result


def _bounded_parquet_read(
    path: Path,
    *,
    timestamp_column: str,
    start: pd.Timestamp,
    end_exclusive: pd.Timestamp,
    columns: list[str],
) -> pd.DataFrame:
    """Read through Parquet predicates; never fall back to a whole-file read."""

    return pd.read_parquet(
        path,
        columns=columns,
        filters=[
            (timestamp_column, ">=", start.to_pydatetime()),
            (timestamp_column, "<", end_exclusive.to_pydatetime()),
        ],
    )


def load_catalog_window(
    catalog_path: Path,
    *,
    start: str,
    end_exclusive: str,
    timeframes: Iterable[str] = ("1h", "4h"),
    verify_hashes: bool = False,
) -> CatalogWindow:
    """Load a frozen time window without returning future Locked OOS rows.

    Formal runs normally bind to the hashes already frozen and verified by V19.
    Re-hashing a mixed historical/future partition would itself read Locked OOS
    bytes, so ``verify_hashes`` is intentionally opt-in for non-formal audits.
    """

    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end_exclusive)
    if start_ts.tzinfo is None:
        start_ts = start_ts.tz_localize("UTC")
    else:
        start_ts = start_ts.tz_convert("UTC")
    if end_ts.tzinfo is None:
        end_ts = end_ts.tz_localize("UTC")
    else:
        end_ts = end_ts.tz_convert("UTC")
    if start_ts >= end_ts:
        raise ValueError("catalog_window_invalid")

    payload: dict[str, Any] = json.loads(Path(catalog_path).read_text(encoding="utf-8"))
    allowed = {str(value) for value in timeframes}
    frames: dict[str, dict[str, pd.DataFrame]] = {value: {} for value in allowed}
    funding: dict[str, pd.DataFrame] = {}
    dataset_rows: list[dict[str, Any]] = []
    for row in payload.get("datasets", []):
        data_type = str(row.get("dataType") or "")
        timeframe = str(row.get("timeframe") or "")
        symbols = [str(value) for value in row.get("symbols", [])]
        if len(symbols) != 1:
            continue
        symbol = symbols[0]
        path = Path(str(row.get("sourcePath") or ""))
        if data_type in {"ohlcv", "market_ohlcv"} and timeframe in allowed:
            pass
        elif data_type == "funding":
            pass
        else:
            continue
        if not path.is_file():
            raise FileNotFoundError(path)
        expected_hash = str(row.get("contentHash") or "")
        if verify_hashes and expected_hash and sha256_file(path) != expected_hash:
            raise ValueError(f"catalog_partition_hash_mismatch:{row.get('datasetId')}")

        if data_type == "funding":
            frame = _bounded_parquet_read(
                path,
                timestamp_column="timestampUtc",
                start=start_ts,
                end_exclusive=end_ts,
                columns=[
                    "timestampUtc",
                    "sourceTimestamp",
                    "exchange",
                    "marketType",
                    "instrumentId",
                    "fundingRate",
                ],
            )
            frame["timestampUtc"] = pd.to_datetime(frame["timestampUtc"], utc=True)
            funding[symbol] = frame.sort_values("timestampUtc").reset_index(drop=True)
            timestamp_column = "timestampUtc"
        else:
            frame = _bounded_parquet_read(
                path,
                timestamp_column="date",
                start=start_ts,
                end_exclusive=end_ts,
                columns=["date", "open", "high", "low", "close", "volume"],
            )
            frame["date"] = pd.to_datetime(frame["date"], utc=True)
            frames[timeframe][symbol] = frame.sort_values("date").reset_index(drop=True)
            timestamp_column = "date"
        returned_max = frame[timestamp_column].max() if len(frame) else None
        if returned_max is not None and returned_max >= end_ts:
            raise ValueError("future_locked_oos_row_returned")
        dataset_rows.append(
            {
                "datasetId": str(row.get("datasetId") or ""),
                "dataType": data_type,
                "timeframe": timeframe or None,
                "instrumentId": symbol,
                "returnedRowCount": int(len(frame)),
                "returnedMaximumTimestamp": (
                    returned_max.isoformat() if returned_max is not None else None
                ),
                "hashVerificationMode": (
                    "current_full_file" if verify_hashes else "v19_frozen_catalog_binding"
                ),
            }
        )

    missing = sorted(timeframe for timeframe, values in frames.items() if not values)
    if missing:
        raise ValueError("catalog_timeframes_missing:" + ",".join(missing))
    access_report = {
        "schemaVersion": "automatic_catalog_window_access_v1",
        "start": start_ts.isoformat(),
        "endExclusive": end_ts.isoformat(),
        "datasetCount": len(dataset_rows),
        "datasets": dataset_rows,
        "futureLockedOosRowsReturned": 0,
        "lockedOosContentReadCount": 0,
        "networkAccessCount": 0,
        "wholeFileFallbackUsed": False,
    }
    return CatalogWindow(frames=frames, funding=funding, access_report=access_report)


__all__ = ["CatalogWindow", "load_catalog_frames", "load_catalog_window"]
