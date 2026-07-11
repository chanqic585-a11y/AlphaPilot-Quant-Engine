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
        exit_code, payload = self.run_cli_raw(*args)
        self.assertEqual(exit_code, 0)
        return payload

    def run_cli_raw(self, *args: str) -> tuple[int, dict]:
        output = io.StringIO()
        try:
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
        except SystemExit as error:
            self.fail(f"workflow CLI command is unavailable: {error}")
        return exit_code, json.loads(output.getvalue())

    def test_bootstrap_and_projection_are_idempotent(self) -> None:
        first = self.run_cli("bootstrap")
        second = self.run_cli("bootstrap")
        projection = self.run_cli("projection")

        self.assertEqual(first["strategyVersionId"], second["strategyVersionId"])
        self.assertEqual(projection["summary"]["strategyCount"], 1)
        self.assertEqual(projection["items"][0]["status"], "awaiting")

    def test_projection_exposes_immutable_optimization_context(self) -> None:
        self.run_cli("bootstrap")

        item = self.run_cli("projection")["items"][0]

        context = item["optimizationContext"]
        self.assertEqual(context["sourceKind"], "workflow_version")
        self.assertEqual(context["definition"]["timeframe"], "4h")
        self.assertEqual(context["parameters"]["targetRMultiple"], 2.0)
        self.assertEqual(
            context["parentStrategyVersionId"], item["strategyVersionId"]
        )

    def test_import_optimized_legacy_strategy_creates_backtest_version(self) -> None:
        imported = self.run_cli(
            "import-optimized",
            "--legacy-strategy-id",
            "legacy-short-1",
            "--display-name",
            "空头上影拒绝 优化版",
            "--definition-json",
            json.dumps(
                {
                    "schemaVersion": "strategy_workflow_definition_v1",
                    "family": "short_rejection",
                    "direction": "short",
                    "timeframe": "1h",
                    "targetR": 2.0,
                }
            ),
            "--base-parameters-json",
            json.dumps({"volume_min": 1.2, "targetRMultiple": 2.0}),
            "--parameters-json",
            json.dumps({"volume_min": 1.3, "targetRMultiple": 2.0}),
        )
        projection = self.run_cli("projection")

        self.assertIsNone(imported["strategyCandidateId"])
        self.assertEqual(
            imported["definition"]["optimizationLineage"]["legacyStrategyId"],
            "legacy-short-1",
        )
        self.assertEqual(imported["sourceType"], "legacy_stage_optimization")
        self.assertIsNone(imported["parentStrategyVersionId"])
        self.assertEqual(projection["items"][0]["stage"], "backtest")
        self.assertEqual(projection["items"][0]["status"], "awaiting")
        self.assertEqual(
            projection["items"][0]["optimizationContext"]["parameters"]["volume_min"],
            1.3,
        )

    def test_import_optimized_rejects_unchanged_parameters(self) -> None:
        parameters = {"volume_min": 1.2, "targetRMultiple": 2.0}
        exit_code, payload = self.run_cli_raw(
            "import-optimized",
            "--legacy-strategy-id",
            "legacy-short-1",
            "--display-name",
            "空头上影拒绝 优化版",
            "--definition-json",
            json.dumps({"timeframe": "1h", "targetR": 2.0}),
            "--base-parameters-json",
            json.dumps(parameters),
            "--parameters-json",
            json.dumps(parameters),
        )

        self.assertEqual(exit_code, 2)
        self.assertEqual(payload["error"], "optimized_parameters_unchanged")

    def test_import_optimized_rejects_target_below_two_r(self) -> None:
        exit_code, payload = self.run_cli_raw(
            "import-optimized",
            "--legacy-strategy-id",
            "legacy-short-1",
            "--display-name",
            "空头上影拒绝 优化版",
            "--definition-json",
            json.dumps({"timeframe": "1h", "targetR": 2.0}),
            "--base-parameters-json",
            json.dumps({"volume_min": 1.2, "targetRMultiple": 2.0}),
            "--parameters-json",
            json.dumps({"volume_min": 1.3, "targetRMultiple": 1.5}),
        )

        self.assertEqual(exit_code, 2)
        self.assertEqual(payload["error"], "minimum_target_r_is_2")

    def test_resolve_backtest_run_supports_unicode_strategy_name(self) -> None:
        self.run_cli("bootstrap")
        projection = self.run_cli("projection")

        resolved = self.run_cli(
            "resolve-backtest-run",
            "--strategy-name",
            "Alpha191 加密因子观察策略",
        )

        self.assertEqual(
            resolved,
            {"workflowRunId": projection["items"][0]["workflowRunId"]},
        )

    def test_powershell_wrapper_is_ascii_for_windows_powershell_compatibility(
        self,
    ) -> None:
        script = (
            Path(__file__).resolve().parents[2]
            / "scripts"
            / "run_v13_27_1_1_dual_backtest.ps1"
        )

        script.read_bytes().decode("ascii")

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

    def test_one_click_does_not_queue_when_another_worker_holds_the_lock(self) -> None:
        self.run_cli("bootstrap")
        run_id = self.run_cli("projection")["items"][0]["workflowRunId"]

        with patch(
            "alphapilot.evolution.workflow.cli.workflow_worker_lock"
        ) as lock, patch(
            "alphapilot.evolution.workflow.cli.run_dual_layer_backtest_workflow"
        ) as worker:
            lock.return_value.__enter__.return_value = False
            result = self.run_cli("one-click-backtest", "--run-id", run_id)

        worker.assert_not_called()
        self.assertEqual(result["status"], "awaiting")


if __name__ == "__main__":
    unittest.main()
