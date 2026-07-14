from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

import pandas as pd

from alphapilot.data_foundation.official_resume import (
    OfficialResumeStore,
    ResumeIdentity,
)


def _identity() -> ResumeIdentity:
    return ResumeIdentity(
        strategyDataContractId="contract-a",
        key="BTC-USDT-SWAP|5m",
        instrumentId="BTC-USDT-SWAP",
        timeframe="5m",
        sourceEndpoint="https://official.example/history-candles",
        collectionStartMs=1_700_000_000_000,
        baseSha256=None,
    )


def _frame(start: str, periods: int = 3) -> pd.DataFrame:
    timestamps = pd.date_range(start, periods=periods, freq="5min", tz="UTC")
    return pd.DataFrame(
        {
            "timestamp_ms": timestamps.as_unit("ms").astype("int64"),
            "date": timestamps,
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.5,
            "volume": 1000.0,
            "confirmed": 1,
        }
    )


class OfficialResumeStoreTests(unittest.TestCase):
    def test_partial_chunks_survive_a_new_store_instance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "official-resume"
            identity = _identity()
            frame = _frame("2026-07-14T00:00:00Z")
            oldest = int(frame["timestamp_ms"].min())
            OfficialResumeStore(root).append(
                identity,
                frame,
                request_count=25,
                oldest_timestamp_ms=oldest,
            )

            resumed = OfficialResumeStore(root).load(identity)

            self.assertEqual(len(resumed.frame), len(frame))
            self.assertEqual(resumed.requestCount, 25)
            self.assertEqual(resumed.oldestTimestampMs, oldest)
            self.assertEqual(resumed.chunkCount, 1)

    def test_overlapping_chunks_are_deduplicated(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "official-resume"
            identity = _identity()
            store = OfficialResumeStore(root)
            first = _frame("2026-07-14T00:00:00Z")
            second = _frame("2026-07-14T00:10:00Z")
            store.append(
                identity,
                first,
                request_count=25,
                oldest_timestamp_ms=int(first["timestamp_ms"].min()),
            )
            store.append(
                identity,
                second,
                request_count=50,
                oldest_timestamp_ms=int(first["timestamp_ms"].min()),
            )

            resumed = store.load(identity)

            self.assertEqual(len(resumed.frame), 5)
            self.assertTrue(resumed.frame["timestamp_ms"].is_unique)
            self.assertEqual(resumed.chunkCount, 2)

    def test_identity_mismatch_does_not_reuse_chunks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "official-resume"
            identity = _identity()
            frame = _frame("2026-07-14T00:00:00Z")
            OfficialResumeStore(root).append(
                identity,
                frame,
                request_count=25,
                oldest_timestamp_ms=int(frame["timestamp_ms"].min()),
            )

            mismatched = OfficialResumeStore(root).load(
                replace(identity, baseSha256="different-base")
            )

            self.assertTrue(mismatched.frame.empty)
            self.assertEqual(mismatched.requestCount, 0)
            self.assertIsNone(mismatched.oldestTimestampMs)

    def test_corrupt_chunk_is_not_reused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "official-resume"
            identity = _identity()
            frame = _frame("2026-07-14T00:00:00Z")
            store = OfficialResumeStore(root)
            store.append(
                identity,
                frame,
                request_count=25,
                oldest_timestamp_ms=int(frame["timestamp_ms"].min()),
            )
            chunk = next(root.rglob("chunk-*.parquet"))
            chunk.write_bytes(b"corrupt")

            resumed = store.load(identity)

            self.assertTrue(resumed.frame.empty)
            self.assertEqual(resumed.chunkCount, 0)

    def test_clear_removes_only_the_matching_resume_partition(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "official-resume"
            identity = _identity()
            other = replace(identity, key="ETH-USDT-SWAP|5m", instrumentId="ETH-USDT-SWAP")
            frame = _frame("2026-07-14T00:00:00Z")
            store = OfficialResumeStore(root)
            for item in (identity, other):
                store.append(
                    item,
                    frame,
                    request_count=25,
                    oldest_timestamp_ms=int(frame["timestamp_ms"].min()),
                )

            store.clear(identity)

            self.assertTrue(store.load(identity).frame.empty)
            self.assertFalse(store.load(other).frame.empty)


if __name__ == "__main__":
    unittest.main()
