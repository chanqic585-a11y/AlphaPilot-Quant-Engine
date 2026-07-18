from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from alphapilot.research_factory.catalog_frames import load_catalog_window


def _ohlcv(path: Path) -> None:
    dates = pd.date_range("2024-12-31 20:00", periods=4, freq="4h", tz="UTC")
    pd.DataFrame(
        {
            "date": dates,
            "open": [1.0, 2.0, 3.0, 4.0],
            "high": [2.0, 3.0, 4.0, 5.0],
            "low": [0.5, 1.5, 2.5, 3.5],
            "close": [1.5, 2.5, 3.5, 4.5],
            "volume": [10.0, 11.0, 12.0, 13.0],
        }
    ).to_parquet(path, index=False)


def _funding(path: Path) -> None:
    dates = pd.date_range("2024-12-31 16:00", periods=4, freq="8h", tz="UTC")
    pd.DataFrame(
        {
            "timestampUtc": dates,
            "sourceTimestamp": dates,
            "exchange": "binance",
            "marketType": "swap",
            "instrumentId": "BTC-USDT-SWAP",
            "fundingRate": [0.0001, 0.0002, -0.0001, 0.0001],
        }
    ).to_parquet(path, index=False)


def test_catalog_window_never_returns_future_locked_oos_rows(tmp_path: Path) -> None:
    ohlcv = tmp_path / "btc-4h.parquet"
    funding = tmp_path / "btc-funding.parquet"
    _ohlcv(ohlcv)
    _funding(funding)
    catalog = tmp_path / "catalog.json"
    catalog.write_text(
        json.dumps(
            {
                "datasets": [
                    {
                        "datasetId": "btc-4h",
                        "dataType": "ohlcv",
                        "timeframe": "4h",
                        "symbols": ["BTC-USDT-SWAP"],
                        "sourcePath": str(ohlcv),
                    },
                    {
                        "datasetId": "btc-funding",
                        "dataType": "funding",
                        "symbols": ["BTC-USDT-SWAP"],
                        "sourcePath": str(funding),
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    window = load_catalog_window(
        catalog,
        start="2024-12-31T00:00:00Z",
        end_exclusive="2025-01-01T00:00:00Z",
        timeframes=("4h",),
        verify_hashes=False,
    )

    assert window.frames["4h"]["BTC-USDT-SWAP"]["date"].max() < pd.Timestamp(
        "2025-01-01T00:00:00Z"
    )
    assert window.funding["BTC-USDT-SWAP"]["timestampUtc"].max() < pd.Timestamp(
        "2025-01-01T00:00:00Z"
    )
    assert window.access_report["lockedOosContentReadCount"] == 0
    assert window.access_report["futureLockedOosRowsReturned"] == 0
