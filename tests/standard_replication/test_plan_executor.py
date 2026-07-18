from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from alphapilot.standard_replication.plan_executor import ReplicationPlanExecutor
from alphapilot.standard_replication.registry import ReplicationSourceRegistry


class ReplicationPlanExecutorTests(unittest.TestCase):
    def test_executor_freezes_registered_and_data_blocked_families(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        registry = ReplicationSourceRegistry.load(
            repo_root
            / "research"
            / "source_registry"
            / "strategy_research_source_registry.json"
        )
        with tempfile.TemporaryDirectory() as directory:
            executor = ReplicationPlanExecutor(
                registry=registry,
                output_root=Path(directory),
            )
            candidate_ids = tuple(
                variant.candidate_id
                for family in registry.items
                for variant in family.variants
            )

            result = executor.execute(
                {
                    "campaignId": "v35-campaign-a",
                    "familyIds": list(registry.family_ids),
                    "candidateIds": list(candidate_ids),
                }
            )
            artifact_path = Path(str(result["artifactPath"]))
            payload = json.loads(artifact_path.read_text(encoding="utf-8"))

            self.assertEqual(result["status"], "ready_for_prefilter")
            self.assertEqual(result["candidateCount"], len(candidate_ids))
            self.assertEqual(result["blockedFamilyCount"], 2)
            self.assertEqual(payload["campaignId"], "v35-campaign-a")
            self.assertEqual(payload["formalRunCount"], 0)
            self.assertEqual(payload["lockedOosReadCount"], 0)
            self.assertEqual(payload["demoReleaseCount"], 0)
            self.assertFalse(payload["demoArm"])

    def test_executor_rejects_candidate_outside_registered_family_set(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        registry = ReplicationSourceRegistry.load(
            repo_root
            / "research"
            / "source_registry"
            / "strategy_research_source_registry.json"
        )
        with tempfile.TemporaryDirectory() as directory:
            executor = ReplicationPlanExecutor(
                registry=registry,
                output_root=Path(directory),
            )

            with self.assertRaisesRegex(
                ValueError,
                "candidate_not_registered_for_campaign",
            ):
                executor.execute(
                    {
                        "campaignId": "v35-campaign-a",
                        "familyIds": ["crypto_tsmom_turtle_v1"],
                        "candidateIds": ["not-registered"],
                    }
                )


if __name__ == "__main__":
    unittest.main()
