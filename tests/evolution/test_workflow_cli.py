from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

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

    def test_one_click_uses_approved_warehouse_and_dual_layer_worker(self) -> None:
        self.run_cli("bootstrap")
        projection = self.run_cli("projection")
        run_id = projection["items"][0]["workflowRunId"]
        captured = {}

        def fake_worker(workflow, registry, workflow_run_id, **kwargs):
            captured.update(kwargs)
            return workflow.get_workflow_run(workflow_run_id)

        with patch(
            "alphapilot.evolution.workflow.cli.run_dual_layer_backtest_workflow",
            side_effect=fake_worker,
        ):
            result = self.run_cli("one-click-backtest", "--run-id", run_id)

        self.assertEqual(result["status"], "queued")
        self.assertEqual(
            Path(captured["warehouse_root"]),
            Path(r"D:\Codex-Workspace\回测数据"),
        )
        self.assertEqual(Path(captured["output_root"]), self.output_root)


if __name__ == "__main__":
    unittest.main()
