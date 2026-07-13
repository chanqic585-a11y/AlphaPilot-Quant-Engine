from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from alphapilot.evolution.registry.database import connect_registry
from alphapilot.evolution.registry.hashing import stable_hash
from alphapilot.evolution.registry.repositories import (
    ImmutableRecordConflict,
    RegistryRepository,
)
from alphapilot.evolution.registry.types import StrategyFamilyRecord
from alphapilot.evolution.workflow import (
    GateProfileRecord,
    WorkflowConflict,
    WorkflowRepository,
    WorkflowTransitionError,
    archive_strategy_version,
    build_workflow_projection,
    cancel_workflow_run,
    checkpoint_workflow_run,
    complete_workflow_run,
    create_challenger_version,
    create_next_stage_run,
    pause_workflow_run,
    queue_workflow_run,
    register_strategy_version,
    retry_workflow_run,
    start_workflow_run,
    yield_workflow_run,
)


class WorkflowOrchestratorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "registry.sqlite"
        self.connection = connect_registry(self.path)
        self.registry = RegistryRepository(self.connection)
        self.workflow = WorkflowRepository(self.connection)
        family_payload = {"scope": "workflow_test"}
        self.family = StrategyFamilyRecord(
            strategyFamilyId="family_workflow_test",
            familyKey="workflow_test",
            name="Workflow Test",
            status="research_only",
            metadata=family_payload,
            contentHash=stable_hash(family_payload),
        )
        self.registry.create_strategy_family(self.family)

    def tearDown(self) -> None:
        self.connection.close()
        self.temp.cleanup()

    def register(self, *, threshold: float = 1.0):
        return register_strategy_version(
            self.workflow,
            strategy_family_id=self.family.strategyFamilyId,
            display_name="趋势回撤测试策略",
            source_type="manual_import",
            definition={"entry": "trend_pullback", "targetR": 2.0},
            parameters={"threshold": threshold},
        )

    def start_initial_run(self):
        version = self.register()
        run = self.workflow.get_latest_workflow_run(version.strategyVersionId)
        self.assertIsNotNone(run)
        queued = queue_workflow_run(self.workflow, run.workflowRunId, actor="user")
        return version, start_workflow_run(
            self.workflow, queued.workflowRunId, actor="worker"
        )

    def test_registration_is_idempotent_and_creates_backtest_awaiting_run(self) -> None:
        first = self.register()
        second = self.register()
        runs = self.workflow.list_workflow_runs(strategy_version_id=first.strategyVersionId)

        self.assertEqual(first, second)
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0].stage, "backtest")
        self.assertEqual(runs[0].status, "awaiting")
        self.assertEqual(self.workflow.count("StrategyVersions"), 1)

    def test_missing_initial_gate_fails_before_strategy_version_is_written(self) -> None:
        with self.assertRaisesRegex(
            WorkflowConflict,
            "initial_gate_profile_missing:missing_gate",
        ):
            register_strategy_version(
                self.workflow,
                strategy_family_id=self.family.strategyFamilyId,
                display_name="无效门禁测试策略",
                source_type="test_fixture",
                definition={"entry": "test", "targetR": 2.0},
                parameters={"threshold": 1.0},
                initial_gate_profile_id="missing_gate",
            )

        self.assertEqual(self.workflow.count("StrategyVersions"), 0)
        self.assertEqual(self.workflow.count("WorkflowRuns"), 0)

    def test_user_cannot_mark_a_workflow_run_passed(self) -> None:
        _, running = self.start_initial_run()

        with self.assertRaises(WorkflowTransitionError):
            complete_workflow_run(
                self.workflow,
                running.workflowRunId,
                status="passed",
                actor="user",
                result={"profitFactor": 1.4},
                evidence={"lockedOosHash": "oos_hash"},
            )

        current = self.workflow.get_workflow_run(running.workflowRunId)
        self.assertEqual(current.status, "running")

    def test_user_cannot_start_the_worker_directly(self) -> None:
        version = self.register()
        awaiting = self.workflow.get_latest_workflow_run(version.strategyVersionId)
        queued = queue_workflow_run(
            self.workflow, awaiting.workflowRunId, actor="user"
        )

        with self.assertRaises(WorkflowTransitionError):
            start_workflow_run(self.workflow, queued.workflowRunId, actor="user")

    def test_running_work_can_pause_resume_and_cancel_without_changing_version(self) -> None:
        version, running = self.start_initial_run()
        paused = pause_workflow_run(
            self.workflow, running.workflowRunId, actor="user"
        )
        repeated_pause = pause_workflow_run(
            self.workflow, running.workflowRunId, actor="user"
        )
        resumed = queue_workflow_run(
            self.workflow, running.workflowRunId, actor="user"
        )
        cancelled = cancel_workflow_run(
            self.workflow, running.workflowRunId, actor="user"
        )

        self.assertEqual(paused, repeated_pause)
        self.assertEqual(resumed.status, "queued")
        self.assertEqual(cancelled.status, "cancelled")
        self.assertEqual(cancelled.strategyVersionId, version.strategyVersionId)

    def test_queued_work_can_pause_and_resume_without_becoming_cancelled(self) -> None:
        version = self.register()
        awaiting = self.workflow.get_latest_workflow_run(version.strategyVersionId)
        queued = queue_workflow_run(
            self.workflow, awaiting.workflowRunId, actor="user"
        )

        paused = pause_workflow_run(
            self.workflow, queued.workflowRunId, actor="user"
        )
        repeated_pause = pause_workflow_run(
            self.workflow, queued.workflowRunId, actor="user"
        )
        resumed = queue_workflow_run(
            self.workflow, queued.workflowRunId, actor="user"
        )

        self.assertEqual(paused.status, "paused")
        self.assertEqual(repeated_pause, paused)
        self.assertEqual(resumed.status, "queued")

    def test_worker_can_yield_prefetched_work_back_to_queue(self) -> None:
        version, running = self.start_initial_run()

        yielded = yield_workflow_run(
            self.workflow,
            running.workflowRunId,
            actor="worker",
        )

        self.assertEqual(yielded.status, "queued")
        self.assertEqual(yielded.strategyVersionId, version.strategyVersionId)
        with self.assertRaises(WorkflowTransitionError):
            yield_workflow_run(
                self.workflow,
                yielded.workflowRunId,
                actor="user",
            )

    def test_cancelled_work_can_restart_from_its_checkpoint_idempotently(self) -> None:
        version, running = self.start_initial_run()
        checkpointed = checkpoint_workflow_run(
            self.workflow,
            running.workflowRunId,
            progress={"phase": "preparing_official_data", "completed": 67},
            actor="worker",
        )
        cancelled = cancel_workflow_run(
            self.workflow, checkpointed.workflowRunId, actor="user"
        )

        restarted = retry_workflow_run(
            self.workflow, cancelled.workflowRunId, actor="user"
        )
        repeated = retry_workflow_run(
            self.workflow, cancelled.workflowRunId, actor="user"
        )

        self.assertEqual(restarted, repeated)
        self.assertEqual(restarted.strategyVersionId, version.strategyVersionId)
        self.assertEqual(restarted.attemptNumber, 2)
        self.assertEqual(restarted.status, "queued")
        self.assertEqual(restarted.progress, checkpointed.progress)
        self.assertEqual(cancelled.status, "cancelled")

    def test_archive_hides_version_from_active_page_without_deleting_history(self) -> None:
        version = self.register()
        archived = archive_strategy_version(
            self.workflow, version.strategyVersionId, actor="user"
        )
        repeated = archive_strategy_version(
            self.workflow, version.strategyVersionId, actor="user"
        )
        projection = build_workflow_projection(self.workflow)

        self.assertEqual(archived, repeated)
        self.assertEqual(archived.status, "archived")
        self.assertEqual(projection["summary"]["totalStrategyVersionCount"], 1)
        self.assertEqual(projection["summary"]["strategyCount"], 0)
        self.assertEqual(projection["summary"]["archivedCount"], 1)
        self.assertEqual(projection["items"], [])
        self.assertEqual(len(projection["archivedItems"]), 1)
        self.assertGreaterEqual(
            projection["archivedItems"][0]["historyEventCount"], 2
        )

    def test_passed_backtest_can_create_one_local_forward_run(self) -> None:
        version, running = self.start_initial_run()
        passed = complete_workflow_run(
            self.workflow,
            running.workflowRunId,
            status="passed",
            actor="worker",
            result={"profitFactor": 1.4, "targetR": 2.0},
            evidence={"lockedOosHash": "oos_hash", "walkForwardHash": "wf_hash"},
        )
        forward = create_next_stage_run(
            self.workflow, version.strategyVersionId, actor="user"
        )
        repeated = create_next_stage_run(
            self.workflow, version.strategyVersionId, actor="user"
        )
        projection = build_workflow_projection(self.workflow)

        self.assertEqual(passed.status, "passed")
        self.assertEqual(forward, repeated)
        self.assertEqual(forward.stage, "local_forward")
        self.assertEqual(forward.status, "awaiting")
        self.assertEqual(projection["summary"]["localSimulationCount"], 1)
        self.assertEqual(projection["summary"]["strategyCount"], 0)
        self.assertEqual(projection["items"][0]["page"], "local_simulation")

    def test_operational_failure_can_retry_same_version(self) -> None:
        version, running = self.start_initial_run()
        failed = complete_workflow_run(
            self.workflow,
            running.workflowRunId,
            status="failed",
            actor="worker",
            result={"completedShards": 2},
            evidence={"workerLogHash": "worker_log"},
            failure={
                "category": "worker_operational",
                "summary": "Worker interrupted after a checkpoint.",
                "retryDisposition": "same_version_retry",
                "metrics": {"completedShards": 2},
                "suggestions": ["Resume from the latest checkpoint."],
            },
        )
        retry = retry_workflow_run(self.workflow, failed.workflowRunId, actor="user")
        repeated = retry_workflow_run(self.workflow, failed.workflowRunId, actor="user")

        self.assertEqual(retry, repeated)
        self.assertEqual(retry.strategyVersionId, version.strategyVersionId)
        self.assertEqual(retry.attemptNumber, 2)
        self.assertEqual(retry.status, "queued")

    def test_blocked_operational_retry_is_idempotent(self) -> None:
        _, running = self.start_initial_run()
        blocked = complete_workflow_run(
            self.workflow,
            running.workflowRunId,
            status="blocked",
            actor="worker",
            result={"completedShards": 2},
            evidence={"workerLogHash": "blocked_worker_log"},
            failure={
                "category": "worker_operational",
                "summary": "Worker dependency is temporarily unavailable.",
                "retryDisposition": "same_version_retry",
                "metrics": {"completedShards": 2},
                "suggestions": ["Retry after the dependency recovers."],
            },
        )

        retry = retry_workflow_run(self.workflow, blocked.workflowRunId, actor="user")
        repeated = retry_workflow_run(
            self.workflow, blocked.workflowRunId, actor="user"
        )

        self.assertEqual(retry, repeated)
        self.assertEqual(retry.attemptNumber, 2)
        self.assertEqual(retry.status, "queued")
        original = self.workflow.get_workflow_run(blocked.workflowRunId)
        self.assertEqual(original.status, "cancelled")

    def test_strategy_failure_requires_changed_challenger(self) -> None:
        version, running = self.start_initial_run()
        failed = complete_workflow_run(
            self.workflow,
            running.workflowRunId,
            status="failed",
            actor="worker",
            result={"profitFactor": 0.7},
            evidence={"lockedOosHash": "failed_oos"},
            failure={
                "category": "strategy_performance",
                "summary": "Locked OOS profit factor is below the gate.",
                "retryDisposition": "new_version_required",
                "metrics": {"profitFactor": 0.7},
                "suggestions": ["Research a stricter trend filter."],
            },
        )

        with self.assertRaises(WorkflowTransitionError):
            retry_workflow_run(self.workflow, failed.workflowRunId, actor="user")
        with self.assertRaises(WorkflowConflict):
            create_challenger_version(
                self.workflow,
                parent_strategy_version_id=version.strategyVersionId,
                display_name="趋势回撤测试策略 v2",
                source_type="generated_challenger",
                definition=version.definition,
                parameters=version.parameters,
            )

        challenger = create_challenger_version(
            self.workflow,
            parent_strategy_version_id=version.strategyVersionId,
            display_name="趋势回撤测试策略 v2",
            source_type="generated_challenger",
            definition=version.definition,
            parameters={"threshold": 1.2},
        )
        challenger_run = self.workflow.get_latest_workflow_run(
            challenger.strategyVersionId
        )

        self.assertEqual(challenger.parentStrategyVersionId, version.strategyVersionId)
        self.assertNotEqual(challenger.contentHash, version.contentHash)
        self.assertEqual(challenger_run.stage, "backtest")
        self.assertEqual(challenger_run.status, "awaiting")

    def test_checkpoint_survives_repository_reconnect(self) -> None:
        _, running = self.start_initial_run()
        checkpoint_workflow_run(
            self.workflow,
            running.workflowRunId,
            progress={"completedShards": 3, "totalShards": 10},
            actor="worker",
        )
        self.connection.close()

        self.connection = connect_registry(self.path)
        self.registry = RegistryRepository(self.connection)
        self.workflow = WorkflowRepository(self.connection)
        recovered = self.workflow.get_workflow_run(running.workflowRunId)

        self.assertEqual(recovered.status, "running")
        self.assertEqual(recovered.progress["completedShards"], 3)
        events = self.workflow.list_stage_events(workflow_run_id=running.workflowRunId)
        self.assertTrue(any(event.reasonCode == "checkpoint_saved" for event in events))

    def test_second_active_run_for_same_version_and_stage_is_rejected(self) -> None:
        version = self.register()

        with self.assertRaises(WorkflowConflict):
            self.workflow.create_workflow_run(
                strategy_version_id=version.strategyVersionId,
                stage="backtest",
                status="awaiting",
                attempt_number=2,
                gate_profile_id=None,
                risk_profile_id=None,
                idempotency_key="different-active-run",
                progress={},
                result={},
            )

    def test_gate_profile_is_immutable_and_idempotent(self) -> None:
        rules = {"minimumClosedSamples": 30, "minimumTargetR": 2.0}
        profile = GateProfileRecord(
            gateProfileId="gate_backtest_v1",
            profileKey="default_backtest",
            version=1,
            stage="backtest",
            status="active",
            rules=rules,
            contentHash=stable_hash(rules),
        )
        first = self.workflow.create_gate_profile(profile)
        second = self.workflow.create_gate_profile(profile)
        conflicting = GateProfileRecord(
            **{
                **profile.__dict__,
                "rules": {"minimumClosedSamples": 1},
                "contentHash": "different_hash",
            }
        )

        self.assertEqual(first, second)
        with self.assertRaises(ImmutableRecordConflict):
            self.workflow.create_gate_profile(conflicting)

        duplicate_version = GateProfileRecord(
            **{
                **profile.__dict__,
                "gateProfileId": "gate_backtest_duplicate_v1",
            }
        )
        with self.assertRaises(WorkflowConflict):
            self.workflow.create_gate_profile(duplicate_version)


if __name__ == "__main__":
    unittest.main()
