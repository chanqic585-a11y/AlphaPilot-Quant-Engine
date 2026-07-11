from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from alphapilot.evolution.workflow.worker_lock import workflow_worker_lock


class WorkflowWorkerLockTests(unittest.TestCase):
    def test_only_one_worker_can_hold_the_same_run_lock(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output_root = Path(temp)

            with workflow_worker_lock(output_root, "run-1") as first:
                with workflow_worker_lock(output_root, "run-1") as second:
                    self.assertTrue(first)
                    self.assertFalse(second)

            with workflow_worker_lock(output_root, "run-1") as after_release:
                self.assertTrue(after_release)

    def test_different_runs_use_independent_locks(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output_root = Path(temp)

            with workflow_worker_lock(output_root, "run-1") as first:
                with workflow_worker_lock(output_root, "run-2") as second:
                    self.assertTrue(first)
                    self.assertTrue(second)


if __name__ == "__main__":
    unittest.main()
