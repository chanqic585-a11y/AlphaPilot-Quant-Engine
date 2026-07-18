"""Load only frozen catalog partitions required by the automatic program."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from alphapilot.evolution.registry.hashing import sha256_file


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


__all__ = ["load_catalog_frames"]
