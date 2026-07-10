from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from alphapilot.data_foundation.okx_public import (
    OkxPublicClient,
    collect_public_increment,
    latest_canonical_timestamp,
)


class _Response:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


class OkxPublicTests(unittest.TestCase):
    def test_latest_completed_candles_excludes_open_exchange_bar(self) -> None:
        def opener(_request: object, timeout: int) -> _Response:
            self.assertEqual(timeout, 30)
            return _Response(
                {
                    "code": "0",
                    "msg": "",
                    "data": [
                        ["2000", "10", "12", "9", "11", "1", "1", "100", "0"],
                        ["1000", "9", "11", "8", "10", "1", "1", "90", "1"],
                    ],
                }
            )

        frame = OkxPublicClient(opener=opener).latest_completed_candles(
            instrument_id="BTC-USDT-SWAP", timeframe="15m"
        )

        self.assertEqual(frame["timestamp_ms"].tolist(), [1000])
        self.assertEqual(frame["confirmed"].tolist(), [1])

    def test_history_candles_filters_cutoff_and_unconfirmed_rows(self) -> None:
        calls: list[str] = []

        def opener(request: object, timeout: int) -> _Response:
            calls.append(getattr(request, "full_url"))
            self.assertEqual(timeout, 30)
            return _Response(
                {
                    "code": "0",
                    "msg": "",
                    "data": [
                        ["2000", "10", "12", "9", "11", "1", "1", "100", "1"],
                        ["1000", "9", "11", "8", "10", "1", "1", "90", "1"],
                        ["3000", "11", "13", "10", "12", "1", "1", "110", "0"],
                    ],
                }
            )

        client = OkxPublicClient(opener=opener, throttle_seconds=0)
        frame, request_count = client.history_candles(
            instrument_id="BTC-USDT-SWAP",
            timeframe="15m",
            start_exclusive_ms=1000,
            max_pages=1,
        )

        self.assertEqual(request_count, 1)
        self.assertEqual(frame["timestamp_ms"].tolist(), [2000])
        self.assertIn("instId=BTC-USDT-SWAP", calls[0])
        self.assertNotIn("OK-ACCESS", str(calls[0]))

    def test_increment_uses_latest_unknown_provenance_canonical_cutoff(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_dir = root / "unknown" / "swap" / "ohlcv" / "BTC-USDT-SWAP" / "15m"
            source_dir.mkdir(parents=True)
            pd.DataFrame({"timestamp_ms": [0, 900_000]}).to_parquet(source_dir / "base.parquet", index=False)

            class StubClient:
                base_url = "https://example.test"

                @staticmethod
                def history_candles(**kwargs: object) -> tuple[pd.DataFrame, int]:
                    self.assertEqual(kwargs["start_exclusive_ms"], 900_000)
                    frame = pd.DataFrame(
                        {
                            "timestamp_ms": [1_800_000],
                            "date": pd.to_datetime([1_800_000], unit="ms", utc=True),
                            "open": [10.0],
                            "high": [12.0],
                            "low": [9.0],
                            "close": [11.0],
                            "volume": [100.0],
                            "confirmed": [1],
                        }
                    )
                    return frame, 1

            result = collect_public_increment(
                client=StubClient(),  # type: ignore[arg-type]
                canonical_root=root,
                instrument_id="BTC-USDT-SWAP",
                timeframe="15m",
            )

            latest = latest_canonical_timestamp(
                root,
                market_type="swap",
                instrument_id="BTC-USDT-SWAP",
                timeframe="15m",
            )

        self.assertEqual(result.status, "collected")
        self.assertEqual(result.startExclusiveMs, 900_000)
        self.assertEqual(result.rows, 1)
        self.assertEqual(result.continuityStatus, "contiguous")
        self.assertEqual(result.gapBars, 0)
        self.assertEqual(latest, 1_800_000)

    def test_latest_cutoff_prefers_verified_okx_increment(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            unknown_dir = root / "unknown" / "swap" / "ohlcv" / "BTC-USDT-SWAP" / "1h"
            okx_dir = root / "okx" / "swap" / "ohlcv" / "BTC-USDT-SWAP" / "1h"
            unknown_dir.mkdir(parents=True)
            okx_dir.mkdir(parents=True)
            pd.DataFrame({"timestamp_ms": [3_600_000]}).to_parquet(unknown_dir / "base.parquet", index=False)
            pd.DataFrame({"timestamp_ms": [7_200_000]}).to_parquet(okx_dir / "increment.parquet", index=False)

            latest = latest_canonical_timestamp(
                root,
                market_type="swap",
                instrument_id="BTC-USDT-SWAP",
                timeframe="1h",
            )

        self.assertEqual(latest, 7_200_000)

    def test_invalid_timeframe_is_rejected_before_cutoff_lookup(self) -> None:
        class StubClient:
            base_url = "https://example.test"

        with self.assertRaisesRegex(ValueError, "Unsupported OKX timeframe"):
            collect_public_increment(
                client=StubClient(),  # type: ignore[arg-type]
                canonical_root="missing",
                instrument_id="BTC-USDT-SWAP",
                timeframe="1",
            )


if __name__ == "__main__":
    unittest.main()
