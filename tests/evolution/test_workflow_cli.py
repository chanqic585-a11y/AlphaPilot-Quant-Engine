from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from alphapilot.evolution.workflow.cli import main


class WorkflowCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.registry = self.root / "registry.sqlite"
        self.output_root = self.root / "workflow"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def run_cli(self, *args: str) -> dict:
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = main(
                [
                    "--registry",
                    str(self.registry),
                    "--output-root",
                    str(self.output_root),
                    *args,
                ]
            )
        self.assertEqual(exit_code, 0)
        return json.loads(output.getvalue())

    def test_bootstrap_and_projection_are_idempotent(self) -> None:
        first = self.run_cli("bootstrap")
        second = self.run_cli("bootstrap")
        projection = self.run_cli("projection")

        self.assertEqual(first["strategyVersionId"], second["strategyVersionId"])
        self.assertEqual(projection["summary"]["strategyCount"], 1)
        self.assertEqual(projection["items"][0]["status"], "awaiting")

    def test_queue_then_run_records_precise_alpha191_data_blocker(self) -> None:
        bootstrapped = self.run_cli("bootstrap")
        projection = self.run_cli("projection")
        run_id = projection["items"][0]["workflowRunId"]

        queued = self.run_cli("queue", "--run-id", run_id)
        blocked = self.run_cli("run", "--run-id", run_id)
        refreshed = self.run_cli("projection")

        self.assertEqual(queued["status"], "queued")
        self.assertEqual(blocked["status"], "blocked")
        self.assertEqual(
            refreshed["items"][0]["strategyVersionId"],
            bootstrapped["strategyVersionId"],
        )
        failure = refreshed["items"][0]["failure"]
        self.assertEqual(failure["category"], "data_integrity")
        self.assertIn("data_snapshot_id_missing", failure["summary"])


if __name__ == "__main__":
    unittest.main()
