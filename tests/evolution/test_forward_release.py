from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from alphapilot.evolution.forward.release import create_forward_release
from alphapilot.evolution.registry.database import connect_registry
from alphapilot.evolution.registry.repositories import RegistryRepository
from alphapilot.evolution.registry.types import StrategyCandidateRecord, StrategyFamilyRecord


class ForwardReleaseTests(unittest.TestCase):
    def test_engine_probe_cannot_create_forward_release(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            connection = connect_registry(Path(directory) / "registry.sqlite")
            try:
                repository = RegistryRepository(connection)
                family = StrategyFamilyRecord(
                    strategyFamilyId="family",
                    familyKey="family",
                    name="Family",
                    status="research_only",
                    metadata={},
                    contentHash="family-hash",
                )
                candidate = StrategyCandidateRecord(
                    strategyCandidateId="candidate",
                    strategyFamilyId=family.strategyFamilyId,
                    name="Candidate",
                    status="shadow_candidate",
                    candidate={},
                    contentHash="candidate-hash",
                )
                repository.create_strategy_family(family)
                repository.create_strategy_candidate(candidate)
                with self.assertRaisesRegex(ValueError, "Engine probe"):
                    create_forward_release(
                        candidate,
                        replay_report={"engineProbeOnly": True},
                        repository=repository,
                        code_commit="test",
                    )
            finally:
                connection.close()


if __name__ == "__main__":
    unittest.main()
