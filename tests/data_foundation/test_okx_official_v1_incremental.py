from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

import pandas as pd

from alphapilot import data_foundation
from alphapilot.data_foundation.okx_official_v1 import OkxOfficialV1Layout
from alphapilot.data_foundation.okx_official_v1_incremental import (
    OkxOfficialV1IncrementalCollector,
)


class FakePublicClient:
    def __init__(self) -> None:
        self.request_audit_records: list[dict[str, Any]] = []
        self.funding_rows = [
            {"fundingTime": "1000", "fundingRate": "0.0001", "realizedRate": "0.0001"},
            {"fundingTime": "2000", "fundingRate": "0.0002", "realizedRate": "0.0002"},
        ]

    def _receipt(self, path: str, completed_at: str = "2026-07-19T00:00:01+00:00") -> None:
        self.request_audit_records.append(
            {
                "path": path,
                "requestCompletedAt": completed_at,
                "rawPayloadSha256": hashlib.sha256(path.encode("utf-8")).hexdigest(),
            }
        )

    def funding_rate_history(self, **_: Any) -> list[dict[str, Any]]:
        self._receipt("/api/v5/public/funding-rate-history")
        return [dict(row) for row in self.funding_rows]

    def public_instruments(self, **_: Any) -> list[dict[str, Any]]:
        self._receipt("/api/v5/public/instruments")
        return [
            {
                "instId": "BTC-USDT-SWAP",
                "instType": "SWAP",
                "uly": "BTC-USDT",
                "state": "live",
                "tickSz": "0.1",
                "lotSz": "0.01",
                "minSz": "0.01",
            }
        ]

    def open_interest(self, **_: Any) -> list[dict[str, Any]]:
        self._receipt("/api/v5/public/open-interest")
        return [{"instId": "BTC-USDT-SWAP", "oi": "123", "ts": "1000"}]

    def current_funding_rate(self, **_: Any) -> list[dict[str, Any]]:
        self._receipt("/api/v5/public/funding-rate")
        return [{"instId": "BTC-USDT-SWAP", "fundingRate": "0.0001", "ts": "1000"}]

    def mark_price(self, **_: Any) -> list[dict[str, Any]]:
        self._receipt("/api/v5/public/mark-price")
        return [{"instId": "BTC-USDT-SWAP", "markPx": "60000", "ts": "1000"}]

    def index_ticker(self, **_: Any) -> list[dict[str, Any]]:
        self._receipt("/api/v5/market/index-tickers")
        return [{"instId": "BTC-USDT", "idxPx": "59990", "ts": "1000"}]

    def public_tickers(self, **_: Any) -> list[dict[str, Any]]:
        self._receipt("/api/v5/market/tickers")
        return [
            {
                "instId": "BTC-USDT-SWAP",
                "bidPx": "59999",
                "askPx": "60001",
                "last": "60000",
                "ts": "1000",
            }
        ]

    def order_book(self, **_: Any) -> list[dict[str, Any]]:
        self._receipt("/api/v5/market/books")
        return [{"asks": [["60001", "2"]], "bids": [["59999", "3"]], "ts": "1000"}]


class OkxOfficialV1IncrementalCollectorTests(unittest.TestCase):
    def test_incremental_collector_is_available_from_data_foundation_package(self) -> None:
        self.assertIs(
            data_foundation.OkxOfficialV1IncrementalCollector,
            OkxOfficialV1IncrementalCollector,
        )

    def test_funding_collection_writes_only_unseen_timestamps(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            client = FakePublicClient()
            collector = OkxOfficialV1IncrementalCollector(
                warehouse_root=Path(directory),
                client=client,
                instruments=("BTC-USDT-SWAP",),
            )

            first = collector.collect_task(
                "funding_increment", "2026-07-19T00:00:00+00:00"
            )
            second = collector.collect_task(
                "funding_increment", "2026-07-19T01:00:00+00:00"
            )

            self.assertEqual(first.row_count, 2)
            self.assertEqual(second.row_count, 0)
            self.assertEqual(second.status, "no_new_rows")
            self.assertIsNone(second.artifact_path)

    def test_funding_seeds_high_water_from_v34b_parquet(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            layout = OkxOfficialV1Layout.from_warehouse(root)
            legacy_path = (
                layout.canonicalRoot
                / "okx"
                / "swap"
                / "funding"
                / "BTC-USDT-SWAP"
                / "funding-history-legacy.parquet"
            )
            legacy_path.parent.mkdir(parents=True, exist_ok=True)
            pd.DataFrame(
                [{"instrumentId": "BTC-USDT-SWAP", "fundingTime": 2000}]
            ).to_parquet(legacy_path, index=False)
            client = FakePublicClient()
            client.funding_rows.append(
                {"fundingTime": "3000", "fundingRate": "0.0003", "realizedRate": "0.0003"}
            )
            collector = OkxOfficialV1IncrementalCollector(
                warehouse_root=root,
                client=client,
                instruments=("BTC-USDT-SWAP",),
            )

            result = collector.collect_task(
                "funding_increment", "2026-07-19T00:00:00+00:00"
            )
            rows = pd.read_parquet(Path(result.artifact_path or ""))

            self.assertEqual(result.row_count, 1)
            self.assertEqual(rows["fundingTime"].tolist(), [3000])

    def test_metadata_is_pit_only_and_keeps_public_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            collector = OkxOfficialV1IncrementalCollector(
                warehouse_root=Path(directory),
                client=FakePublicClient(),
                instruments=("BTC-USDT-SWAP",),
            )

            result = collector.collect_task(
                "instrument_metadata", "2026-07-19T00:00:00+00:00"
            )
            payload = json.loads(Path(result.artifact_path or "").read_text(encoding="utf-8"))

            self.assertEqual(payload["pitHistoryBeginsAt"], "2026-07-19T00:00:00+00:00")
            self.assertFalse(payload["historicalStateReconstructed"])
            self.assertEqual(payload["sourceEndpoint"], "/api/v5/public/instruments")
            self.assertEqual(len(payload["sourceResponseHash"]), 64)
            self.assertEqual(payload["observedAt"], "2026-07-19T00:00:00+00:00")

    def test_identical_snapshot_reuses_the_content_addressed_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            collector = OkxOfficialV1IncrementalCollector(
                warehouse_root=Path(directory),
                client=FakePublicClient(),
                instruments=("BTC-USDT-SWAP",),
            )

            first = collector.collect_task(
                "open_interest", "2026-07-19T00:00:00+00:00"
            )
            second = collector.collect_task(
                "open_interest", "2026-07-19T00:00:00+00:00"
            )

            self.assertEqual(first.artifact_path, second.artifact_path)
            self.assertEqual(first.artifact_sha256, second.artifact_sha256)
            self.assertTrue(second.details["artifactReused"])

    def test_all_public_snapshot_tasks_emit_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            collector = OkxOfficialV1IncrementalCollector(
                warehouse_root=Path(directory),
                client=FakePublicClient(),
                instruments=("BTC-USDT-SWAP",),
            )

            for task_name in (
                "instrument_state",
                "current_funding",
                "open_interest",
                "mark_price",
                "index_price",
                "ticker_spread",
                "order_book_summary",
            ):
                with self.subTest(task_name=task_name):
                    result = collector.collect_task(
                        task_name,
                        "2026-07-19T00:00:00+00:00",
                    )
                    payload = json.loads(
                        Path(result.artifact_path or "").read_text(encoding="utf-8")
                    )
                    self.assertEqual(payload["taskName"], task_name)
                    self.assertEqual(payload["observedAt"], "2026-07-19T00:00:00+00:00")
                    self.assertTrue(payload["publicDataOnly"])
                    self.assertTrue(payload["records"])
                    self.assertEqual(len(payload["records"][0]["sourceHash"]), 64)
                    self.assertTrue(payload["records"][0]["sourceEndpoint"].startswith("/api/v5/"))


if __name__ == "__main__":
    unittest.main()
