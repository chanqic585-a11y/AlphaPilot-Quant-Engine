from __future__ import annotations

import unittest

from alphapilot.evolution.workflow.local_forward_bridge import (
    LocalForwardRetiredError,
    project_legacy_local_forward,
    run_local_forward_cycle,
    start_local_forward_after_pass,
)


class _ExplodingDependency:
    def __getattr__(self, name: str) -> object:
        raise AssertionError(f"retired path touched dependency: {name}")


class WorkflowLocalForwardBridgeRetirementTests(unittest.TestCase):
    def test_legacy_record_is_projected_read_only_without_losing_evidence(self) -> None:
        historical = {
            "workflowRunId": "legacy-local-run",
            "stage": "local_forward",
            "status": "running",
            "result": {
                "closedOutcomeCount": 7,
                "forwardReleaseId": "legacy-release",
            },
        }

        projected = project_legacy_local_forward(historical)

        self.assertEqual(projected["workflowRunId"], "legacy-local-run")
        self.assertEqual(projected["stage"], "legacy_local_observation")
        self.assertEqual(projected["legacyStage"], "local_forward")
        self.assertEqual(projected["status"], "running")
        self.assertEqual(projected["result"], historical["result"])
        self.assertTrue(projected["readOnly"])
        self.assertTrue(projected["historicalDataPreserved"])

    def test_start_is_rejected_before_any_dependency_is_touched(self) -> None:
        dependency = _ExplodingDependency()

        with self.assertRaisesRegex(LocalForwardRetiredError, "local_forward_retired"):
            start_local_forward_after_pass(
                dependency,
                dependency,
                dependency,
                dependency,
                dependency,
                code_commit="retired",
                market_data=dependency,
            )

    def test_cycle_is_rejected_before_any_dependency_is_touched(self) -> None:
        dependency = _ExplodingDependency()

        with self.assertRaisesRegex(LocalForwardRetiredError, "local_forward_retired"):
            run_local_forward_cycle(
                dependency,
                dependency,
                "legacy-run",
                code_commit="retired",
                market_data=dependency,
            )


if __name__ == "__main__":
    unittest.main()
