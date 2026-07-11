from __future__ import annotations

import inspect
import tempfile
import threading
import unittest
from pathlib import Path

from alphapilot.evolution.workflow.worker_lock import workflow_worker_lock


class WorkflowWorkerLockTests(unittest.TestCase):
    def test_waits_for_existing_worker_to_release_the_run_lock(self) -> None:
        self.assertIn(
            "wait_seconds",
            inspect.signature(workflow_worker_lock).parameters,
        )
        with tempfile.TemporaryDirectory() as temp:
            output_root = Path(temp)
            acquired_by_holder = threading.Event()
            release_holder = threading.Event()

            def hold_lock() -> None:
                with workflow_worker_lock(output_root, "run-1") as acquired:
                    self.assertTrue(acquired)
                    acquired_by_holder.set()
                    release_holder.wait(timeout=2)

            holder = threading.Thread(target=hold_lock)
            holder.start()
            self.assertTrue(acquired_by_holder.wait(timeout=1))
            threading.Timer(0.1, release_holder.set).start()

            with workflow_worker_lock(
                output_root,
                "run-1",
                wait_seconds=1.0,
                poll_seconds=0.01,
            ) as acquired_after_wait:
                self.assertTrue(acquired_after_wait)

            holder.join(timeout=1)
            self.assertFalse(holder.is_alive())

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
