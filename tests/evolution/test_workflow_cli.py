from __future__ import annotations

import io
import json
import tempfile
import threading
import unittest
from collections import Counter
from contextlib import redirect_stdout
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from alphapilot.evolution.registry.database import connect_registry
from alphapilot.evolution.registry.repositories import RegistryRepository
from alphapilot.evolution.workflow.cli import (
    _prepare_dual_layer_once,
    _run_selected_forward_cycles,
    main,
)
from alphapilot.evolution.workflow.repository import WorkflowRepository
from alphapilot.evolution.workflow.service import (
    checkpoint_workflow_run,
    complete_workflow_run,
    pause_workflow_run,
    queue_workflow_run,
    start_workflow_run,
)
from alphapilot.evolution.workflow.types import WorkflowRunRecord


class WorkflowCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.registry = self.root / "registry.sqlite"
        self.output_root = self.root / "workflow"
        self.prepare_patcher = patch(
            "alphapilot.evolution.workflow.cli._prepare_dual_layer_once",
            side_effect=lambda workflow, _registry, workflow_run_id, **_kwargs: (
                workflow.get_workflow_run(workflow_run_id)
            ),
            create=True,
        )
        self.prefetch_patcher = patch(
            "alphapilot.evolution.workflow.cli._prepare_backtest_in_fresh_connection",
            return_value=None,
            create=True,
        )
        self.prepare_worker = self.prepare_patcher.start()
        self.prefetch_worker = self.prefetch_patcher.start()

    def tearDown(self) -> None:
        self.prefetch_patcher.stop()
        self.prepare_patcher.stop()
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

    def test_archive_campaign_command_is_available_and_idempotent(self) -> None:
        self.run_cli("bootstrap-short-cycle")
        item = self.run_cli("projection")["items"][0]

        archived = self.run_cli(
            "archive-campaign",
            "--strategy-version-id",
            item["strategyVersionId"],
        )
        repeated = self.run_cli(
            "archive-campaign",
            "--strategy-version-id",
            item["strategyVersionId"],
        )

        self.assertEqual(
            archived["rootStrategyVersionId"],
            item["strategyVersionId"],
        )
        self.assertEqual(
            archived["archivedStrategyVersionIds"],
            [item["strategyVersionId"]],
        )
        self.assertEqual(repeated["archivedStrategyVersionIds"], [])
        self.assertEqual(
            repeated["alreadyArchivedStrategyVersionIds"],
            [item["strategyVersionId"]],
        )

    def test_data_prefetch_stops_before_memory_heavy_snapshot_freeze(self) -> None:
        workflow = Mock()
        registry = Mock()
        with patch(
            "alphapilot.evolution.workflow.cli._run_dual_layer_once"
        ) as run_once:
            _prepare_dual_layer_once(
                workflow,
                registry,
                "workflow_run_1",
                warehouse_root=self.root / "warehouse",
                output_root=self.output_root,
            )

        self.assertEqual(
            run_once.call_args.kwargs["stop_after_phase"],
            "validating_official_data",
        )

    def test_backtest_queue_prioritizes_runs_with_ready_official_data(self) -> None:
        from alphapilot.evolution.workflow.cli import _prioritize_backtest_runs

        waiting_for_data = Mock(
            workflowRunId="waiting_for_data",
            progress={"completedPhases": ["checking_local_data"]},
        )
        ready_for_formal = Mock(
            workflowRunId="ready_for_formal",
            progress={
                "completedPhases": [
                    "checking_local_data",
                    "research_smoke_running",
                    "preparing_official_data",
                    "validating_official_data",
                    "freezing_data_snapshot",
                    "building_validation_manifests",
                ]
            },
        )
        validated_data = Mock(
            workflowRunId="validated_data",
            progress={
                "completedPhases": [
                    "checking_local_data",
                    "research_smoke_running",
                    "preparing_official_data",
                    "validating_official_data",
                ]
            },
        )

        ordered = _prioritize_backtest_runs(
            [waiting_for_data, ready_for_formal, validated_data]
        )

        self.assertEqual(
            [run.workflowRunId for run in ordered],
            ["ready_for_formal", "validated_data", "waiting_for_data"],
        )

    def test_data_ready_backtest_does_not_consume_prefetch_slot(self) -> None:
        from alphapilot.evolution.workflow.cli import _requires_data_prefetch

        ready = Mock(
            progress={
                "completedPhases": [
                    "checking_local_data",
                    "research_smoke_running",
                    "preparing_official_data",
                    "validating_official_data",
                ]
            }
        )
        waiting = Mock(
            progress={
                "completedPhases": [
                    "checking_local_data",
                    "research_smoke_running",
                ]
            }
        )

        self.assertFalse(_requires_data_prefetch(ready))
        self.assertTrue(_requires_data_prefetch(waiting))

    def test_completed_prefetch_returns_run_to_queue(self) -> None:
        from alphapilot.evolution.workflow.cli import (
            _return_prefetched_run_to_queue,
        )

        workflow = Mock()
        workflow.get_workflow_run.return_value = Mock(
            status="running",
            progress={
                "completedPhases": [
                    "checking_local_data",
                    "research_smoke_running",
                    "preparing_official_data",
                    "validating_official_data",
                ]
            },
        )

        with patch(
            "alphapilot.evolution.workflow.cli.yield_workflow_run",
            return_value=Mock(status="queued"),
        ) as yield_run:
            result = _return_prefetched_run_to_queue(workflow, "run-ready")

        yield_run.assert_called_once_with(workflow, "run-ready", actor="worker")
        self.assertEqual(result.status, "queued")

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
        self.assertEqual(projection["version"], "V13.27.6")
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

    def test_redesigned_short_cycle_bootstrap_registers_six_awaiting_candidates(self) -> None:
        first = self.run_cli("bootstrap-redesigned-short-cycle")
        second = self.run_cli("bootstrap-redesigned-short-cycle")
        projection = self.run_cli("projection")
        items = [
            item
            for item in projection["items"]
            if item["sourceType"] == "short_cycle_redesign_pack_v13_27_13"
        ]

        self.assertEqual(first, second)
        self.assertEqual(first["count"], 6)
        self.assertEqual(len(items), 6)
        self.assertEqual(
            {(item["stage"], item["status"]) for item in items},
            {("backtest", "awaiting")},
        )

    def test_evidence_redesigned_bootstrap_registers_six_awaiting_candidates(self) -> None:
        first = self.run_cli("bootstrap-evidence-redesigned-short-cycle")
        second = self.run_cli("bootstrap-evidence-redesigned-short-cycle")
        projection = self.run_cli("projection")
        items = [
            item
            for item in projection["items"]
            if item["sourceType"] == "short_cycle_evidence_redesign_pack_v13_27_15"
        ]

        self.assertEqual(first, second)
        self.assertEqual(first["count"], 6)
        self.assertEqual(len(items), 6)
        self.assertEqual(
            {(item["stage"], item["status"]) for item in items},
            {("backtest", "awaiting")},
        )

    def test_v13_27_17_event_window_bootstrap_registers_only_eligible_versions(self) -> None:
        first = self.run_cli("bootstrap-v13-27-17-event-window")
        second = self.run_cli("bootstrap-v13-27-17-event-window")
        projection = self.run_cli("projection")
        items = [
            item
            for item in projection["items"]
            if item["sourceType"]
            == "event_window_research_eligible_pack_v13_27_17"
        ]

        self.assertEqual(first, second)
        self.assertEqual(first["count"], 7)
        self.assertEqual(len(items), 7)
        self.assertEqual(
            {(item["stage"], item["status"]) for item in items},
            {("backtest", "awaiting")},
        )

    def test_v13_27_18_cross_timeframe_bootstrap_registers_five_per_timeframe(self) -> None:
        first = self.run_cli("bootstrap-v13-27-18-cross-timeframe")
        second = self.run_cli("bootstrap-v13-27-18-cross-timeframe")
        projection = self.run_cli("projection")
        items = [
            item
            for item in projection["items"]
            if item["sourceType"] == "cross_timeframe_research_pack_v13_27_18"
        ]

        self.assertEqual(first, second)
        self.assertEqual(first["count"], 25)
        self.assertEqual(len(items), 25)
        self.assertEqual(
            Counter(
                item["optimizationContext"]["definition"]["timeframe"]
                for item in items
            ),
            {"5m": 5, "15m": 5, "1h": 5, "4h": 5, "1d": 5},
        )
        self.assertEqual(
            {(item["stage"], item["status"]) for item in items},
            {("backtest", "awaiting")},
        )

        connection = connect_registry(self.registry)
        try:
            workflow = WorkflowRepository(connection)
            versions = {
                version.strategyVersionId: version
                for version in workflow.list_strategy_versions()
                if version.sourceType == "cross_timeframe_research_pack_v13_27_18"
            }
            for run in workflow.list_workflow_runs():
                version = versions.get(run.strategyVersionId)
                if version is None:
                    continue
                profile = workflow.get_gate_profile(str(run.gateProfileId))
                self.assertIsNotNone(profile)
                expected_minimum = (
                    12 if version.definition["timeframe"] == "1d" else 30
                )
                self.assertEqual(profile.rules["minimumTradeCount"], expected_minimum)
                self.assertEqual(profile.rules["minimumTargetR"], 2.0)
                self.assertEqual(profile.rules["minimumProfitFactor"], 1.1)
                self.assertTrue(profile.rules["requiresCostStress"])
                self.assertTrue(profile.rules["requiresLockedOos"])
        finally:
            connection.close()

    def test_failed_backtest_drains_three_bounded_challengers_in_same_batch(self) -> None:
        self.run_cli("bootstrap-short-cycle")
        projection = self.run_cli("projection")
        root = next(
            item
            for item in projection["items"]
            if item["optimizationContext"]["definition"]["signalFamily"]
            == "ema_reclaim_long"
        )
        metrics = {
            "bySplit": {
                split: {
                    "tradeCount": 40,
                    "profitFactor": 1.0,
                    "averageNetR": 0.02,
                    "maximumDrawdownR": 8.0,
                }
                for split in ("development", "walk_forward")
            },
            "costStress": {
                "bySplit": {
                    split: {"tradeCount": 40, "averageNetR": 0.01}
                    for split in ("development", "walk_forward")
                }
            },
        }

        def fail_run(workflow, _registry, workflow_run_id, **_kwargs):
            current = workflow.get_workflow_run(workflow_run_id)
            assert current is not None
            if current.status == "queued":
                current = start_workflow_run(
                    workflow,
                    current.workflowRunId,
                    actor="worker",
                )
            return complete_workflow_run(
                workflow,
                current.workflowRunId,
                status="failed",
                actor="worker",
                result={"metrics": metrics, "checks": {"minimumProfitFactor": False}},
                evidence={"fixture": "bounded_campaign"},
                failure={
                    "category": "strategy_performance",
                    "summary": "Selection profit factor is below the gate.",
                    "retryDisposition": "new_version_required",
                    "metrics": {"failedChecks": ["minimumProfitFactor"]},
                    "suggestions": ["Run bounded optimization."],
                },
            )

        with patch(
            "alphapilot.evolution.workflow.cli._run_dual_layer_once",
            side_effect=fail_run,
        ):
            result = self.run_cli(
                "run-selected-backtests",
                "--run-id",
                root["workflowRunId"],
            )

        self.assertEqual(result["processedCount"], 4)
        self.assertEqual(len(result["drainedWorkflowRunIds"]), 4)
        connection = connect_registry(self.registry)
        try:
            workflow = WorkflowRepository(connection)
            registry = RegistryRepository(connection)
            versions = [
                version
                for version in workflow.list_strategy_versions()
                if (
                    version.definition.get("optimizationLineage") or {}
                ).get("rootStrategyVersionId")
                == root["strategyVersionId"]
            ]
            events = registry.list_audit_events(
                event_type="bounded_auto_optimization",
                entity_type="StrategyVersion",
                entity_id=root["strategyVersionId"],
            )
        finally:
            connection.close()
        self.assertEqual(len(versions), 3)
        self.assertEqual(len(events), 4)
        self.assertEqual(events[-1].payload["terminalStatus"], "budget_exhausted")

    def test_structurally_weak_backtest_queues_and_drains_one_structural_child(self) -> None:
        self.run_cli("bootstrap-short-cycle")
        root = next(
            item
            for item in self.run_cli("projection")["items"]
            if item["optimizationContext"]["definition"]["signalFamily"]
            == "ema_reclaim_long"
        )
        weak = {
            "bySplit": {
                split: {
                    "tradeCount": 100,
                    "profitFactor": 0.5,
                    "averageNetR": -0.35,
                    "maximumDrawdownR": 30.0,
                }
                for split in ("development", "walk_forward")
            },
            "costStress": {
                "bySplit": {
                    split: {"tradeCount": 100, "averageNetR": -0.5}
                    for split in ("development", "walk_forward")
                }
            },
        }

        def finish_run(workflow, _registry, workflow_run_id, **_kwargs):
            current = workflow.get_workflow_run(workflow_run_id)
            assert current is not None
            if current.status == "queued":
                current = start_workflow_run(
                    workflow,
                    current.workflowRunId,
                    actor="worker",
                )
            version = workflow.get_strategy_version(current.strategyVersionId)
            assert version is not None
            is_structural_child = bool(
                version.definition.get("structuralRedesignLineage")
            )
            return complete_workflow_run(
                workflow,
                current.workflowRunId,
                status="passed" if is_structural_child else "failed",
                actor="worker",
                result={"metrics": weak, "checks": {}},
                evidence={"fixture": "structural_worker_hook"},
                failure=(
                    None
                    if is_structural_child
                    else {
                        "category": "strategy_performance",
                        "summary": "fixture structural weakness",
                        "retryDisposition": "new_version_required",
                        "metrics": {},
                        "suggestions": [],
                    }
                ),
            )

        with patch(
            "alphapilot.evolution.workflow.cli._run_dual_layer_once",
            side_effect=finish_run,
        ):
            result = self.run_cli(
                "run-selected-backtests",
                "--run-id",
                root["workflowRunId"],
            )

        self.assertEqual(result["processedCount"], 2)
        self.assertEqual(len(result["drainedWorkflowRunIds"]), 2)
        self.assertEqual(result["formalWorkerCount"], 1)
        self.assertEqual(result["dataPrefetchWorkerCount"], 1)
        connection = connect_registry(self.registry)
        try:
            workflow = WorkflowRepository(connection)
            parent = workflow.get_strategy_version(root["strategyVersionId"])
            assert parent is not None
            children = [
                version
                for version in workflow.list_strategy_versions()
                if version.parentStrategyVersionId == parent.strategyVersionId
                and version.definition.get("structuralRedesignLineage")
            ]
            self.assertEqual(len(children), 1)
            child_run = workflow.get_latest_workflow_run(
                children[0].strategyVersionId,
                stage="backtest",
            )
            assert child_run is not None
        finally:
            connection.close()
        self.assertEqual(parent.status, "archived")
        self.assertIn(child_run.workflowRunId, result["drainedWorkflowRunIds"])

    def test_recover_structural_redesigns_creates_online_backup(self) -> None:
        self.run_cli("bootstrap-short-cycle")
        item = self.run_cli("projection")["items"][0]
        weak = {
            "bySplit": {
                split: {
                    "tradeCount": 100,
                    "profitFactor": 0.5,
                    "averageNetR": -0.35,
                    "maximumDrawdownR": 30.0,
                }
                for split in ("development", "walk_forward")
            },
            "costStress": {
                "bySplit": {
                    split: {"tradeCount": 100, "averageNetR": -0.5}
                    for split in ("development", "walk_forward")
                }
            },
        }
        connection = connect_registry(self.registry)
        try:
            workflow = WorkflowRepository(connection)
            queued = queue_workflow_run(
                workflow,
                item["workflowRunId"],
                actor="user",
            )
            running = start_workflow_run(
                workflow,
                queued.workflowRunId,
                actor="worker",
            )
            complete_workflow_run(
                workflow,
                running.workflowRunId,
                status="failed",
                actor="worker",
                result={"metrics": weak, "checks": {}},
                evidence={"fixture": "structural_recovery"},
                failure={
                    "category": "strategy_performance",
                    "summary": "old structural failure",
                    "retryDisposition": "new_version_required",
                    "metrics": {},
                    "suggestions": [],
                },
            )
        finally:
            connection.close()

        first = self.run_cli(
            "recover-structural-redesigns",
            "--strategy-version-id",
            item["strategyVersionId"],
        )
        repeated = self.run_cli(
            "recover-structural-redesigns",
            "--strategy-version-id",
            item["strategyVersionId"],
        )

        self.assertEqual(first["reviewedCount"], 1)
        self.assertEqual(first["createdChildCount"], 1)
        self.assertTrue(Path(first["backupPath"]).is_file())
        self.assertEqual(repeated["reviewedCount"], 0)
        self.assertEqual(repeated["alreadyReviewedCount"], 1)
        self.assertIsNone(repeated["backupPath"])

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

    def test_recover_bounded_optimizations_reviews_an_old_terminal_run(self) -> None:
        self.run_cli("bootstrap-short-cycle")
        item = self.run_cli("projection")["items"][0]
        connection = connect_registry(self.registry)
        try:
            workflow = WorkflowRepository(connection)
            queued = queue_workflow_run(
                workflow,
                item["workflowRunId"],
                actor="user",
            )
            running = start_workflow_run(
                workflow,
                queued.workflowRunId,
                actor="worker",
            )
            complete_workflow_run(
                workflow,
                running.workflowRunId,
                status="blocked",
                actor="worker",
                result={"metrics": {}, "checks": {}},
                evidence={"fixture": "old_terminal_run"},
                failure={
                    "category": "worker_operational",
                    "summary": "worker stopped before optimization review",
                    "retryDisposition": "same_version_retry",
                    "metrics": {},
                    "suggestions": [],
                },
            )
        finally:
            connection.close()

        result = self.run_cli(
            "recover-bounded-optimizations",
            "--strategy-version-id",
            item["strategyVersionId"],
        )

        self.assertEqual(result["reviewedCount"], 1)
        self.assertEqual(result["stoppedCount"], 1)
        self.assertEqual(result["challengerWorkflowRunIds"], [])
        refreshed = next(
            candidate
            for candidate in self.run_cli("projection")["items"]
            if candidate["strategyVersionId"] == item["strategyVersionId"]
        )
        self.assertTrue(refreshed["optimizationCampaign"]["reviewed"])

    def test_migrate_local_formal_resets_obsolete_active_progress(self) -> None:
        self.run_cli("bootstrap-short-cycle")
        item = self.run_cli("projection")["items"][0]
        connection = connect_registry(self.registry)
        try:
            workflow = WorkflowRepository(connection)
            queued = queue_workflow_run(
                workflow,
                item["workflowRunId"],
                actor="user",
            )
            running = start_workflow_run(
                workflow,
                queued.workflowRunId,
                actor="worker",
            )
            checkpoint_workflow_run(
                workflow,
                running.workflowRunId,
                progress={
                    "phase": "preparing_official_data",
                    "completedPhases": [
                        "checking_local_data",
                        "research_smoke_running",
                        "preparing_official_data",
                    ],
                    "artifacts": {
                        "strategyDataContractId": "contract-1",
                        "researchSmokePath": "smoke.json",
                        "officialCollectionPath": "old-official.json",
                    },
                },
                actor="worker",
            )
        finally:
            connection.close()

        result = self.run_cli(
            "migrate-local-formal",
            "--strategy-version-id",
            item["strategyVersionId"],
        )
        repeated = self.run_cli(
            "migrate-local-formal",
            "--strategy-version-id",
            item["strategyVersionId"],
        )

        self.assertEqual(result["migratedCount"], 1)
        self.assertTrue(Path(result["backupPath"]).is_file())
        self.assertEqual(repeated["migratedCount"], 0)
        refreshed = next(
            candidate
            for candidate in self.run_cli("projection")["items"]
            if candidate["strategyVersionId"] == item["strategyVersionId"]
        )
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
        statuses_when_first_worker_started: list[str] = []

        def fake_worker(workflow, _registry, workflow_run_id, **_kwargs):
            if not observed:
                statuses_when_first_worker_started.extend(
                    workflow.get_workflow_run(run_id).status
                    for run_id in requested_ids
                )
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
        self.assertEqual(statuses_when_first_worker_started, ["queued", "queued"])
        self.assertEqual(result["processedCount"], 2)
        self.assertEqual(result["workflowRunIds"], requested_ids)
        self.assertEqual(
            [run["status"] for run in result["runs"]], ["queued", "queued"]
        )

    def test_selected_backtests_prefetch_queue_while_current_formal_runs(self) -> None:
        self.prepare_patcher.stop()
        self.prefetch_patcher.stop()
        self.run_cli("bootstrap-short-cycle")
        items = self.run_cli("projection")["items"][:3]
        first_id, second_id, third_id = [item["workflowRunId"] for item in items]
        third_prefetch_started = threading.Event()
        observed: list[str] = []

        def prepare_current(workflow, _registry, workflow_run_id, **_kwargs):
            observed.append(f"prepare:{workflow_run_id}")
            return workflow.get_workflow_run(workflow_run_id)

        def prefetch_next(*_args, workflow_run_id, **_kwargs):
            observed.append(f"prefetch:{workflow_run_id}")
            if workflow_run_id == third_id:
                third_prefetch_started.set()

        def run_formal(workflow, _registry, workflow_run_id, **_kwargs):
            if workflow_run_id == first_id:
                self.assertTrue(third_prefetch_started.wait(timeout=2))
            observed.append(f"formal:{workflow_run_id}")
            return workflow.get_workflow_run(workflow_run_id)

        try:
            with patch(
                "alphapilot.evolution.workflow.cli._prepare_dual_layer_once",
                side_effect=prepare_current,
                create=True,
            ), patch(
                "alphapilot.evolution.workflow.cli._prepare_backtest_in_fresh_connection",
                side_effect=prefetch_next,
                create=True,
            ), patch(
                "alphapilot.evolution.workflow.cli._run_dual_layer_once",
                side_effect=run_formal,
            ):
                result = self.run_cli(
                    "run-selected-backtests",
                    "--run-id",
                    first_id,
                    "--run-id",
                    second_id,
                    "--run-id",
                    third_id,
                )
        finally:
            self.prepare_worker = self.prepare_patcher.start()
            self.prefetch_worker = self.prefetch_patcher.start()

        self.assertEqual(result["processedCount"], 3)
        self.assertIn(f"prefetch:{second_id}", observed)
        self.assertIn(f"prefetch:{third_id}", observed)
        self.assertLess(
            observed.index(f"prefetch:{third_id}"),
            observed.index(f"formal:{first_id}"),
        )
        self.assertNotIn(f"prepare:{second_id}", observed)
        self.assertNotIn(f"prepare:{third_id}", observed)

    def test_selected_backtests_exit_when_another_serial_batch_is_active(self) -> None:
        self.run_cli("bootstrap-short-cycle")
        run_id = self.run_cli("projection")["items"][0]["workflowRunId"]

        with patch(
            "alphapilot.evolution.workflow.cli.workflow_batch_lock",
            create=True,
        ) as batch_lock, patch(
            "alphapilot.evolution.workflow.cli._run_dual_layer_once"
        ) as worker:
            batch_lock.return_value.__enter__.return_value = False
            batch_lock.return_value.__exit__.return_value = None
            result = self.run_cli(
                "run-selected-backtests",
                "--run-id",
                run_id,
            )

        worker.assert_not_called()
        self.assertTrue(result["batchAlreadyRunning"])
        self.assertEqual(result["processedCount"], 0)
        self.assertEqual(result["workflowRunIds"], [run_id])

    def test_one_click_backtest_queues_then_yields_to_an_active_serial_batch(self) -> None:
        self.run_cli("bootstrap-short-cycle")
        run_id = self.run_cli("projection")["items"][0]["workflowRunId"]
        connection = connect_registry(self.registry)
        try:
            workflow = WorkflowRepository(connection)
            current = workflow.get_workflow_run(run_id)
        finally:
            connection.close()
        self.assertIsNotNone(current)

        with patch(
            "alphapilot.evolution.workflow.cli.workflow_batch_lock"
        ) as batch_lock, patch(
            "alphapilot.evolution.workflow.cli._run_dual_layer_once",
            return_value=current,
        ) as worker:
            batch_lock.return_value.__enter__.return_value = False
            batch_lock.return_value.__exit__.return_value = None
            result = self.run_cli(
                "one-click-backtest",
                "--run-id",
                run_id,
            )

        worker.assert_not_called()
        self.assertTrue(result["batchAlreadyRunning"])
        self.assertEqual(result["status"], "queued")

    def test_active_serial_batch_drains_newly_queued_backtests(self) -> None:
        self.run_cli("bootstrap-short-cycle")
        items = self.run_cli("projection")["items"][:2]
        first_id, second_id = [item["workflowRunId"] for item in items]
        observed: list[str] = []

        def fake_worker(workflow, _registry, workflow_run_id, **_kwargs):
            observed.append(workflow_run_id)
            if workflow_run_id == first_id:
                queue_workflow_run(workflow, second_id, actor="user")
            return workflow.get_workflow_run(workflow_run_id)

        with patch(
            "alphapilot.evolution.workflow.cli._run_dual_layer_once",
            side_effect=fake_worker,
        ):
            result = self.run_cli(
                "run-selected-backtests",
                "--run-id",
                first_id,
            )

        self.assertEqual(observed, [first_id, second_id])
        self.assertEqual(result["processedCount"], 2)

    def test_selected_backtests_recover_missed_structural_failures_before_drain(
        self,
    ) -> None:
        self.run_cli("bootstrap-short-cycle")
        run_id = self.run_cli("projection")["items"][0]["workflowRunId"]

        with patch(
            "alphapilot.evolution.workflow.cli.recover_terminal_structural_redesigns"
        ) as recover_structural, patch(
            "alphapilot.evolution.workflow.cli._run_dual_layer_once",
            side_effect=lambda workflow, _registry, workflow_run_id, **_kwargs: (
                workflow.get_workflow_run(workflow_run_id)
            ),
        ):
            self.run_cli("run-selected-backtests", "--run-id", run_id)

        recover_structural.assert_called_once()
        self.assertEqual(
            Path(recover_structural.call_args.kwargs["registry_path"]),
            self.registry,
        )

    def test_selected_backtests_auto_retry_operational_blocker(self) -> None:
        self.run_cli("bootstrap-short-cycle")
        run_id = self.run_cli("projection")["items"][0]["workflowRunId"]

        def blocked_worker(workflow, _registry, workflow_run_id, **_kwargs):
            current = workflow.get_workflow_run(workflow_run_id)
            return replace(current, status="blocked", attemptNumber=1)

        with patch(
            "alphapilot.evolution.workflow.cli._run_dual_layer_once",
            side_effect=blocked_worker,
        ), patch(
            "alphapilot.evolution.workflow.cli.process_bounded_optimization_result",
            return_value=SimpleNamespace(
                decision=SimpleNamespace(terminalStatus="non_performance_failure")
            ),
        ), patch(
            "alphapilot.evolution.workflow.cli.retry_backtest_for_data_preparation",
            return_value=SimpleNamespace(workflowRunId=run_id, status="queued"),
        ) as retry_blocked:
            self.run_cli("run-selected-backtests", "--run-id", run_id)

        retry_blocked.assert_called_once_with(
            unittest.mock.ANY,
            run_id,
            actor="system",
        )

    def test_selected_backtests_stop_auto_retry_after_third_operational_attempt(
        self,
    ) -> None:
        self.run_cli("bootstrap-short-cycle")
        run_id = self.run_cli("projection")["items"][0]["workflowRunId"]

        def blocked_worker(workflow, _registry, workflow_run_id, **_kwargs):
            current = workflow.get_workflow_run(workflow_run_id)
            return replace(current, status="blocked", attemptNumber=3)

        with patch(
            "alphapilot.evolution.workflow.cli._run_dual_layer_once",
            side_effect=blocked_worker,
        ), patch(
            "alphapilot.evolution.workflow.cli.process_bounded_optimization_result",
            return_value=SimpleNamespace(
                decision=SimpleNamespace(terminalStatus="non_performance_failure")
            ),
        ), patch(
            "alphapilot.evolution.workflow.cli.retry_backtest_for_data_preparation",
            return_value=SimpleNamespace(workflowRunId=run_id, status="queued"),
        ) as retry_blocked:
            self.run_cli("run-selected-backtests", "--run-id", run_id)

        retry_blocked.assert_not_called()

    def test_selected_backtests_recover_queued_and_running_runs_serially(self) -> None:
        self.run_cli("bootstrap-short-cycle")
        items = self.run_cli("projection")["items"][:2]
        run_ids = [item["workflowRunId"] for item in items]
        connection = connect_registry(self.registry)
        try:
            workflow = WorkflowRepository(connection)
            queue_workflow_run(workflow, run_ids[0], actor="user")
            queue_workflow_run(workflow, run_ids[1], actor="user")
            start_workflow_run(workflow, run_ids[1], actor="worker")
        finally:
            connection.close()
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
                run_ids[0],
                "--run-id",
                run_ids[1],
            )

        self.assertEqual(observed, run_ids)
        self.assertEqual(
            [item["status"] for item in result["runs"]],
            ["queued", "running"],
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
        self.run_cli("cancel", "--run-id", run_id)
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

    def test_one_click_keeps_a_durable_queue_when_another_worker_holds_the_lock(self) -> None:
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
        self.assertEqual(result["status"], "queued")

    def test_one_click_resume_waits_for_paused_worker_lock_handoff(self) -> None:
        self.run_cli("bootstrap")
        run_id = self.run_cli("projection")["items"][0]["workflowRunId"]
        connection = connect_registry(self.registry)
        try:
            workflow = WorkflowRepository(connection)
            queue_workflow_run(workflow, run_id, actor="user")
            start_workflow_run(workflow, run_id, actor="worker")
            pause_workflow_run(workflow, run_id, actor="user")
        finally:
            connection.close()

        with patch(
            "alphapilot.evolution.workflow.cli.workflow_worker_lock"
        ) as lock, patch(
            "alphapilot.evolution.workflow.cli.run_dual_layer_backtest_workflow"
        ) as worker:
            lock.return_value.__enter__.return_value = True
            worker.side_effect = (
                lambda workflow, _registry, workflow_run_id, **_kwargs: (
                    workflow.get_workflow_run(workflow_run_id)
                )
            )
            result = self.run_cli("one-click-backtest", "--run-id", run_id)

        lock.assert_called_once_with(
            str(self.output_root),
            run_id,
            wait_seconds=120.0,
        )
        self.assertEqual(result["status"], "queued")


if __name__ == "__main__":
    unittest.main()
