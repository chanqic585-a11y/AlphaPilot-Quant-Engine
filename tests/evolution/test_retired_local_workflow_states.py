from __future__ import annotations

import unittest

from alphapilot.evolution.workflow.local_forward_bridge import (
    LocalForwardRetiredError,
    project_legacy_local_forward,
    run_local_forward_cycle,
    start_local_forward_after_pass,
)
from alphapilot.evolution.workflow.service import NEXT_STAGE
from alphapilot.evolution.workflow.states import (
    WorkflowTransitionError,
    validate_active_stage,
    validate_stage,
)


class RetiredLocalWorkflowStateTests(unittest.TestCase):
    def test_historical_local_forward_value_is_readable_but_not_active(self) -> None:
        validate_stage("local_forward")

        with self.assertRaisesRegex(
            WorkflowTransitionError,
            "retired_workflow_stage:local_forward",
        ):
            validate_active_stage("local_forward")

        projection = project_legacy_local_forward({
            "stage": "local_forward",
            "status": "running",
            "result": {"closedOutcomeCount": 7},
        })
        self.assertEqual(projection["stage"], "legacy_local_observation")
        self.assertTrue(projection["readOnly"])
        self.assertTrue(projection["historicalDataPreserved"])

    def test_new_workflow_skips_local_forward(self) -> None:
        self.assertEqual(NEXT_STAGE["backtest"], "demo")
        self.assertNotIn("local_forward", NEXT_STAGE.values())

    def test_local_forward_commands_fail_before_touching_dependencies(self) -> None:
        with self.assertRaises(LocalForwardRetiredError):
            start_local_forward_after_pass(None, None, None, None, None, "", None)  # type: ignore[arg-type]
        with self.assertRaises(LocalForwardRetiredError):
            run_local_forward_cycle(None, None, "legacy-run", code_commit="", market_data=None)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
