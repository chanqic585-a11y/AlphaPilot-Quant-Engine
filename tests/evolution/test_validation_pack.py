from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from alphapilot.data_foundation.formal_snapshot import freeze_formal_snapshot
from alphapilot.data_foundation.warehouse import WarehouseLayout
from alphapilot.evolution.evaluation.validation_pack import (
    build_formal_validation_pack,
)
from alphapilot.evolution.registry.database import connect_registry
from alphapilot.evolution.registry.repositories import RegistryRepository
from tests.data_foundation.test_formal_snapshot import (
    make_collection,
    make_contract,
)


class FormalValidationPackTests(unittest.TestCase):
    def test_pack_is_deterministic_leakage_resistant_and_complete(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            layout = WarehouseLayout.from_root(root / "回测数据")
            layout.ensure_directories()
            connection = connect_registry(root / "registry.sqlite")
            try:
                contract = make_contract()
                snapshot = freeze_formal_snapshot(
                    make_collection(layout), contract, layout, RegistryRepository(connection)
                )

                first = build_formal_validation_pack(
                    contract,
                    snapshot,
                    canonical_root=layout.canonicalRoot,
                    manifest_root=layout.manifestRoot,
                )
                second = build_formal_validation_pack(
                    contract,
                    snapshot,
                    canonical_root=layout.canonicalRoot,
                    manifest_root=layout.manifestRoot,
                )
            finally:
                connection.close()

            self.assertEqual(first, second)
            self.assertTrue(first.walkForwardManifestHash.startswith("walk_forward_"))
            self.assertTrue(first.holdoutManifestHash.startswith("holdout_"))
            self.assertTrue(first.lockedOosManifestHash.startswith("locked_oos_"))
            self.assertTrue(first.regimeManifestHash.startswith("regime_"))
            self.assertTrue(first.costManifestHash.startswith("cost_"))
            self.assertTrue(all(Path(path).is_file() for path in first.manifestPaths))
            self.assertTrue(first.holdoutSymbols)
            self.assertTrue(first.trainingSymbols)
            self.assertTrue(set(first.holdoutSymbols).isdisjoint(first.trainingSymbols))
            self.assertGreaterEqual(first.walkForwardFoldCount, 3)
            self.assertGreater(first.lockedStartIndex, 0)


if __name__ == "__main__":
    unittest.main()
