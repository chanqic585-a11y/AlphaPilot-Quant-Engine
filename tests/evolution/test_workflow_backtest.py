from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from alphapilot.data_foundation.checkpoint import write_json_atomic
from alphapilot.data_foundation.warehouse import WarehouseLayout
from alphapilot.evolution.registry.database import connect_registry
from alphapilot.evolution.registry.hashing import stable_hash
from alphapilot.evolution.registry.repositories import RegistryRepository
from alphapilot.evolution.registry.types import (
    DataSnapshotRecord,
    StrategyFamilyRecord,
)
from alphapilot.evolution.workflow import (
    WorkflowRepository,
    build_workflow_projection,
    pause_workflow_run,
    queue_workflow_run,
    register_strategy_version,
    start_workflow_run,
)
from alphapilot.evolution.workflow.backtest import (
    BacktestAdapterError,
    BacktestAdapterResult,
    execute_registered_adapter,
    run_backtest_workflow,
)
from alphapilot.evolution.workflow.bootstrap import (
    ensure_default_backtest_gate_profile,
    register_alpha191_observer,
)
from alphapilot.evolution.workflow.data_contract import derive_strategy_data_contract
from alphapilot.evolution.workflow.states import WorkflowTransitionError


class WorkflowBacktestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.connection = connect_registry(self.root / "registry.sqlite")
        self.registry = RegistryRepository(self.connection)
        self.workflow = WorkflowRepository(self.connection)
        family_payload = {"scope": "workflow_backtest_test"}
        self.family = self.registry.create_strategy_family(
            StrategyFamilyRecord(
                strategyFamilyId="family_workflow_backtest",
                familyKey="workflow_backtest",
                name="Workflow Backtest",
                status="research_only",
                metadata=family_payload,
                contentHash=stable_hash(family_payload),
            )
        )
        self.gate = ensure_default_backtest_gate_profile(self.workflow)

    def tearDown(self) -> None:
        self.connection.close()
        self.temp.cleanup()

    def register_snapshot(self) -> DataSnapshotRecord:
        manifest = {
            "pointInTimeValidated": True,
            "formalResearchEligible": True,
            "sourceManifestSha256": "source_sha",
            "canonicalManifestSha256": "canonical_sha",
        }
        return self.registry.create_data_snapshot(
            DataSnapshotRecord(
                dataSnapshotId="snapshot_workflow_backtest",
                source="canonical_public_ohlcv",
                exchange="okx",
                marketType="swap",
                timeframe="4h",
                startTime="2024-01-01T00:00:00+00:00",
                endTime="2026-01-01T00:00:00+00:00",
                pointInTimeCutoff="2026-01-01T00:00:00+00:00",
                manifest=manifest,
                contentHash=stable_hash(manifest),
            )
        )

    def register_version(
        self,
        *,
        data_snapshot_id: str | None = "snapshot_workflow_backtest",
    ):
        definition = {
            "direction": "both",
            "timeframe": "4h",
            "targetR": 2.0,
            "backtest": {
                "adapterId": "test_adapter",
                "dataSnapshotId": data_snapshot_id,
                "walkForwardManifestHash": "walk_forward_test_hash",
                "lockedOosManifestHash": "locked_oos_test_hash",
                "costModel": {"feeRate": 0.0005, "slippageRate": 0.0002},
            },
        }
        return register_strategy_version(
            self.workflow,
            strategy_family_id=self.family.strategyFamilyId,
            display_name="工作流回测测试策略",
            source_type="test_fixture",
            definition=definition,
            parameters={"threshold": 1.0},
            initial_gate_profile_id=self.gate.gateProfileId,
        )

    def queue_initial(self, version_id: str):
        run = self.workflow.get_latest_workflow_run(version_id)
        self.assertIsNotNone(run)
        return queue_workflow_run(self.workflow, run.workflowRunId, actor="user")

    def test_real_worker_persists_manifest_checkpoints_and_passed_evidence(self) -> None:
        snapshot = self.register_snapshot()
        version = self.register_version(data_snapshot_id=snapshot.dataSnapshotId)
        queued = self.queue_initial(version.strategyVersionId)
        calls: list[dict] = []

        def execute(context, checkpoint):
            calls.append(context)
            checkpoint({"phase": "adapter_running", "completedUnits": 1, "totalUnits": 2})
            return BacktestAdapterResult(
                metrics={
                    "tradeCount": 120,
                    "profitFactor": 1.4,
                    "averageNetR": 0.18,
                    "maximumDrawdownR": 8.0,
                },
                checks={
                    "minimumTradeCount": True,
                    "minimumProfitFactor": True,
                    "positiveAverageNetR": True,
                    "maximumDrawdown": True,
                    "costStress": True,
                    "stability": True,
                    "lockedOos": True,
                },
                evidence={"reportSha256": "report_sha", "artifactPath": "report.json"},
            )

        completed = run_backtest_workflow(
            self.workflow,
            self.registry,
            queued.workflowRunId,
            output_root=self.root / "workflow",
            adapter_executor=execute,
        )

        self.assertEqual(completed.status, "passed")
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["dataSnapshotId"], snapshot.dataSnapshotId)
        self.assertTrue((self.root / "workflow" / queued.workflowRunId / "manifest.json").is_file())
        self.assertTrue((self.root / "workflow" / queued.workflowRunId / "result.json").is_file())
        self.assertEqual(completed.result["metrics"]["tradeCount"], 120)
        self.assertEqual(completed.result["evidence"]["reportSha256"], "report_sha")
        events = self.workflow.list_stage_events(workflow_run_id=queued.workflowRunId)
        self.assertTrue(any(event.reasonCode == "checkpoint_saved" for event in events))

    def test_new_contract_bound_run_requires_evaluation_binding(self) -> None:
        version = register_alpha191_observer(self.registry, self.workflow)
        derive_strategy_data_contract(version, self.workflow)
        queued = self.queue_initial(version.strategyVersionId)
        called = False

        def execute(context, checkpoint):
            nonlocal called
            called = True
            raise AssertionError("adapter must not run without an evaluation binding")

        completed = run_backtest_workflow(
            self.workflow,
            self.registry,
            queued.workflowRunId,
            output_root=self.root / "binding-required",
            adapter_executor=execute,
        )

        self.assertEqual(completed.status, "blocked")
        self.assertIn(
            "evaluation_binding_missing",
            completed.result["prerequisiteErrors"],
        )
        self.assertFalse(called)

    def test_worker_blocks_missing_registered_snapshot_before_adapter_execution(self) -> None:
        version = self.register_version(data_snapshot_id="missing_snapshot")
        queued = self.queue_initial(version.strategyVersionId)
        called = False

        def execute(context, checkpoint):
            nonlocal called
            called = True
            raise AssertionError("adapter must not run without registered data")

        blocked = run_backtest_workflow(
            self.workflow,
            self.registry,
            queued.workflowRunId,
            output_root=self.root / "workflow",
            adapter_executor=execute,
        )

        self.assertFalse(called)
        self.assertEqual(blocked.status, "blocked")
        diagnosis = self.workflow.get_latest_failure_diagnosis(blocked.workflowRunId)
        self.assertEqual(diagnosis.category, "data_integrity")
        self.assertEqual(diagnosis.retryDisposition, "manual_review")
        self.assertIn("missing_snapshot", diagnosis.summary)

    def test_failed_gate_requires_new_strategy_version(self) -> None:
        self.register_snapshot()
        version = self.register_version()
        queued = self.queue_initial(version.strategyVersionId)

        def execute(context, checkpoint):
            return BacktestAdapterResult(
                metrics={
                    "tradeCount": 80,
                    "profitFactor": 0.82,
                    "averageNetR": -0.1,
                    "maximumDrawdownR": 25.0,
                },
                checks={
                    "minimumTradeCount": True,
                    "minimumProfitFactor": False,
                    "positiveAverageNetR": False,
                    "maximumDrawdown": False,
                    "costStress": False,
                    "stability": False,
                    "lockedOos": True,
                },
                evidence={"reportSha256": "failed_report_sha"},
            )

        failed = run_backtest_workflow(
            self.workflow,
            self.registry,
            queued.workflowRunId,
            output_root=self.root / "workflow",
            adapter_executor=execute,
        )

        self.assertEqual(failed.status, "failed")
        diagnosis = self.workflow.get_latest_failure_diagnosis(failed.workflowRunId)
        self.assertEqual(diagnosis.category, "strategy_performance")
        self.assertEqual(diagnosis.retryDisposition, "new_version_required")
        self.assertIn("minimumProfitFactor", diagnosis.metrics["failedChecks"])

    def test_worker_recalculates_gate_metrics_instead_of_trusting_adapter(self) -> None:
        self.register_snapshot()
        version = self.register_version()
        queued = self.queue_initial(version.strategyVersionId)

        def execute(context, checkpoint):
            return BacktestAdapterResult(
                metrics={
                    "tradeCount": 120,
                    "profitFactor": 0.4,
                    "averageNetR": 0.2,
                    "maximumDrawdownR": 5.0,
                },
                checks={
                    "minimumTradeCount": True,
                    "minimumProfitFactor": True,
                    "positiveAverageNetR": True,
                    "maximumDrawdown": True,
                    "costStress": True,
                    "stability": True,
                    "lockedOos": True,
                },
                evidence={"reportSha256": "misleading_adapter_report"},
            )

        failed = run_backtest_workflow(
            self.workflow,
            self.registry,
            queued.workflowRunId,
            output_root=self.root / "workflow",
            adapter_executor=execute,
        )

        self.assertEqual(failed.status, "failed")
        self.assertFalse(failed.result["checks"]["minimumProfitFactor"])

    def test_paused_result_resumes_from_persisted_artifact_without_rerun(self) -> None:
        self.register_snapshot()
        version = self.register_version()
        queued = self.queue_initial(version.strategyVersionId)
        call_count = 0

        def execute(context, checkpoint):
            nonlocal call_count
            call_count += 1
            pause_workflow_run(
                self.workflow, queued.workflowRunId, actor="user"
            )
            return BacktestAdapterResult(
                metrics={
                    "tradeCount": 120,
                    "profitFactor": 1.4,
                    "averageNetR": 0.18,
                    "maximumDrawdownR": 8.0,
                },
                checks={
                    "costStress": True,
                    "stability": True,
                    "lockedOos": True,
                },
                evidence={"reportSha256": "paused_report_sha"},
            )

        paused = run_backtest_workflow(
            self.workflow,
            self.registry,
            queued.workflowRunId,
            output_root=self.root / "workflow",
            adapter_executor=execute,
        )
        self.assertEqual(paused.status, "paused")
        queue_workflow_run(self.workflow, queued.workflowRunId, actor="user")
        resumed = run_backtest_workflow(
            self.workflow,
            self.registry,
            queued.workflowRunId,
            output_root=self.root / "workflow",
            adapter_executor=execute,
        )

        self.assertEqual(resumed.status, "passed")
        self.assertEqual(call_count, 1)

    def test_running_workflow_rejects_a_second_worker_without_explicit_recovery(self) -> None:
        self.register_snapshot()
        version = self.register_version()
        queued = self.queue_initial(version.strategyVersionId)
        start_workflow_run(self.workflow, queued.workflowRunId, actor="worker")
        called = False

        def execute(context, checkpoint):
            nonlocal called
            called = True
            raise AssertionError("duplicate worker must not execute")

        with self.assertRaisesRegex(
            WorkflowTransitionError,
            "backtest_run_already_has_active_worker",
        ):
            run_backtest_workflow(
                self.workflow,
                self.registry,
                queued.workflowRunId,
                output_root=self.root / "workflow",
                adapter_executor=execute,
            )

        self.assertFalse(called)

    def test_explicit_recovery_can_resume_a_running_workflow(self) -> None:
        self.register_snapshot()
        version = self.register_version()
        queued = self.queue_initial(version.strategyVersionId)
        start_workflow_run(self.workflow, queued.workflowRunId, actor="worker")

        def execute(context, checkpoint):
            return BacktestAdapterResult(
                metrics={
                    "tradeCount": 120,
                    "profitFactor": 1.4,
                    "averageNetR": 0.18,
                    "maximumDrawdownR": 8.0,
                },
                checks={
                    "costStress": True,
                    "stability": True,
                    "lockedOos": True,
                },
                evidence={"reportSha256": "recovered_report_sha"},
            )

        recovered = run_backtest_workflow(
            self.workflow,
            self.registry,
            queued.workflowRunId,
            output_root=self.root / "workflow",
            adapter_executor=execute,
            recover_running=True,
        )

        self.assertEqual(recovered.status, "passed")
        self.assertEqual(
            recovered.result["evidence"]["reportSha256"],
            "recovered_report_sha",
        )

    def test_production_adapter_terminates_child_when_workflow_is_paused(self) -> None:
        class FakeProcess:
            returncode = None

            def __init__(self):
                self.terminated = False

            def poll(self):
                return None

            def terminate(self):
                self.terminated = True
                self.returncode = 1

            def wait(self, timeout=None):
                return self.returncode

        process = FakeProcess()
        statuses = iter(["running", "paused"])
        context = {
            "adapterId": "alpha191_crypto_subset_v13_5_23",
            "projectRoot": str(self.root),
            "runRoot": str(self.root / "adapter-run"),
            "adapterLockPath": str(self.root / "locks" / "alpha191.lock"),
            "workflowStatus": lambda: next(statuses, "paused"),
        }

        with patch(
            "alphapilot.evolution.workflow.backtest.subprocess.Popen",
            return_value=process,
        ):
            with self.assertRaisesRegex(
                BacktestAdapterError,
                "backtest_worker_paused",
            ):
                execute_registered_adapter(context, lambda progress: None)

        self.assertTrue(process.terminated)

    def test_alpha191_observer_is_idempotent_and_waits_at_backtest(self) -> None:
        first = register_alpha191_observer(self.registry, self.workflow)
        second = register_alpha191_observer(self.registry, self.workflow)
        projection = build_workflow_projection(self.workflow)

        self.assertEqual(first, second)
        self.assertEqual(first.displayName, "Alpha191 加密因子观察策略")
        self.assertEqual(first.definition["targetR"], 2.0)
        self.assertIsNone(first.definition["backtest"]["dataSnapshotId"])
        self.assertEqual(projection["summary"]["strategyCount"], 1)
        self.assertEqual(projection["items"][0]["stage"], "backtest")
        self.assertEqual(projection["items"][0]["status"], "awaiting")

    def test_projection_reads_local_formal_collection_checkpoint(self) -> None:
        version = register_alpha191_observer(self.registry, self.workflow)
        contract = derive_strategy_data_contract(version, self.workflow)
        warehouse_root = self.root / "warehouse"
        layout = WarehouseLayout.from_root(warehouse_root)
        layout.ensure_directories()
        write_json_atomic(
            layout.checkpointRoot
            / "local-formal"
            / f"{contract.strategyDataContractId}.json",
            {
                "status": "completed",
                "source": "user_approved_local_market_data",
                "selectedInstruments": ["BTC-USDT-SWAP", "ETH-USDT-SWAP"],
                "requiredTimeframes": ["4h", "5m", "15m"],
            },
        )

        projection = build_workflow_projection(
            self.workflow,
            warehouse_root=warehouse_root,
        )

        self.assertEqual(
            projection["items"][0]["downloadProgress"],
            {
                "completed": 6,
                "required": 150,
                "fundingFiles": 2,
                "mode": "user_approved_local",
                "status": "completed",
            },
        )


if __name__ == "__main__":
    unittest.main()
