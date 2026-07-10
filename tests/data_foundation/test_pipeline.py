from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from alphapilot.data_foundation.pipeline import run_data_foundation
from alphapilot.evolution.registry.database import connect_registry
from alphapilot.evolution.registry.repositories import RegistryRepository


def _write_swap_file(
    root: Path,
    symbol: str,
    *,
    row_count: int = 4,
    confirmed: list[int] | None = None,
) -> None:
    folder = root / "合约数据" / "swap_candles_15m" / f"{symbol}_USDT_SWAP"
    folder.mkdir(parents=True)
    path = folder / f"{symbol}_USDT_SWAP_swap_candles_15m_ALL.xlsx"
    timestamps = [1577836800000 + index * 900_000 for index in range(row_count)]
    pd.DataFrame(
        {
            "market_type": ["swap"] * row_count,
            "inst_id": [f"{symbol}-USDT-SWAP"] * row_count,
            "bar": ["15m"] * row_count,
            "timestamp_ms": timestamps,
            "open": [10 + index for index in range(row_count)],
            "high": [12 + index for index in range(row_count)],
            "low": [9 + index for index in range(row_count)],
            "close": [11 + index for index in range(row_count)],
            "volume_quote_currency": [100 + index * 10 for index in range(row_count)],
            "confirmed": confirmed or [1] * row_count,
        }
    ).to_excel(path, index=False)


class DataFoundationPipelineTests(unittest.TestCase):
    def test_existing_canonical_preserves_source_cleaning_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            raw_root = base / "raw"
            _write_swap_file(raw_root, "BTC", confirmed=[1, 1, 1, 0])
            arguments = {
                "raw_root": raw_root,
                "market_root": base / "market",
                "registry_path": base / "registry.sqlite",
                "symbols": ("BTC",),
                "timeframes": ("15m",),
                "register_snapshot": False,
            }

            created = run_data_foundation(**arguments)
            with patch(
                "alphapilot.data_foundation.canonical.read_ohlcv",
                side_effect=AssertionError("matching metadata should avoid re-reading the raw source"),
            ):
                reused = run_data_foundation(**arguments)

        self.assertEqual(created["canonicalAssets"][0]["status"], "created")
        self.assertEqual(reused["canonicalAssets"][0]["status"], "existing")
        self.assertEqual(reused["canonicalAssets"][0]["quality"]["sourceRows"], 4)
        self.assertEqual(reused["canonicalAssets"][0]["quality"]["rows"], 3)
        self.assertEqual(reused["canonicalAssets"][0]["quality"]["unconfirmedDroppedCount"], 1)

    def test_snapshot_cutoff_uses_earliest_group_end(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            raw_root = base / "raw"
            _write_swap_file(raw_root, "BTC", row_count=4)
            _write_swap_file(raw_root, "ETH", row_count=3)

            report = run_data_foundation(
                raw_root=raw_root,
                market_root=base / "market",
                registry_path=base / "registry.sqlite",
                symbols=("BTC", "ETH"),
                timeframes=("15m",),
                register_snapshot=False,
            )

        snapshot = report["dataSnapshot"]
        self.assertEqual(snapshot["endTime"], "2020-01-01T00:45:00+00:00")
        self.assertEqual(snapshot["pointInTimeCutoff"], "2020-01-01T00:30:00+00:00")

    def test_unknown_timeframe_fails_instead_of_silently_skipping(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            with self.assertRaisesRegex(ValueError, "Unsupported timeframe"):
                run_data_foundation(
                    raw_root=base,
                    market_root=base / "market",
                    registry_path=base / "registry.sqlite",
                    symbols=("BTC",),
                    timeframes=("1",),
                    register_snapshot=False,
                )

    def test_smoke_pipeline_registers_verified_unknown_provenance_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            raw_root = base / "raw"
            for symbol in ("BTC", "ETH", "SOL"):
                _write_swap_file(raw_root, symbol)
            market_root = base / "market"
            registry_path = base / "registry.sqlite"

            report = run_data_foundation(
                raw_root=raw_root,
                market_root=market_root,
                registry_path=registry_path,
                symbols=("BTC", "ETH", "SOL"),
                timeframes=("15m",),
                market_type="swap",
                exchange="unknown",
                hash_mode="selected",
            )
            connection = connect_registry(registry_path)
            try:
                snapshot_id = report["dataSnapshot"]["dataSnapshotId"]
                loaded = RegistryRepository(connection).get_data_snapshot(snapshot_id)
            finally:
                connection.close()

        self.assertEqual(report["canonicalCreatedOrExistingCount"], 3)
        self.assertEqual(report["canonicalFailedCount"], 0)
        self.assertTrue(report["dataSnapshotVerification"]["valid"])
        self.assertTrue(report["dataSnapshotRegistered"])
        self.assertFalse(report["formalPromotionEligible"])
        self.assertEqual(report["blockers"], ["source_provenance_not_verified"])
        self.assertIsNotNone(loaded)


if __name__ == "__main__":
    unittest.main()
