from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from alphapilot.data_foundation.catalog import build_raw_catalog, discover_raw_assets


class RawCatalogTests(unittest.TestCase):
    def test_all_partition_wins_and_unsafe_files_are_excluded(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            folder = root / "合约数据" / "swap_candles_15m" / "BTC_USDT_SWAP"
            folder.mkdir(parents=True)
            annual = folder / "BTC_USDT_SWAP_swap_candles_15m_2025.xlsx"
            combined = folder / "BTC_USDT_SWAP_swap_candles_15m_ALL.xlsx"
            checkpoint = folder / "BTC_USDT_SWAP_swap_candles_15m_CKPT.csv"
            annual.write_bytes(b"annual")
            combined.write_bytes(b"all")
            checkpoint.write_bytes(b"checkpoint")

            assets = discover_raw_assets(root)

        by_name = {Path(asset.sourcePath).name: asset for asset in assets}
        self.assertFalse(by_name[annual.name].selected)
        self.assertEqual(by_name[annual.name].exclusionReason, "duplicate_of_all_partition")
        self.assertTrue(by_name[combined.name].selected)
        self.assertFalse(by_name[checkpoint.name].selected)
        self.assertEqual(by_name[checkpoint.name].exclusionReason, "checkpoint_file")

    def test_catalog_hash_checkpoint_reuses_unchanged_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "raw"
            source = root / "5m" / "BTC_USDT_5m_from_20180101.csv"
            source.parent.mkdir(parents=True)
            source.write_text("timestamp,open,high,low,close,vol\n1,1,1,1,1,1\n", encoding="utf-8")
            checkpoint = Path(directory) / "checkpoint.json"

            first = build_raw_catalog(root, hash_mode="selected", checkpoint_path=checkpoint)
            with patch("alphapilot.data_foundation.catalog.write_json_atomic") as checkpoint_writer:
                second = build_raw_catalog(root, hash_mode="selected", checkpoint_path=checkpoint)

        self.assertEqual(first["hashSummary"]["hashedFileCount"], 1)
        self.assertEqual(second["hashSummary"]["hashedFileCount"], 0)
        self.assertEqual(second["hashSummary"]["reusedHashCount"], 1)
        self.assertEqual(first["assets"][0]["sha256"], second["assets"][0]["sha256"])
        checkpoint_writer.assert_not_called()


if __name__ == "__main__":
    unittest.main()
