from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from alphapilot.evolution.registry.database import connect_registry
from alphapilot.evolution.registry.hashing import stable_hash
from alphapilot.evolution.registry.repositories import RegistryRepository
from alphapilot.evolution.registry.types import DataSnapshotRecord
from alphapilot.reports.generate_v13_22_offline_evolution_report import build_v13_22_report
from tests.evolution.test_offline_evolution_loop import outcome_record


class V1322OfflineEvolutionReportTests(unittest.TestCase):
    def test_probe_only_registry_is_quarantined_and_cannot_generate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            connection = connect_registry(root / "registry.sqlite")
            try:
                repository = RegistryRepository(connection)
                repository.create_data_snapshot(
                    DataSnapshotRecord(
                        dataSnapshotId="snapshot_1",
                        source="unit_test",
                        exchange="okx",
                        marketType="swap",
                        timeframe="1h",
                        startTime=None,
                        endTime=None,
                        pointInTimeCutoff="2025-01-01T00:00:00+00:00",
                        manifest={"files": []},
                        contentHash=stable_hash({"snapshot": 1}),
                    )
                )
                repository.create_outcome(
                    outcome_record(
                        1,
                        evidence_class="historical_path_replay_probe",
                        source_entity_type="engine_probe",
                    )
                )
            finally:
                connection.close()

            report, triggers = build_v13_22_report(
                registry_path=root / "registry.sqlite",
                code_commit="test-commit",
            )

        self.assertEqual(report["status"], "blocked_no_formal_feedback_evidence")
        self.assertEqual(report["loop"]["evidenceIngestion"]["formalOutcomeCount"], 0)
        self.assertEqual(report["loop"]["evidenceIngestion"]["quarantinedCount"], 1)
        self.assertEqual(report["loop"]["boundedFactorGeneration"]["generatedCandidateCount"], 0)
        self.assertFalse(triggers["automaticPromotionAllowed"])
        self.assertFalse(triggers["createsOrders"])


if __name__ == "__main__":
    unittest.main()
