from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from alphapilot.evolution.data_lineage.snapshot_registry import (
    build_data_snapshot_manifest,
    register_data_snapshot,
)
from alphapilot.evolution.factor_runs.labels import DirectionalLabelConfig
from alphapilot.evolution.factor_runs.materializer import materialize_factor_matrix
from alphapilot.evolution.registry.database import connect_registry
from alphapilot.evolution.registry.repositories import RegistryRepository


class FactorRunMaterializerTests(unittest.TestCase):
    def test_materializes_and_registers_idempotent_point_in_time_runs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            canonical_root = root / "canonical"
            data_path = canonical_root / "okx/swap/ohlcv/BTC-USDT-SWAP/4h/part.parquet"
            data_path.parent.mkdir(parents=True)
            timestamps = np.arange(120, dtype="int64") * 4 * 60 * 60 * 1000
            close = np.linspace(100.0, 130.0, len(timestamps))
            frame = pd.DataFrame(
                {
                    "timestamp_ms": timestamps,
                    "date": pd.to_datetime(timestamps, unit="ms", utc=True),
                    "open": close - 0.1,
                    "high": close + 1.0,
                    "low": close - 1.0,
                    "close": close,
                    "volume": np.linspace(1_000.0, 2_000.0, len(timestamps)),
                }
            )
            frame.to_parquet(data_path, index=False)
            manifest = build_data_snapshot_manifest(
                files=[data_path],
                root=canonical_root,
                source="test",
                exchange="okx",
                market_type="swap",
                timeframe="4h",
                start_time=frame["date"].min().isoformat(),
                end_time=frame["date"].max().isoformat(),
                point_in_time_cutoff=frame["date"].max().isoformat(),
                universe_members=["BTC-USDT-SWAP"],
                metadata={"formalPromotionEligible": True, "provenanceStatus": "test"},
            )
            connection = connect_registry(root / "registry.sqlite")
            try:
                repository = RegistryRepository(connection)
                snapshot = register_data_snapshot(manifest, repository)
                first = materialize_factor_matrix(
                    snapshot=snapshot,
                    repository=repository,
                    canonical_root=canonical_root,
                    output_root=root / "factor_runs",
                    label_config=DirectionalLabelConfig(maxHoldingBars=3),
                    code_commit="test",
                )
                second = materialize_factor_matrix(
                    snapshot=snapshot,
                    repository=repository,
                    canonical_root=canonical_root,
                    output_root=root / "factor_runs",
                    label_config=DirectionalLabelConfig(maxHoldingBars=3),
                    code_commit="test",
                )
                self.assertGreater(first.rowCount, 0)
                self.assertEqual(first.sha256, second.sha256)
                self.assertEqual(first.factorRunIds, second.factorRunIds)
                self.assertEqual(repository.count("FactorRuns"), len(first.featureColumns))
                self.assertEqual(repository.count("FactorDefinitions"), len(first.featureColumns))
                self.assertTrue(first.pointInTimeValidated)
                self.assertTrue(first.formalPromotionEligible)
            finally:
                connection.close()


if __name__ == "__main__":
    unittest.main()
