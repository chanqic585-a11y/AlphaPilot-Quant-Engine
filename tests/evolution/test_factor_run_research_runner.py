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
from alphapilot.evolution.factor_runs.research_runner import run_factor_research
from alphapilot.evolution.registry.database import connect_registry
from alphapilot.evolution.registry.repositories import RegistryRepository


class FactorRunResearchRunnerTests(unittest.TestCase):
    def test_registered_smoke_research_keeps_provenance_blocker_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            canonical_root = root / "canonical"
            files: list[Path] = []
            timestamps = np.arange(600, dtype="int64") * 4 * 60 * 60 * 1000
            for index, instrument in enumerate(
                ("BTC-USDT-SWAP", "ETH-USDT-SWAP", "SOL-USDT-SWAP")
            ):
                path = canonical_root / f"unknown/swap/ohlcv/{instrument}/4h/part.parquet"
                path.parent.mkdir(parents=True)
                sequence = np.arange(len(timestamps), dtype="float64")
                close = 100 + 8 * np.sin(sequence / 8 + index) + 2 * np.sin(sequence / 2.7)
                frame = pd.DataFrame(
                    {
                        "timestamp_ms": timestamps,
                        "date": pd.to_datetime(timestamps, unit="ms", utc=True),
                        "open": close + 0.2 * np.sin(sequence / 3),
                        "high": close + 2.0,
                        "low": close - 2.0,
                        "close": close,
                        "volume": 1_000 + 200 * np.cos(sequence / 5 + index),
                    }
                )
                frame.to_parquet(path, index=False)
                files.append(path)
            manifest = build_data_snapshot_manifest(
                files=files,
                root=canonical_root,
                source="test_mixed",
                exchange="mixed",
                market_type="swap",
                timeframe="4h",
                start_time=pd.Timestamp(timestamps[0], unit="ms", tz="UTC").isoformat(),
                end_time=pd.Timestamp(timestamps[-1], unit="ms", tz="UTC").isoformat(),
                point_in_time_cutoff=pd.Timestamp(
                    timestamps[-1], unit="ms", tz="UTC"
                ).isoformat(),
                universe_members=["BTC-USDT-SWAP", "ETH-USDT-SWAP", "SOL-USDT-SWAP"],
                metadata={
                    "formalPromotionEligible": False,
                    "provenanceStatus": "test_unknown",
                },
            )
            connection = connect_registry(root / "registry.sqlite")
            try:
                repository = RegistryRepository(connection)
                snapshot = register_data_snapshot(manifest, repository)
                labels = DirectionalLabelConfig(maxHoldingBars=6)
                matrix = materialize_factor_matrix(
                    snapshot=snapshot,
                    repository=repository,
                    canonical_root=canonical_root,
                    output_root=root / "factor_runs",
                    label_config=labels,
                    code_commit="test",
                )
                panel = pd.read_parquet(matrix.path)
                self.assertEqual(set(panel["label_long_target_hit"].unique()), {0, 1})
                self.assertEqual(set(panel["label_short_target_hit"].unique()), {0, 1})
                first = run_factor_research(
                    matrix=matrix,
                    repository=repository,
                    label_config=labels,
                    code_commit="test",
                )
                second = run_factor_research(
                    matrix=matrix,
                    repository=repository,
                    label_config=labels,
                    code_commit="test",
                )
                self.assertEqual(first["status"], "completed_with_provenance_blocker")
                self.assertFalse(first["formalPromotionEligible"])
                self.assertEqual(first["strategyCandidates"], [])
                self.assertEqual(len(first["experiments"]), 2)
                self.assertEqual(len(first["models"]), 2)
                self.assertEqual(repository.count("Experiments"), 2)
                self.assertEqual(repository.count("Models"), 2)
                self.assertEqual(repository.count("StrategyCandidates"), 0)
                self.assertEqual(
                    [row["experimentId"] for row in first["experiments"]],
                    [row["experimentId"] for row in second["experiments"]],
                )
            finally:
                connection.close()


if __name__ == "__main__":
    unittest.main()
