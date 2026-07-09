from __future__ import annotations

import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from alphapilot.evolution.data_lineage.snapshot_registry import (
    build_data_snapshot_manifest,
    register_data_snapshot,
    verify_data_snapshot,
)
from alphapilot.evolution.registry.database import connect_registry
from alphapilot.evolution.registry.repositories import RegistryRepository


class SnapshotRegistryTests(unittest.TestCase):
    @staticmethod
    def _build_manifest(root: Path, data_path: Path) -> dict[str, object]:
        return build_data_snapshot_manifest(
            files=[data_path],
            root=root,
            source="unit_test",
            exchange="okx",
            market_type="swap",
            timeframe="1h",
            start_time=None,
            end_time=None,
            point_in_time_cutoff=None,
            universe_members=["BTC/USDT:USDT"],
        )

    def test_manifest_is_stable_and_detects_file_changes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first_path = root / "a.csv"
            second_path = root / "b.csv"
            first_path.write_text("time,close\n1,10\n", encoding="utf-8")
            second_path.write_text("time,close\n1,20\n", encoding="utf-8")

            left = build_data_snapshot_manifest(
                files=[second_path, first_path],
                root=root,
                source="unit_test",
                exchange="okx",
                market_type="swap",
                timeframe="1h",
                start_time="2026-01-01T00:00:00+00:00",
                end_time="2026-01-02T00:00:00+00:00",
                point_in_time_cutoff="2026-01-02T00:00:00+00:00",
                universe_members=["ETH/USDT:USDT", "BTC/USDT:USDT"],
            )
            right = build_data_snapshot_manifest(
                files=[first_path, second_path],
                root=root,
                source="unit_test",
                exchange="okx",
                market_type="swap",
                timeframe="1h",
                start_time="2026-01-01T00:00:00+00:00",
                end_time="2026-01-02T00:00:00+00:00",
                point_in_time_cutoff="2026-01-02T00:00:00+00:00",
                universe_members=["BTC/USDT:USDT", "ETH/USDT:USDT"],
            )

            self.assertEqual(left["dataSnapshotId"], right["dataSnapshotId"])
            self.assertTrue(verify_data_snapshot(left, root=root)["valid"])

            first_path.write_text("time,close\n1,11\n", encoding="utf-8")
            result = verify_data_snapshot(left, root=root)

        self.assertFalse(result["valid"])
        self.assertIn("sha256_mismatch:a.csv", result["errors"])

    def test_manifest_can_be_registered(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data_path = root / "data.csv"
            data_path.write_text("time,close\n1,10\n", encoding="utf-8")
            manifest = build_data_snapshot_manifest(
                files=[data_path],
                root=root,
                source="unit_test",
                exchange="okx",
                market_type="swap",
                timeframe="1h",
                start_time=None,
                end_time=None,
                point_in_time_cutoff=None,
                universe_members=["BTC/USDT:USDT"],
            )
            connection = connect_registry(root / "registry.sqlite")
            try:
                repository = RegistryRepository(connection)
                record = register_data_snapshot(manifest, repository)
                loaded = repository.get_data_snapshot(record.dataSnapshotId)
            finally:
                connection.close()

        self.assertEqual(loaded, record)

    def test_manifest_metadata_tampering_fails_verification(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data_file = root / "a.csv"
            data_file.write_text("timestamp,close\n1,10\n", encoding="utf-8")
            manifest = self._build_manifest(root, data_file)
            tampered = deepcopy(manifest)
            tampered["timeframe"] = "4h"

            verification = verify_data_snapshot(tampered, root=root)

        self.assertFalse(verification["valid"])
        self.assertIn("manifest_hash_mismatch", verification["errors"])

    def test_manifest_path_cannot_escape_declared_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data_root = root / "data"
            data_root.mkdir()
            outside = root / "outside.csv"
            outside.write_text("timestamp,close\n1,10\n", encoding="utf-8")
            manifest = self._build_manifest(root, outside)
            escaped = deepcopy(manifest)
            escaped["files"][0]["path"] = "../outside.csv"

            verification = verify_data_snapshot(escaped, root=data_root)

        self.assertFalse(verification["valid"])
        self.assertIn("outside_root:../outside.csv", verification["errors"])


if __name__ == "__main__":
    unittest.main()
