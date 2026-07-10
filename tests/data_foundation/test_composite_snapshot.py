from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from alphapilot.data_foundation.composite_snapshot import (
    build_composite_data_snapshot,
    inspect_canonical_group,
)


def _write_timestamps(path: Path, timestamps: list[int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"timestamp_ms": timestamps}).to_parquet(path, index=False)


class CompositeSnapshotTests(unittest.TestCase):
    def test_composite_snapshot_is_contiguous_and_provenance_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            market_root = root / "market"
            canonical_root = market_root / "canonical"
            base = canonical_root / "unknown" / "swap" / "ohlcv" / "BTC-USDT-SWAP" / "15m" / "base.parquet"
            increment = canonical_root / "okx" / "swap" / "ohlcv" / "BTC-USDT-SWAP" / "15m" / "increment.parquet"
            _write_timestamps(base, [0, 900_000])
            _write_timestamps(increment, [1_800_000, 2_700_000])

            report = build_composite_data_snapshot(
                market_root=market_root,
                registry_path=root / "registry.sqlite",
                instruments=("BTC-USDT-SWAP",),
                timeframes=("15m",),
            )

        self.assertEqual(report["status"], "completed_with_provenance_warning")
        self.assertEqual(report["validGroupCount"], 1)
        self.assertEqual(report["canonicalFileCount"], 2)
        self.assertTrue(report["dataSnapshotVerification"]["valid"])
        self.assertTrue(report["dataSnapshotRegistered"])
        self.assertFalse(report["formalPromotionEligible"])
        self.assertEqual(report["blockers"], ["local_base_source_provenance_not_verified"])
        self.assertEqual(report["dataSnapshot"]["pointInTimeCutoff"], "1970-01-01T00:45:00+00:00")

    def test_gap_across_fragments_blocks_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base = root / "unknown" / "swap" / "ohlcv" / "BTC-USDT-SWAP" / "15m" / "base.parquet"
            increment = root / "okx" / "swap" / "ohlcv" / "BTC-USDT-SWAP" / "15m" / "increment.parquet"
            _write_timestamps(base, [0, 900_000])
            _write_timestamps(increment, [2_700_000])

            quality = inspect_canonical_group(
                [base, increment],
                timeframe="15m",
                canonical_root=root,
            )

        self.assertFalse(quality["valid"])
        self.assertEqual(quality["gapEventCount"], 1)
        self.assertEqual(quality["missingBarCount"], 1)
        self.assertIn("gaps_across_fragments", quality["errors"])


if __name__ == "__main__":
    unittest.main()
