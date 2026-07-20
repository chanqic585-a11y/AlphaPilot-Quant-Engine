from __future__ import annotations

from pathlib import Path

import pandas as pd

from alphapilot.mechanism_breakthrough.data_catalog import (
    discover_local_ohlcv,
    load_development_frame,
)


def _write_frame(path: Path, rows: int, *, start: str = "2024-01-01") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    dates = pd.date_range(start, periods=rows, freq="h", tz="UTC")
    frame = pd.DataFrame(
        {
            "date": dates,
            "open": range(rows),
            "high": [value + 2 for value in range(rows)],
            "low": [max(0, value - 1) for value in range(rows)],
            "close": [value + 1 for value in range(rows)],
            "volume": [100.0] * rows,
            "instrument_id": ["BTC-USDT-SWAP"] * rows,
            "timeframe": ["1h"] * rows,
        }
    )
    frame.to_parquet(path, index=False)


def test_catalog_reuses_fullest_local_asset_without_network(tmp_path: Path) -> None:
    base = tmp_path / "canonical" / "okx" / "swap" / "ohlcv" / "BTC-USDT-SWAP" / "1h"
    _write_frame(base / "1-10-old.parquet", 10)
    _write_frame(base / "1-20-new.parquet", 20)

    catalog = discover_local_ohlcv(tmp_path / "canonical", timeframes=("1h",))

    assert len(catalog.assets) == 1
    assert catalog.assets[0].path.name == "1-20-new.parquet"
    assert catalog.network_calls == 0


def test_development_loader_reserves_locked_oos_without_reading_it(tmp_path: Path) -> None:
    path = tmp_path / "BTC.parquet"
    _write_frame(path, 100)

    frame, audit = load_development_frame(path, development_fraction=0.8)

    assert len(frame) == 80
    assert audit["reservedLockedOosRowCount"] == 20
    assert audit["lockedOosReadCount"] == 0

