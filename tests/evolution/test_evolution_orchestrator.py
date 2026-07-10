from __future__ import annotations

import tempfile
import unittest
import json
from pathlib import Path

from alphapilot.evolution.orchestrator import EvolutionCycleConfig, run_evolution_cycle
from alphapilot.evolution.registry.database import connect_registry
from alphapilot.evolution.registry.hashing import stable_hash
from alphapilot.evolution.registry.repositories import RegistryRepository
from alphapilot.evolution.registry.types import FactorDefinitionRecord
from alphapilot.reports.generate_evolution_cycle_report import generate_evolution_cycle_report


def register_seed(
    repository: RegistryRepository,
    factor_id: str,
    expression: str,
    required_fields: list[str],
) -> None:
    definition = {
        "dslSupported": True,
        "canonicalExpression": expression,
        "sourceDefinition": {"requiredFields": required_fields},
        "seedEligible": True,
        "researchOnly": True,
    }
    repository.create_factor_definition(
        FactorDefinitionRecord(
            factorDefinitionId=factor_id,
            name=factor_id,
            version="v1",
            expression=expression,
            definition=definition,
            contentHash=stable_hash(definition),
        )
    )


class EvolutionOrchestratorTests(unittest.TestCase):
    def test_cycle_is_idempotent_shadow_only_and_does_not_invent_training_data(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            connection = connect_registry(Path(directory) / "registry.sqlite")
            try:
                repository = RegistryRepository(connection)
                register_seed(repository, "seed_mean", "rolling_mean(close,20)", ["close"])
                register_seed(repository, "seed_delta", "delta(close,3)", ["close"])
                config = EvolutionCycleConfig(
                    researchBudget=8,
                    maxCandidates=6,
                    allowedWindows=(3, 10, 20, 30),
                    fieldReplacements={"close": ("volume",)},
                    additionalFieldTypes={"volume": "number"},
                )
                first = run_evolution_cycle(repository=repository, config=config)
                second = run_evolution_cycle(repository=repository, config=config)
                model_count = repository.count("Models")
                strategy_count = repository.count("StrategyCandidates")
                demo_count = repository.count("DemoReleases")
            finally:
                connection.close()

        self.assertEqual(first["cycleId"], second["cycleId"])
        self.assertGreater(first["generatedCandidateCount"], 0)
        self.assertLessEqual(first["generatedCandidateCount"], 6)
        self.assertEqual(first["newRegisteredFactorDefinitionCount"], first["generatedCandidateCount"])
        self.assertEqual(second["newRegisteredFactorDefinitionCount"], 0)
        self.assertEqual(first["correlationFilterStatus"], "blocked_missing_factor_values")
        self.assertEqual(first["modelTrainingStatus"], "blocked_missing_registered_training_dataset")
        self.assertEqual(first["maximumLifecycleStage"], "shadow_research")
        self.assertFalse(first["safetyBoundary"]["createsDemoRelease"])
        self.assertFalse(first["safetyBoundary"]["createsOrders"])
        self.assertEqual(model_count, 0)
        self.assertEqual(strategy_count, 0)
        self.assertEqual(demo_count, 0)

    def test_cycle_report_bootstraps_legacy_factors_and_persists_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manual = root / "manual.json"
            evaluation = root / "evaluation.json"
            manual.write_text(
                json.dumps(
                    {
                        "version": "V-test",
                        "factorDefinitions": [
                            {
                                "factorId": "mean_close",
                                "name": "Mean close",
                                "formula": "rolling_mean(close, 20)",
                                "requiredFields": ["close"],
                            },
                            {
                                "factorId": "delta_close",
                                "name": "Delta close",
                                "formula": "delta(close, 3)",
                                "requiredFields": ["close"],
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )
            evaluation.write_text(
                json.dumps({"candidateFactors": [], "factorReports": []}), encoding="utf-8"
            )
            output_json = root / "cycle.json"
            output_markdown = root / "cycle.md"

            payload = generate_evolution_cycle_report(
                manual_report_path=manual,
                evaluation_report_path=evaluation,
                registry_path=root / "registry.sqlite",
                output_json=output_json,
                output_markdown=output_markdown,
                config=EvolutionCycleConfig(researchBudget=8, maxCandidates=6),
            )

            persisted = json.loads(output_json.read_text(encoding="utf-8"))
            markdown = output_markdown.read_text(encoding="utf-8")

        self.assertEqual(payload, persisted)
        self.assertEqual(payload["cycle"]["maximumLifecycleStage"], "shadow_research")
        self.assertFalse(payload["safetyBoundary"]["createsDemoRelease"])
        self.assertFalse(payload["safetyBoundary"]["createsOrders"])
        self.assertIn("Evolution and ML", markdown)


if __name__ == "__main__":
    unittest.main()
