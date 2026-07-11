from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import Mock, patch

from alphapilot.evolution.registry.database import connect_registry
from alphapilot.evolution.registry.repositories import RegistryRepository
from alphapilot.evolution.workflow.cli import _run_selected_forward_cycles, main
from alphapilot.evolution.workflow.types import WorkflowRunRecord


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

    def test_short_cycle_bootstrap_is_idempotent_and_awaiting_only(self) -> None:
        first = self.run_cli("bootstrap-short-cycle")
        second = self.run_cli("bootstrap-short-cycle")
        projection = self.run_cli("projection")
        items = [
            item
            for item in projection["items"]
            if item["sourceType"] == "short_cycle_candidate_pack_v13_27_3"
        ]

        self.assertEqual(first, second)
        self.assertEqual(first["count"], 10)
        self.assertEqual(len(first["strategyVersionIds"]), 10)
        self.assertEqual(len(items), 10)
        self.assertEqual(
            {(item["stage"], item["status"]) for item in items},
            {("backtest", "awaiting")},
        )

        connection = connect_registry(self.registry)
        try:
            repository = RegistryRepository(connection)
            self.assertEqual(repository.list_strategy_candidates(), [])
            self.assertEqual(repository.list_demo_releases(), [])
            self.assertEqual(repository.list_live_candidate_packages(), [])
            self.assertEqual(repository.list_live_releases(), [])
        finally:
            connection.close()

    def test_short_cycle_bootstrap_does_not_reset_an_existing_run(self) -> None:
        self.run_cli("bootstrap-short-cycle")
        item = next(
            item
            for item in self.run_cli("projection")["items"]
            if item["sourceType"] == "short_cycle_candidate_pack_v13_27_3"
        )

        queued = self.run_cli("queue", "--run-id", item["workflowRunId"])
        self.run_cli("bootstrap-short-cycle")
        refreshed = next(
            candidate
            for candidate in self.run_cli("projection")["items"]
            if candidate["strategyVersionId"] == item["strategyVersionId"]
        )

        self.assertEqual(queued["status"], "queued")
        self.assertEqual(refreshed["status"], "queued")

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

    def test_short_cycle_registration_wrapper_is_ascii_and_registration_only(
        self,
    ) -> None:
        script = (
            Path(__file__).resolve().parents[2]
            / "scripts"
            / "register_v13_27_3_short_cycle_candidates.ps1"
        )

        content = script.read_bytes().decode("ascii")
        self.assertIn("bootstrap-short-cycle", content)
        self.assertNotIn("run-all-awaiting", content)
        self.assertNotIn("one-click-backtest", content)

    def test_selected_backtests_run_in_requested_serial_order(self) -> None:
        self.run_cli("bootstrap-short-cycle")
        awaiting = [
            item
            for item in self.run_cli("projection")["items"]
            if item["sourceType"] == "short_cycle_candidate_pack_v13_27_3"
        ][:2]
        requested_ids = [item["workflowRunId"] for item in awaiting]
        observed: list[str] = []

        def fake_worker(workflow, _registry, workflow_run_id, **_kwargs):
            observed.append(workflow_run_id)
            return workflow.get_workflow_run(workflow_run_id)

        with patch(
            "alphapilot.evolution.workflow.cli._run_dual_layer_once",
            side_effect=fake_worker,
        ):
            result = self.run_cli(
                "run-selected-backtests",
                "--run-id",
                requested_ids[0],
                "--run-id",
                requested_ids[1],
            )

        self.assertEqual(observed, requested_ids)
        self.assertEqual(result["processedCount"], 2)
        self.assertEqual(result["workflowRunIds"], requested_ids)
        self.assertEqual(
            [run["status"] for run in result["runs"]], ["queued", "queued"]
        )

    def test_selected_backtests_reject_duplicates_and_ineligible_runs(self) -> None:
        self.run_cli("bootstrap-short-cycle")
        run_id = self.run_cli("projection")["items"][0]["workflowRunId"]

        duplicate_code, duplicate = self.run_cli_raw(
            "run-selected-backtests",
            "--run-id",
            run_id,
            "--run-id",
            run_id,
        )
        self.run_cli("queue", "--run-id", run_id)
        ineligible_code, ineligible = self.run_cli_raw(
            "run-selected-backtests", "--run-id", run_id
        )

        self.assertEqual(duplicate_code, 2)
        self.assertEqual(
            duplicate["error"], "selected_backtest_run_ids_must_be_unique"
        )
        self.assertEqual(ineligible_code, 2)
        self.assertIn("selected_backtest_run_not_eligible", ineligible["error"])

    def test_selected_forward_cycles_run_in_requested_serial_order(self) -> None:
        def local_run(run_id: str, *, status: str = "running") -> WorkflowRunRecord:
            return WorkflowRunRecord(
                workflowRunId=run_id,
                strategyVersionId=f"version-{run_id}",
                stage="local_forward",
                status=status,
                attemptNumber=1,
                gateProfileId=None,
                riskProfileId="risk-local",
                idempotencyKey=f"local::{run_id}",
                progress={},
                result={"forwardReleaseId": f"release-{run_id}"},
                startedAt="2026-07-12T00:00:00+00:00",
                checkpointAt=None,
                completedAt=None,
                contentHash=f"hash-{run_id}",
            )

        runs = {"run-2": local_run("run-2"), "run-1": local_run("run-1")}
        workflow = Mock()
        workflow.get_workflow_run.side_effect = runs.get
        observed: list[str] = []

        def fake_cycle(_workflow, _registry, workflow_run_id, **_kwargs):
            observed.append(workflow_run_id)
            return runs[workflow_run_id]

        with patch(
            "alphapilot.evolution.workflow.cli._run_local_forward_once",
            side_effect=fake_cycle,
        ):
            result = _run_selected_forward_cycles(
                workflow,
                Mock(),
                ["run-2", "run-1"],
                output_root=self.output_root,
            )

        self.assertEqual(observed, ["run-2", "run-1"])
        self.assertEqual(result["processedCount"], 2)
        self.assertEqual(result["workflowRunIds"], ["run-2", "run-1"])

    def test_selected_forward_cycles_reject_duplicates_and_ineligible_runs(self) -> None:
        workflow = Mock()
        workflow.get_workflow_run.return_value = WorkflowRunRecord(
            workflowRunId="run-1",
            strategyVersionId="version-1",
            stage="backtest",
            status="running",
            attemptNumber=1,
            gateProfileId=None,
            riskProfileId=None,
            idempotencyKey="backtest::run-1",
            progress={},
            result={},
            startedAt=None,
            checkpointAt=None,
            completedAt=None,
            contentHash="hash-run-1",
        )

        with self.assertRaisesRegex(Exception, "must_be_unique"):
            _run_selected_forward_cycles(
                workflow,
                Mock(),
                ["run-1", "run-1"],
                output_root=self.output_root,
            )
        with self.assertRaisesRegex(Exception, "not_eligible"):
            _run_selected_forward_cycles(
                workflow,
                Mock(),
                ["run-1"],
                output_root=self.output_root,
            )

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
