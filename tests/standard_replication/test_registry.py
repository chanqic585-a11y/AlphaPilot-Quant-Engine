from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from alphapilot.standard_replication.registry import (
    ReplicationRegistryError,
    ReplicationSourceRegistry,
)


class ReplicationSourceRegistryTests(unittest.TestCase):
    def test_repository_registry_contains_six_bounded_families(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]

        registry = ReplicationSourceRegistry.load(
            repo_root
            / "research"
            / "source_registry"
            / "strategy_research_source_registry.json"
        )

        self.assertEqual(
            registry.family_ids,
            (
                "chan_structure_parser_v1",
                "crypto_conditional_mean_reversion_v1",
                "crypto_cross_sectional_factor_v1",
                "crypto_event_driven_v1",
                "crypto_pair_relative_value_v1",
                "crypto_tsmom_turtle_v1",
            ),
        )
        self.assertTrue(all(1 <= len(item.variants) <= 2 for item in registry.items))
        self.assertTrue(all(item.source.url for item in registry.items))
        self.assertTrue(all(item.source.license for item in registry.items))
        self.assertTrue(all(item.source.summary for item in registry.items))
        self.assertTrue(all(item.source.citation for item in registry.items))

    def test_registry_rejects_more_than_two_variants_per_family(self) -> None:
        payload = {
            "schemaVersion": "v35_strategy_research_source_registry_v1",
            "registryId": "test",
            "families": [
                {
                    "familyId": "too_many",
                    "title": "Too many",
                    "source": {
                        "url": "https://example.com/source",
                        "license": "citation_only",
                        "summary": "A bounded test source.",
                        "citation": "Example source.",
                    },
                    "mechanism": "test",
                    "formula": "test",
                    "parameters": {},
                    "universe": {},
                    "costAssumptions": {},
                    "adaptationLimits": [],
                    "replicationState": "registered",
                    "variants": [
                        {"candidateId": "a", "adaptation": "source_replication"},
                        {"candidateId": "b", "adaptation": "crypto_adaptation"},
                        {"candidateId": "c", "adaptation": "extra"},
                    ],
                }
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "registry.json"
            path.write_text(json.dumps(payload), encoding="utf-8")

            with self.assertRaisesRegex(
                ReplicationRegistryError,
                "variant_budget_exceeded:too_many",
            ):
                ReplicationSourceRegistry.load(path)

    def test_registry_rejects_incomplete_source_metadata(self) -> None:
        payload = {
            "schemaVersion": "v35_strategy_research_source_registry_v1",
            "registryId": "test",
            "families": [
                {
                    "familyId": "missing_license",
                    "title": "Missing license",
                    "source": {
                        "url": "https://example.com/source",
                        "license": "",
                        "summary": "A test source.",
                        "citation": "Example source.",
                    },
                    "mechanism": "test",
                    "formula": "test",
                    "parameters": {},
                    "universe": {},
                    "costAssumptions": {},
                    "adaptationLimits": [],
                    "replicationState": "registered",
                    "variants": [
                        {"candidateId": "a", "adaptation": "source_replication"}
                    ],
                }
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "registry.json"
            path.write_text(json.dumps(payload), encoding="utf-8")

            with self.assertRaisesRegex(
                ReplicationRegistryError,
                "source_metadata_incomplete:missing_license",
            ):
                ReplicationSourceRegistry.load(path)


if __name__ == "__main__":
    unittest.main()
