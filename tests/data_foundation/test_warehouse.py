from __future__ import annotations

import tempfile
import unittest
from collections import namedtuple
from pathlib import Path

from alphapilot.data_foundation.warehouse import (
    MINIMUM_FREE_BYTES,
    WarehouseCapacityError,
    WarehouseLayout,
    ensure_capacity,
)


DiskUsage = namedtuple("DiskUsage", "total used free")


class WarehouseLayoutTests(unittest.TestCase):
    def test_layout_creates_only_alphapilot_owned_directories(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "回测数据"
            source = root / "5m" / "BTC_USDT_5m_from_20260101.csv"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"source-must-not-change")
            before = source.read_bytes()

            layout = WarehouseLayout.from_root(root)
            layout.ensure_directories()

            self.assertEqual(layout.alphaPilotRoot, root.resolve() / "_alphapilot")
            self.assertEqual(layout.localFiveMinuteRoot, root.resolve() / "5m")
            self.assertEqual(layout.localSwapRoot, root.resolve() / "合约数据")
            self.assertEqual(layout.localSpotRoot, root.resolve() / "现货数据")
            self.assertTrue(layout.officialRawRoot.is_dir())
            self.assertTrue(layout.canonicalRoot.is_dir())
            self.assertTrue(layout.catalogRoot.is_dir())
            self.assertTrue(layout.manifestRoot.is_dir())
            self.assertTrue(layout.checkpointRoot.is_dir())
            self.assertTrue(layout.reportRoot.is_dir())
            self.assertTrue(layout.temporaryRoot.is_dir())
            self.assertEqual(source.read_bytes(), before)

    def test_capacity_guard_reserves_fifteen_gibibytes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            layout = WarehouseLayout.from_root(Path(directory) / "回测数据")
            layout.ensure_directories()

            with self.assertRaisesRegex(
                WarehouseCapacityError, "warehouse_free_space_below_guard"
            ):
                ensure_capacity(
                    layout,
                    estimated_bytes=2 * 1024**3,
                    usage_reader=lambda _: DiskUsage(
                        total=20 * 1024**3,
                        used=4 * 1024**3,
                        free=16 * 1024**3,
                    ),
                )

            ensure_capacity(
                layout,
                estimated_bytes=1024**3,
                usage_reader=lambda _: DiskUsage(
                    total=40 * 1024**3,
                    used=20 * 1024**3,
                    free=20 * 1024**3,
                ),
            )
            self.assertEqual(MINIMUM_FREE_BYTES, 15 * 1024**3)


if __name__ == "__main__":
    unittest.main()
