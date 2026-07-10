from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from alphapilot.evolution.adapters.legacy_factor_adapter import adapt_legacy_factor_library
from alphapilot.evolution.registry.database import connect_registry
from alphapilot.evolution.registry.repositories import RegistryRepository


class LegacyFactorAdapterTests(unittest.TestCase):
    def test_factor_definitions_are_preserved_registered_and_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manual_path = root / "manual.json"
            evaluation_path = root / "evaluation.json"
            manual_path.write_text(
                json.dumps(
                    {
                        "reportId": "manual",
                        "version": "V-test",
                        "factorCount": 3,
                        "factorDefinitions": [
                            {
                                "factorId": "supported",
                                "name": "Supported",
                                "formula": "ts_mean(close, 20)",
                                "requiredFields": ["close"],
                                "researchOnly": True,
                            },
                            {
                                "factorId": "unsupported_ema",
                                "name": "Unsupported EMA",
                                "formula": "ts_ema(close, 20)",
                                "requiredFields": ["close"],
                                "researchOnly": True,
                            },
                            {
                                "factorId": "missing_field",
                                "name": "Missing Field",
                                "formula": "rolling_mean(hidden_future, 20)",
                                "requiredFields": ["close"],
                                "researchOnly": True,
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )
            evaluation_path.write_text(
                json.dumps(
                    {
                        "reportId": "evaluation",
                        "candidateFactors": [],
                        "factorReports": [
                            {
                                "factorId": "supported",
                                "candidateStatus": {"researchCandidate": False},
                                "primaryHorizonMetrics": {"meanRankIC": 0.01, "profitFactor": 1.01},
                                "stability": {
                                    "stableAcrossPairs": False,
                                    "byPair": [{"group": "BTC", "topBottomSpread": 0.01}],
                                },
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            connection = connect_registry(root / "registry.sqlite")
            try:
                repository = RegistryRepository(connection)
                first = adapt_legacy_factor_library(
                    manual_report_path=manual_path,
                    evaluation_report_path=evaluation_path,
                    repository=repository,
                )
                second = adapt_legacy_factor_library(
                    manual_report_path=manual_path,
                    evaluation_report_path=evaluation_path,
                    repository=repository,
                )
                registered_count = repository.count("FactorDefinitions")
                candidate_count = repository.count("StrategyCandidates")
            finally:
                connection.close()

        self.assertEqual(first["factorCount"], 3)
        self.assertEqual(first["dslSupportedCount"], 1)
        self.assertEqual(first["dslBlockedCount"], 2)
        self.assertEqual(first["formalResearchReadyCount"], 0)
        self.assertFalse(first["valueMutationPerformed"])
        self.assertEqual(first["factors"][0]["sourceFormula"], "ts_mean(close, 20)")
        self.assertEqual(first["factors"][0]["canonicalExpression"], "rolling_mean(close,20)")
        self.assertNotIn("byPair", first["factors"][0]["existingEvaluation"]["stability"])
        self.assertEqual(second["newFactorDefinitionCount"], 0)
        self.assertEqual(registered_count, 3)
        self.assertEqual(candidate_count, 0)


if __name__ == "__main__":
    unittest.main()
