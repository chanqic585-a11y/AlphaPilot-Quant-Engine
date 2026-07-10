from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from alphapilot.evolution.forward.runner import run_forward_cycle
from alphapilot.evolution.forward.types import ForwardRiskEnvelope
from alphapilot.evolution.registry.database import connect_registry
from alphapilot.evolution.registry.hashing import stable_hash
from alphapilot.evolution.registry.repositories import RegistryRepository
from alphapilot.evolution.registry.types import (
    DataSnapshotRecord,
    ForwardReleaseRecord,
    StrategyCandidateRecord,
    StrategyFamilyRecord,
)
from alphapilot.reports.generate_v13_19_local_forward_report import build_v13_19_report


INTERVAL = 4 * 60 * 60 * 1000
BASE = 1_783_641_600_000


class _SequencedMarket:
    def __init__(self, frames: list[pd.DataFrame]) -> None:
        self.frames = frames
        self.index = 0

    def completed_candles(
        self, _instrument_id: str, _timeframe: str, *, limit: int = 300
    ) -> pd.DataFrame:
        self.assert_limit(limit)
        frame = self.frames[min(self.index, len(self.frames) - 1)]
        self.index += 1
        return frame.copy()

    @staticmethod
    def assert_limit(limit: int) -> None:
        if limit != 300:
            raise AssertionError("runner must request the bounded factor window")


def _frame(count: int, *, final_high: float = 101.0) -> pd.DataFrame:
    timestamps = [BASE + index * INTERVAL for index in range(count)]
    return pd.DataFrame(
        {
            "timestamp_ms": timestamps,
            "open": [100.0] * count,
            "high": [101.0] * (count - 1) + [final_high],
            "low": [99.0] * (count - 1) + [99.0],
            "close": [100.0] * count,
            "volume": [1000.0] * count,
        }
    )


class LocalForwardRunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.registry_path = Path(self.directory.name) / "registry.sqlite"
        self.connection = connect_registry(self.registry_path)
        self.repository = RegistryRepository(self.connection)
        snapshot = DataSnapshotRecord(
            dataSnapshotId="snapshot_forward",
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
        family = StrategyFamilyRecord(
            strategyFamilyId="family_forward",
            familyKey="forward",
            name="Forward",
            status="research_only",
            metadata={},
            contentHash="family-hash",
        )
        candidate = StrategyCandidateRecord(
            strategyCandidateId="candidate_forward",
            strategyFamilyId=family.strategyFamilyId,
            name="Forward Candidate",
            status="shadow_candidate",
            candidate={},
            contentHash="candidate-hash",
        )
        release_payload = {
            "trainingDataSnapshotId": snapshot.dataSnapshotId,
            "marketDefinition": {
                "timeframe": "4h",
                "eligibleInstruments": ["BTC-USDT-SWAP"],
            },
            "signalPolicy": {
                "direction": "long",
                "rules": [{"factorId": "rsi_14", "operator": "gte", "threshold": 0}],
            },
            "createsOrders": False,
        }
        self.release = ForwardReleaseRecord(
            forwardReleaseId="release_forward",
            strategyCandidateId=candidate.strategyCandidateId,
            status="forward_eligible",
            riskEnvelope=ForwardRiskEnvelope(feeRate=0, slippageRate=0).to_dict(),
            release=release_payload,
            contentHash=stable_hash(release_payload),
        )
        self.repository.create_data_snapshot(snapshot)
        self.repository.create_strategy_family(family)
        self.repository.create_strategy_candidate(candidate)
        self.repository.create_forward_release(self.release)

    def tearDown(self) -> None:
        self.connection.close()
        self.directory.cleanup()

    def test_runner_restores_checkpoint_and_persists_forward_outcome(self) -> None:
        market = _SequencedMarket([_frame(60), _frame(61, final_high=105.0)])
        first = run_forward_cycle(
            self.release,
            repository=self.repository,
            market_data=market,
            code_commit="test-commit",
        )
        second = run_forward_cycle(
            self.release,
            repository=self.repository,
            market_data=market,
            code_commit="test-commit",
        )

        self.assertEqual(first.closedOutcomeCount, 0)
        self.assertEqual(second.closedOutcomeCount, 1)
        self.assertEqual(len(second.state["openPositions"]), 0)
        outcomes = self.repository.list_outcomes(
            source_entity_type="local_forward_session",
            source_entity_id=second.forwardSessionId,
        )
        self.assertEqual(len(outcomes), 1)
        self.assertEqual(outcomes[0].evidenceClass, "realtime_local_forward")
        self.assertFalse(outcomes[0].outcome["createsOrder"])
        self.assertGreaterEqual(self.repository.count("ForwardEvents"), 2)

    def test_report_fails_closed_without_forward_release(self) -> None:
        empty_registry = Path(self.directory.name) / "empty.sqlite"
        report, contract = build_v13_19_report(
            registry_path=empty_registry,
            code_commit="test-commit",
            observe=True,
        )

        self.assertEqual(report["status"], "blocked_no_eligible_forward_release")
        self.assertEqual(report["closedForwardOutcomeCount"], 0)
        self.assertFalse(contract["executionEnabled"])
        self.assertFalse(contract["createsOrders"])


if __name__ == "__main__":
    unittest.main()
