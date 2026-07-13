from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from alphapilot.evolution.registry.database import connect_registry
from alphapilot.evolution.registry.hashing import stable_hash
from alphapilot.evolution.registry.repositories import RegistryRepository
from alphapilot.evolution.registry.types import StrategyFamilyRecord
from alphapilot.evolution.workflow.bounded_optimization_service import (
    process_bounded_optimization_result,
)
from alphapilot.evolution.workflow.bootstrap import ensure_default_backtest_gate_profile
from alphapilot.evolution.workflow.projection import build_workflow_projection
from alphapilot.evolution.workflow.repository import WorkflowRepository
from alphapilot.evolution.workflow.service import (
    complete_workflow_run,
    queue_workflow_run,
    register_strategy_version,
    start_workflow_run,
)


class BoundedOptimizationIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.connection = connect_registry(self.root / "registry.sqlite")
        self.registry = RegistryRepository(self.connection)
        self.workflow = WorkflowRepository(self.connection)
        payload = {"scope": "bounded_optimizer_test"}
        family = self.registry.create_strategy_family(
            StrategyFamilyRecord(
                strategyFamilyId="family_bounded_optimizer",
                familyKey="bounded_optimizer",
                name="Bounded optimizer fixture",
                status="research_only",
                metadata=payload,
                contentHash=stable_hash(payload),
            )
        )
        gate = ensure_default_backtest_gate_profile(self.workflow)
        self.version = register_strategy_version(
            self.workflow,
            strategy_family_id=family.strategyFamilyId,
            display_name="15m EMA20 回收反弹 ATR1.4",
            source_type="test_fixture",
            definition={
                "signalFamily": "ema_reclaim_long",
                "timeframe": "15m",
                "direction": "long",
                "targetR": 2.0,
            },
            parameters={
                "trend_tolerance": 0.995,
                "reclaim_buffer": 0.003,
                "rsi_min": 42,
                "rsi_max": 72,
                "volume_min": 1.0,
                "stop_atr": 1.4,
                "max_hold": 16,
            },
            initial_gate_profile_id=gate.gateProfileId,
        )

    def tearDown(self) -> None:
        self.connection.close()
        self.temp.cleanup()

    @staticmethod
    def metrics() -> dict:
        split = {
            "tradeCount": 40,
            "profitFactor": 1.0,
            "averageNetR": 0.03,
            "maximumDrawdownR": 7.0,
        }
        stress = {"tradeCount": 40, "averageNetR": 0.01}
        return {
            "bySplit": {
                "development": dict(split),
                "walk_forward": dict(split),
                "holdout": {"profitFactor": 999.0},
                "locked_oos": {"profitFactor": 999.0},
            },
            "costStress": {
                "bySplit": {
                    "development": dict(stress),
                    "walk_forward": dict(stress),
                    "holdout": {"averageNetR": 999.0},
                    "locked_oos": {"averageNetR": 999.0},
                }
            },
        }

    def fail_initial(self, *, category: str = "strategy_performance"):
        initial = self.workflow.get_latest_workflow_run(
            self.version.strategyVersionId,
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

    def test_failure_creates_one_queued_immutable_challenger_and_one_audit(self) -> None:
        failed = self.fail_initial()

        first = process_bounded_optimization_result(
            self.workflow,
            self.registry,
            failed,
        )
        repeated = process_bounded_optimization_result(
            self.workflow,
            self.registry,
            failed,
        )

        self.assertEqual(first.challengerStrategyVersionId, repeated.challengerStrategyVersionId)
        self.assertEqual(self.workflow.count("StrategyVersions"), 2)
        challenger = self.workflow.get_strategy_version(
            str(first.challengerStrategyVersionId)
        )
        assert challenger is not None
        self.assertEqual(challenger.parentStrategyVersionId, self.version.strategyVersionId)
        run = self.workflow.get_latest_workflow_run(
            challenger.strategyVersionId,
            stage="backtest",
        )
        assert run is not None
        self.assertEqual(run.status, "queued")
        self.assertEqual(
            run.gateProfileId,
            self.workflow.get_latest_workflow_run(
                self.version.strategyVersionId,
                stage="backtest",
            ).gateProfileId,
        )
        audits = self.registry.list_audit_events(
            event_type="bounded_auto_optimization",
            entity_type="StrategyVersion",
            entity_id=self.version.strategyVersionId,
        )
        self.assertEqual(len(audits), 1)
        self.assertNotIn("holdout", repr(audits[0].payload))
        self.assertNotIn("locked", repr(audits[0].payload))

        item = next(
            item
            for item in build_workflow_projection(
                self.workflow,
                warehouse_root=self.root / "warehouse",
            )["items"]
            if item["strategyVersionId"] == challenger.strategyVersionId
        )
        self.assertEqual(item["optimizationCampaign"]["attemptNumber"], 1)
        self.assertEqual(item["optimizationCampaign"]["maxAttempts"], 3)

    def test_worker_failure_records_terminal_stop_and_creates_no_version(self) -> None:
        blocked = self.fail_initial(category="worker_operational")

        result = process_bounded_optimization_result(
            self.workflow,
            self.registry,
            blocked,
        )

        self.assertIsNone(result.challengerStrategyVersionId)
        self.assertEqual(result.decision.terminalStatus, "data_evidence_blocked")
        self.assertEqual(self.workflow.count("StrategyVersions"), 1)


if __name__ == "__main__":
    unittest.main()
