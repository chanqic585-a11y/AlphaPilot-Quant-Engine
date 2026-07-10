from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from alphapilot.evolution.registry.database import connect_registry
from alphapilot.evolution.registry.repositories import RegistryRepository
from alphapilot.evolution.registry.types import DataSnapshotRecord
from alphapilot.evolution.replay import (
    ReplayConfig,
    ReplayResult,
    ReplaySignal,
    run_historical_replay,
)
from alphapilot.evolution.replay.ledger import persist_replay_outcomes


class ReplayOutcomeLedgerTests(unittest.TestCase):
    def test_empty_replay_writes_a_stable_empty_artifact(self) -> None:
        result = ReplayResult(ReplayConfig(), (), ())
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            connection = connect_registry(root / "registry.sqlite")
            try:
                manifest = persist_replay_outcomes(
                    result,
                    repository=RegistryRepository(connection),
                    data_snapshot_id="data_snapshot_empty",
                    source_entity_type="engine_probe",
                    source_entity_id="empty_probe",
                    evidence_class="historical_path_replay_probe",
                    code_commit="test",
                    output_root=root / "replay",
                )
                artifact = pd.read_parquet(manifest["artifactPath"])
                self.assertEqual(manifest["outcomeCount"], 0)
                self.assertEqual(list(artifact.columns)[0], "outcomeId")
                self.assertTrue(artifact.empty)
            finally:
                connection.close()

    def test_replay_outcomes_are_hashed_and_idempotent(self) -> None:
        frame = pd.DataFrame(
            {
                "timestamp_ms": [0, 1, 2, 3],
                "open": [90.0, 100.0, 100.0, 100.0],
                "high": [91.0, 103.0, 101.0, 101.0],
                "low": [89.0, 99.5, 99.5, 99.5],
                "close": [90.0, 100.5, 100.5, 100.5],
            }
        )
        result = run_historical_replay(
            [
                ReplaySignal(
                    signalId="signal_1",
                    instrumentId="BTC-USDT-SWAP",
                    timeframe="4h",
                    direction="long",
                    decisionTimestampMs=0,
                    riskDistance=1.0,
                    sourceEntityId="probe_v1",
                )
            ],
            bars_by_instrument={"BTC-USDT-SWAP": frame},
            config=ReplayConfig(maxHoldingBars=2, feeRate=0, slippageRate=0),
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            connection = connect_registry(root / "registry.sqlite")
            try:
                repository = RegistryRepository(connection)
                repository.create_data_snapshot(
                    DataSnapshotRecord(
                        dataSnapshotId="data_snapshot_replay",
                        source="test",
                        exchange="okx",
                        marketType="swap",
                        timeframe="4h",
                        startTime=None,
                        endTime=None,
                        pointInTimeCutoff=None,
                        manifest={"files": []},
                        contentHash="snapshot-hash",
                    )
                )
                first = persist_replay_outcomes(
                    result,
                    repository=repository,
                    data_snapshot_id="data_snapshot_replay",
                    source_entity_type="engine_probe",
                    source_entity_id="probe_v1",
                    evidence_class="historical_path_replay_probe",
                    code_commit="test",
                    output_root=root / "replay",
                )
                second = persist_replay_outcomes(
                    result,
                    repository=repository,
                    data_snapshot_id="data_snapshot_replay",
                    source_entity_type="engine_probe",
                    source_entity_id="probe_v1",
                    evidence_class="historical_path_replay_probe",
                    code_commit="test",
                    output_root=root / "replay",
                )
                self.assertEqual(first["artifactSha256"], second["artifactSha256"])
                self.assertEqual(first["outcomeIds"], second["outcomeIds"])
                self.assertEqual(repository.count("OutcomeLedger"), 1)
                self.assertTrue(Path(first["artifactPath"]).is_file())
            finally:
                connection.close()


if __name__ == "__main__":
    unittest.main()
