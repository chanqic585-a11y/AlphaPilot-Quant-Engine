from __future__ import annotations

import json
import inspect
import tempfile
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pandas as pd

from alphapilot.data_foundation.okx_public import (
    OkxPublicClient,
    collect_public_increment,
    latest_canonical_timestamp,
)
from alphapilot.data_foundation import okx_public


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
    def test_history_candles_reports_page_level_progress(self) -> None:
        pages = [
            [
                ["5000", "10", "12", "9", "11", "1", "1", "100", "1"],
                ["4000", "9", "11", "8", "10", "1", "1", "90", "1"],
            ],
            [
                ["3000", "8", "10", "7", "9", "1", "1", "80", "1"],
                ["2000", "7", "9", "6", "8", "1", "1", "70", "1"],
            ],
        ]
        pages_for_progress = [
            [list(item) for item in pages[0]],
            [list(pages[1][0])],
        ]
        progress: list[dict[str, object]] = []

        def opener(_request: object, timeout: int) -> _Response:
            self.assertEqual(timeout, 30)
            return _Response({"code": "0", "msg": "", "data": pages.pop(0)})

        frame, request_count = OkxPublicClient(
            opener=opener,
            throttle_seconds=0,
        ).history_candles(
            instrument_id="BTC-USDT-SWAP",
            timeframe="5m",
            start_exclusive_ms=2500,
            max_pages=5,
            page_progress=progress.append,
        )

        self.assertEqual(request_count, 2)
        self.assertEqual(frame["timestamp_ms"].tolist(), [3000, 4000, 5000])
        self.assertEqual(
            progress,
            [
                {
                    "requestCount": 1,
                    "rowCount": 2,
                    "oldestTimestampMs": 4000,
                    "maxPages": 5,
                    "isFinalPage": False,
                    "pageRows": pages_for_progress[0],
                },
                {
                    "requestCount": 2,
                    "rowCount": 3,
                    "oldestTimestampMs": 2000,
                    "maxPages": 5,
                    "isFinalPage": True,
                    "pageRows": pages_for_progress[1],
                },
            ],
        )

    def test_history_candles_starts_after_durable_resume_cursor(self) -> None:
        calls: list[str] = []

        def opener(request: object, timeout: int) -> _Response:
            self.assertEqual(timeout, 30)
            calls.append(str(getattr(request, "full_url")))
            return _Response(
                {
                    "code": "0",
                    "msg": "",
                    "data": [
                        ["3000", "10", "12", "9", "11", "1", "1", "100", "1"],
                        ["2000", "9", "11", "8", "10", "1", "1", "90", "1"],
                    ],
                }
            )

        OkxPublicClient(opener=opener, throttle_seconds=0).history_candles(
            instrument_id="BTC-USDT-SWAP",
            timeframe="5m",
            start_exclusive_ms=2500,
            initial_after_ms=4000,
            max_pages=1,
        )

        query = parse_qs(urlparse(calls[0]).query)
        self.assertEqual(query["after"], ["4000"])

    def test_history_candles_stops_before_requesting_the_next_page(self) -> None:
        calls: list[str] = []
        stop_checks = 0

        def opener(request: object, timeout: int) -> _Response:
            self.assertEqual(timeout, 30)
            calls.append(str(getattr(request, "full_url")))
            return _Response(
                {
                    "code": "0",
                    "msg": "",
                    "data": [
                        ["3000", "10", "12", "9", "11", "1", "1", "100", "1"],
                        ["2000", "9", "11", "8", "10", "1", "1", "90", "1"],
                    ],
                }
            )

        def stop_requested() -> bool:
            nonlocal stop_checks
            stop_checks += 1
            return stop_checks > 1

        self.assertTrue(hasattr(okx_public, "OkxHistoryCollectionStopped"))
        self.assertIn(
            "stop_requested",
            inspect.signature(OkxPublicClient.history_candles).parameters,
        )
        client = OkxPublicClient(opener=opener, throttle_seconds=0)
        with self.assertRaises(okx_public.OkxHistoryCollectionStopped):
            client.history_candles(
                instrument_id="BTC-USDT-SWAP",
                timeframe="15m",
                start_exclusive_ms=1000,
                max_pages=3,
                stop_requested=stop_requested,
            )

        self.assertEqual(len(calls), 1)

    def test_public_metadata_and_funding_methods_use_unauthenticated_endpoints(self) -> None:
        calls: list[str] = []

        def opener(request: object, timeout: int) -> _Response:
            self.assertEqual(timeout, 30)
            url = str(getattr(request, "full_url"))
            calls.append(url)
            path = urlparse(url).path
            if path.endswith("/public/instruments"):
                data: list[object] = [
                    {"instId": "BTC-USDT-SWAP", "instType": "SWAP", "state": "live"}
                ]
            elif path.endswith("/public/funding-rate-history"):
                data = [{"instId": "BTC-USDT-SWAP", "fundingRate": "0.0001", "fundingTime": "1000"}]
            else:
                data = [["1000", "1", "2", "0.5", "1.5", "1", "1", "10", "1"]]
            return _Response({"code": "0", "msg": "", "data": data})

        client = OkxPublicClient(opener=opener, throttle_seconds=0)
        instruments = client.public_instruments(instrument_type="SWAP")
        funding = client.funding_rate_history(
            instrument_id="BTC-USDT-SWAP", before_ms=2000, limit=50
        )
        candles = client.history_candle_page(
            instrument_id="BTC-USDT-SWAP",
            timeframe="4h",
            after_ms=3000,
            limit=25,
        )

        self.assertEqual(instruments[0]["instId"], "BTC-USDT-SWAP")
        self.assertEqual(funding[0]["fundingRate"], "0.0001")
        self.assertEqual(candles[0][0], "1000")
        parsed = [(urlparse(url).path, parse_qs(urlparse(url).query)) for url in calls]
        self.assertEqual(parsed[0][0], "/api/v5/public/instruments")
        self.assertEqual(parsed[0][1]["instType"], ["SWAP"])
        self.assertEqual(parsed[1][0], "/api/v5/public/funding-rate-history")
        self.assertEqual(parsed[1][1]["before"], ["2000"])
        self.assertEqual(parsed[2][0], "/api/v5/market/history-candles")
        self.assertEqual(parsed[2][1]["after"], ["3000"])
        self.assertTrue(all("OK-ACCESS" not in url for url in calls))

    def test_public_tickers_uses_unauthenticated_swap_market_endpoint(self) -> None:
        calls: list[object] = []

        def opener(request: object, timeout: int) -> _Response:
            self.assertEqual(timeout, 30)
            calls.append(request)
            return _Response(
                {
                    "code": "0",
                    "msg": "",
                    "data": [
                        {
                            "instId": "BTC-USDT-SWAP",
                            "last": "60000",
                            "volCcy24h": "1000",
                        }
                    ],
                }
            )

        tickers = OkxPublicClient(
            opener=opener,
            throttle_seconds=0,
        ).public_tickers(instrument_type="SWAP")

        self.assertEqual(tickers[0]["instId"], "BTC-USDT-SWAP")
        request = calls[0]
        parsed = urlparse(str(getattr(request, "full_url")))
        self.assertEqual(parsed.path, "/api/v5/market/tickers")
        self.assertEqual(parse_qs(parsed.query)["instType"], ["SWAP"])
        headers = {
            str(key).upper(): str(value)
            for key, value in getattr(request, "headers", {}).items()
        }
        self.assertFalse(any(key.startswith("OK-ACCESS") for key in headers))

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
