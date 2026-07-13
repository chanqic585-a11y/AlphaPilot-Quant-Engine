from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from alphapilot.evolution.registry.database import connect_registry
from alphapilot.evolution.registry.hashing import stable_hash
from alphapilot.evolution.registry.repositories import RegistryRepository
from alphapilot.evolution.registry.types import StrategyFamilyRecord
from alphapilot.evolution.workflow.bootstrap import ensure_default_backtest_gate_profile
from alphapilot.evolution.workflow.projection import build_workflow_projection
from alphapilot.evolution.workflow.repository import WorkflowRepository
from alphapilot.evolution.workflow.service import (
    complete_workflow_run,
    queue_workflow_run,
    register_strategy_version,
    start_workflow_run,
)
from alphapilot.evolution.workflow.structural_redesign_service import (
    process_structural_redesign_result,
    recover_terminal_structural_redesigns,
)


class StructuralRedesignIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.connection = connect_registry(self.root / "registry.sqlite")
        self.registry = RegistryRepository(self.connection)
        self.workflow = WorkflowRepository(self.connection)
        payload = {"scope": "structural_redesign_integration_test"}
        self.family = self.registry.create_strategy_family(
            StrategyFamilyRecord(
                strategyFamilyId="family_structural_redesign",
                familyKey="structural_redesign",
                name="Structural redesign fixture",
                status="research_only",
                metadata=payload,
                contentHash=stable_hash(payload),
            )
        )
        self.gate = ensure_default_backtest_gate_profile(self.workflow)

    def tearDown(self) -> None:
        self.connection.close()
        self.temp.cleanup()

    @staticmethod
    def metrics() -> dict:
        weak = {
            "tradeCount": 100,
            "profitFactor": 0.5,
            "averageNetR": -0.35,
            "maximumDrawdownR": 30.0,
        }
        stressed = {"tradeCount": 100, "averageNetR": -0.5}
        return {
            "bySplit": {
                "development": dict(weak),
                "walk_forward": dict(weak),
                "holdout": {"profitFactor": 999.0},
                "locked_oos": {"profitFactor": 999.0},
            },
            "costStress": {
                "bySplit": {
                    "development": dict(stressed),
                    "walk_forward": dict(stressed),
                    "holdout": {"averageNetR": 999.0},
                    "locked_oos": {"averageNetR": 999.0},
                }
            },
        }

    def register_version(self, *, generation: int = 0):
        definition = {
            "signalEngine": "short_cycle_v1",
            "signalFamily": "ema_reclaim_long",
            "timeframe": "15m",
            "direction": "long",
            "targetR": 2.0,
            "exitPolicy": "two_r_half_atr_runner_v1",
            "researchOnly": True,
            "executionEnabled": False,
        }
        if generation:
            definition["structuralRedesignLineage"] = {
                "schemaVersion": "structural_redesign_lineage_v1",
                "campaignId": "campaign_fixture",
                "rootStrategyVersionId": "root_fixture",
                "parentStrategyVersionId": "parent_fixture",
                "generation": generation,
                "maxGenerations": 3,
                "grammarVersion": "structural_strategy_grammar_v1",
                "recipeId": "failed_reclaim_rejection_v1",
                "failureEvidenceHash": "failure_fixture",
            }
        return register_strategy_version(
            self.workflow,
            strategy_family_id=self.family.strategyFamilyId,
            display_name=f"15m structural fixture generation {generation}",
            source_type="test_fixture",
            definition=definition,
            parameters={
                "trend_tolerance": 0.995,
                "reclaim_buffer": 0.003,
                "rsi_min": 42,
                "rsi_max": 72,
                "volume_min": 1.0,
                "stop_atr": 1.4,
                "max_hold": 16,
            },
            initial_gate_profile_id=self.gate.gateProfileId,
        )

    def fail_version(self, version, *, category: str = "strategy_performance"):
        initial = self.workflow.get_latest_workflow_run(
            version.strategyVersionId,
            stage="backtest",
        )
        assert initial is not None
        queued = queue_workflow_run(self.workflow, initial.workflowRunId, actor="user")
        running = start_workflow_run(self.workflow, queued.workflowRunId, actor="worker")
        return complete_workflow_run(
            self.workflow,
            running.workflowRunId,
            status="failed" if category == "strategy_performance" else "blocked",
            actor="worker",
            result={"metrics": self.metrics(), "checks": {}},
            evidence={"fixture": True},
            failure={
                "category": category,
                "summary": "fixture failure",
                "retryDisposition": (
                    "new_version_required"
                    if category == "strategy_performance"
                    else "same_version_retry"
                ),
                "metrics": {},
                "suggestions": [],
            },
        )

    def test_structural_failure_atomically_archives_parent_and_queues_child(self) -> None:
        parent = self.register_version()
        failed = self.fail_version(parent)

        result = process_structural_redesign_result(
            self.workflow,
            self.registry,
            failed,
        )

        self.assertEqual(result.action, "create_child")
        self.assertIsNotNone(result.childStrategyVersionId)
        self.assertIsNotNone(result.childWorkflowRunId)
        stored_parent = self.workflow.get_strategy_version(parent.strategyVersionId)
        assert stored_parent is not None
        self.assertEqual(stored_parent.status, "archived")
        child = self.workflow.get_strategy_version(str(result.childStrategyVersionId))
        assert child is not None
        self.assertEqual(child.parentStrategyVersionId, parent.strategyVersionId)
        self.assertEqual(child.status, "active")
        self.assertGreaterEqual(float(child.definition["targetR"]), 2.0)
        self.assertTrue(child.definition["researchOnly"])
        self.assertFalse(child.definition["executionEnabled"])
        child_run = self.workflow.get_workflow_run(str(result.childWorkflowRunId))
        assert child_run is not None
        self.assertEqual(child_run.status, "queued")
        self.assertEqual(child_run.gateProfileId, failed.gateProfileId)
        self.assertEqual(len(self.workflow.list_stage_events(strategy_version_id=child.strategyVersionId)), 1)
        self.assertEqual(len(self.workflow.list_stage_events(strategy_version_id=parent.strategyVersionId)), 5)
        created = self.registry.list_audit_events(
            event_type="structural_redesign_candidate_created",
            entity_type="StrategyVersion",
            entity_id=parent.strategyVersionId,
        )
        archived = self.registry.list_audit_events(
            event_type="structural_redesign_parent_archived",
            entity_type="StrategyVersion",
            entity_id=parent.strategyVersionId,
        )
        self.assertEqual(len(created), 1)
        self.assertEqual(len(archived), 1)
        self.assertNotIn("holdout", repr(created[0].payload))
        self.assertNotIn("locked", repr(created[0].payload))
        projected = next(
            item
            for item in build_workflow_projection(self.workflow)["items"]
            if item["strategyVersionId"] == child.strategyVersionId
        )
        campaign = projected["structuralRedesignCampaign"]
        self.assertEqual(campaign["generation"], 1)
        self.assertEqual(campaign["maxGenerations"], 3)
        self.assertEqual(campaign["parentStatus"], "archived")
        self.assertEqual(campaign["childStatus"], "queued")
        self.assertEqual(campaign["childWorkflowRunId"], child_run.workflowRunId)
        self.assertTrue(campaign["recipeSummary"])
        self.assertNotIn("holdout", repr(campaign))
        self.assertNotIn("locked", repr(campaign))

    def test_repeated_processing_returns_same_child_without_duplicate_records(self) -> None:
        parent = self.register_version()
        failed = self.fail_version(parent)

        first = process_structural_redesign_result(self.workflow, self.registry, failed)
        repeated = process_structural_redesign_result(self.workflow, self.registry, failed)

        self.assertEqual(first.childStrategyVersionId, repeated.childStrategyVersionId)
        self.assertEqual(first.childWorkflowRunId, repeated.childWorkflowRunId)
        self.assertEqual(self.workflow.count("StrategyVersions"), 2)
        self.assertEqual(self.workflow.count("WorkflowRuns"), 2)
        self.assertEqual(
            len(
                self.registry.list_audit_events(
                    entity_type="StrategyVersion",
                    entity_id=parent.strategyVersionId,
                )
            ),
            2,
        )

    def test_non_performance_failure_creates_nothing_and_keeps_parent_active(self) -> None:
        parent = self.register_version()
        blocked = self.fail_version(parent, category="worker_operational")

        result = process_structural_redesign_result(
            self.workflow,
            self.registry,
            blocked,
        )

        self.assertEqual(result.action, "stop")
        self.assertEqual(result.reasonCode, "non_performance_failure")
        self.assertIsNone(result.childStrategyVersionId)
        stored_parent = self.workflow.get_strategy_version(parent.strategyVersionId)
        assert stored_parent is not None
        self.assertEqual(stored_parent.status, "active")
        self.assertEqual(self.workflow.count("StrategyVersions"), 1)
        self.assertEqual(self.connection.execute("SELECT COUNT(*) FROM AuditEvents").fetchone()[0], 0)

    def test_projection_keeps_structural_campaign_empty_without_lineage_or_audit(self) -> None:
        version = self.register_version()

        projected = next(
            item
            for item in build_workflow_projection(self.workflow)["items"]
            if item["strategyVersionId"] == version.strategyVersionId
        )

        campaign = projected["structuralRedesignCampaign"]
        self.assertFalse(campaign["supported"])
        self.assertIsNone(campaign["campaignId"])
        self.assertEqual(campaign["generation"], 0)
        self.assertIsNone(campaign["parentStrategyVersionId"])
        self.assertIsNone(campaign["parentStatus"])
        self.assertIsNone(campaign["childStrategyVersionId"])
        self.assertIsNone(campaign["childStatus"])

    def test_mid_transaction_failure_rolls_back_child_audits_and_parent_archive(self) -> None:
        parent = self.register_version()
        failed = self.fail_version(parent)
        original = self.workflow._insert_audit_event_record
        calls = 0

        def fail_second_audit(record):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError("injected_audit_failure")
            return original(record)

        with mock.patch.object(
            self.workflow,
            "_insert_audit_event_record",
            side_effect=fail_second_audit,
        ):
            with self.assertRaisesRegex(RuntimeError, "injected_audit_failure"):
                process_structural_redesign_result(
                    self.workflow,
                    self.registry,
                    failed,
                )

        stored_parent = self.workflow.get_strategy_version(parent.strategyVersionId)
        assert stored_parent is not None
        self.assertEqual(stored_parent.status, "active")
        self.assertEqual(self.workflow.count("StrategyVersions"), 1)
        self.assertEqual(self.workflow.count("WorkflowRuns"), 1)
        self.assertEqual(self.connection.execute("SELECT COUNT(*) FROM AuditEvents").fetchone()[0], 0)

    def test_generation_budget_archives_terminal_weak_parent_and_records_stop(self) -> None:
        parent = self.register_version(generation=3)
        failed = self.fail_version(parent)

        result = process_structural_redesign_result(
            self.workflow,
            self.registry,
            failed,
        )

        self.assertEqual(result.action, "stop")
        self.assertEqual(result.reasonCode, "structural_generation_budget_exhausted")
        self.assertIsNone(result.childStrategyVersionId)
        stored_parent = self.workflow.get_strategy_version(parent.strategyVersionId)
        assert stored_parent is not None
        self.assertEqual(stored_parent.status, "archived")
        audits = self.registry.list_audit_events(
            event_type="structural_redesign_stopped",
            entity_type="StrategyVersion",
            entity_id=parent.strategyVersionId,
        )
        self.assertEqual(len(audits), 1)
        self.assertEqual(audits[0].payload["reasonCode"], result.reasonCode)

    def test_recovery_backs_up_before_mutation_and_is_idempotent(self) -> None:
        parent = self.register_version()
        self.fail_version(parent)

        first = recover_terminal_structural_redesigns(
            self.workflow,
            self.registry,
            registry_path=self.root / "registry.sqlite",
            strategy_version_ids=[parent.strategyVersionId],
        )
        repeated = recover_terminal_structural_redesigns(
            self.workflow,
            self.registry,
            registry_path=self.root / "registry.sqlite",
            strategy_version_ids=[parent.strategyVersionId],
        )

        self.assertEqual(first.reviewedCount, 1)
        self.assertEqual(first.createdChildCount, 1)
        self.assertEqual(len(first.childWorkflowRunIds), 1)
        self.assertIsNotNone(first.backupPath)
        self.assertTrue(Path(str(first.backupPath)).is_file())
        backup_connection = connect_registry(Path(str(first.backupPath)))
        try:
            backed_up_parent = WorkflowRepository(
                backup_connection
            ).get_strategy_version(parent.strategyVersionId)
            assert backed_up_parent is not None
            self.assertEqual(backed_up_parent.status, "active")
        finally:
            backup_connection.close()
        self.assertEqual(repeated.reviewedCount, 0)
        self.assertEqual(repeated.alreadyReviewedCount, 1)
        self.assertIsNone(repeated.backupPath)
        self.assertEqual(self.workflow.count("StrategyVersions"), 2)

    def test_recovery_ignores_data_or_worker_failures_without_backup(self) -> None:
        parent = self.register_version()
        self.fail_version(parent, category="worker_operational")

        result = recover_terminal_structural_redesigns(
            self.workflow,
            self.registry,
            registry_path=self.root / "registry.sqlite",
            strategy_version_ids=[parent.strategyVersionId],
        )

        self.assertEqual(result.reviewedCount, 0)
        self.assertEqual(result.createdChildCount, 0)
        self.assertIsNone(result.backupPath)
        stored_parent = self.workflow.get_strategy_version(parent.strategyVersionId)
        assert stored_parent is not None
        self.assertEqual(stored_parent.status, "active")

    def test_recovery_ignores_previously_archived_structural_failure(self) -> None:
        parent = self.register_version()
        self.fail_version(parent)
        with self.connection:
            self.connection.execute(
                "UPDATE StrategyVersions SET status = 'archived' WHERE strategyVersionId = ?",
                (parent.strategyVersionId,),
            )

        result = recover_terminal_structural_redesigns(
            self.workflow,
            self.registry,
            registry_path=self.root / "registry.sqlite",
            strategy_version_ids=[parent.strategyVersionId],
        )

        self.assertEqual(result.reviewedCount, 0)
        self.assertEqual(result.createdChildCount, 0)
        self.assertEqual(result.stoppedCount, 0)
        self.assertIsNone(result.backupPath)
        self.assertEqual(self.workflow.count("StrategyVersions"), 1)
        stored_parent = self.workflow.get_strategy_version(parent.strategyVersionId)
        assert stored_parent is not None
        self.assertEqual(stored_parent.status, "archived")


if __name__ == "__main__":
    unittest.main()
