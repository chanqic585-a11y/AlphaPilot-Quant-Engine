from __future__ import annotations

import inspect
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from alphapilot.data_foundation.checkpoint import write_json_atomic
from alphapilot.data_foundation.official_history import OfficialCollectionResult
from alphapilot.data_foundation.warehouse import WarehouseLayout
from alphapilot.evolution.evaluation.validation_pack import FormalValidationPack
from alphapilot.evolution.registry.database import connect_registry
from alphapilot.evolution.registry.hashing import stable_hash
from alphapilot.evolution.registry.repositories import RegistryRepository
from alphapilot.evolution.registry.types import DataSnapshotRecord
from alphapilot.evolution.workflow.backtest import BacktestAdapterResult
from alphapilot.evolution.workflow.bootstrap import register_alpha191_observer
from alphapilot.evolution.workflow.dual_layer import (
    DualLayerDependencies,
    _default_dependencies,
    run_dual_layer_backtest_workflow,
)
from alphapilot.evolution.workflow import dual_layer as dual_layer_module
from alphapilot.evolution.workflow.data_contract import derive_strategy_data_contract
from alphapilot.evolution.workflow.repository import WorkflowRepository
from alphapilot.evolution.workflow.service import (
    checkpoint_workflow_run,
    create_challenger_version,
    pause_workflow_run,
    queue_workflow_run,
    retry_backtest_for_data_preparation,
    start_workflow_run,
)


EXPECTED_PHASES = [
    "checking_local_data",
    "research_smoke_running",
    "preparing_official_data",
    "validating_official_data",
    "freezing_data_snapshot",
    "building_validation_manifests",
    "formal_backtest_running",
    "evaluating_gate",
]


class DualLayerWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.connection = connect_registry(self.root / "registry.sqlite")
        self.registry = RegistryRepository(self.connection)
        self.workflow = WorkflowRepository(self.connection)
        self.version = register_alpha191_observer(self.registry, self.workflow)
        initial = self.workflow.get_latest_workflow_run(self.version.strategyVersionId)
        assert initial is not None
        self.run = queue_workflow_run(
            self.workflow, initial.workflowRunId, actor="user"
        )
        self.calls: list[str] = []

    def tearDown(self) -> None:
        self.connection.close()
        self.temp.cleanup()

    def test_default_dependencies_use_offline_local_formal_collector(self) -> None:
        with patch(
            "alphapilot.data_foundation.okx_public.OkxPublicClient",
            side_effect=AssertionError("network client must not be constructed"),
        ), patch(
            "alphapilot.evolution.workflow.dual_layer.LocalFormalHistoryCollector.collect",
            return_value=OfficialCollectionResult(
                status="blocked",
                strategyDataContractId="strategy_data_contract_local_test",
                instrumentCount=0,
                completedPartitionCount=0,
                reusedPartitionCount=0,
                failedPartitionCount=1,
                fundingFileCount=0,
                partitions=(),
                checkpointPath="local-checkpoint.json",
                generatedAt="2026-07-15T00:00:00+00:00",
            ),
        ) as collect:
            dependencies = _default_dependencies()
            contract = derive_strategy_data_contract(self.version, self.workflow)
            result = dependencies.collectOfficialHistory(
                contract,
                WarehouseLayout.from_root(self.root / "warehouse"),
            )

        self.assertEqual(result.status, "blocked")
        collect.assert_called_once()

    def snapshot(self) -> DataSnapshotRecord:
        manifest = {
            "metadata": {
                "formalResearchEligible": True,
                "pointInTimeValidated": True,
                "formalPromotionEligible": True,
            },
            "files": [],
        }
        return self.registry.create_data_snapshot(
            DataSnapshotRecord(
                dataSnapshotId="data_snapshot_dual_test",
                source="okx_public_official",
                exchange="okx",
                marketType="swap",
                timeframe="multi",
                startTime="2020-01-01T00:00:00+00:00",
                endTime="2026-07-11T00:00:00+00:00",
                pointInTimeCutoff="2026-07-11T00:00:00+00:00",
                manifest=manifest,
                contentHash=stable_hash(manifest),
            )
        )

    def dependencies(self, *, collection_status: str = "completed") -> DualLayerDependencies:
        snapshot = self.snapshot()

        def smoke(contract, layout, output_path):
            self.calls.append("smoke")
            return {
                "status": "blocked",
                "implementationValid": False,
                "formalPromotionEligible": False,
                "reportHash": "research_smoke_hash",
                "blockers": ["local_fixture_missing"],
            }

        def collect(contract, layout):
            self.calls.append("collect")
            return OfficialCollectionResult(
                status=collection_status,
                strategyDataContractId=contract.strategyDataContractId,
                instrumentCount=20,
                completedPartitionCount=40 if collection_status == "completed" else 0,
                reusedPartitionCount=0,
                failedPartitionCount=0 if collection_status == "completed" else 1,
                fundingFileCount=20 if collection_status == "completed" else 0,
                partitions=(),
                checkpointPath=str(self.root / "official-checkpoint.json"),
                generatedAt="2026-07-11T00:00:00+00:00",
            )

        def freeze(collection, contract, layout, registry):
            self.calls.append("freeze")
            return snapshot

        def pack(contract, frozen, *, canonical_root, manifest_root):
            self.calls.append("pack")
            return FormalValidationPack(
                strategyDataContractId=contract.strategyDataContractId,
                dataSnapshotId=frozen.dataSnapshotId,
                walkForwardManifestHash="walk_forward_dual_test",
                holdoutManifestHash="holdout_dual_test",
                lockedOosManifestHash="locked_oos_dual_test",
                regimeManifestHash="regime_dual_test",
                costManifestHash="cost_dual_test",
                holdoutSymbols=("SOL-USDT-SWAP",),
                trainingSymbols=("BTC-USDT-SWAP", "ETH-USDT-SWAP"),
                walkForwardFoldCount=3,
                lockedStartIndex=300,
                manifestPaths=(),
            )

        def backtest(strategy_version, binding, frozen, manifest_root):
            self.calls.append("backtest")
            return BacktestAdapterResult(
                metrics={
                    "tradeCount": 120,
                    "profitFactor": 1.4,
                    "averageNetR": 0.18,
                    "maximumDrawdownR": 8.0,
                    "holdoutTradeCount": 20,
                    "lockedTradeCount": 20,
                },
                checks={
                    "costStress": True,
                    "stability": True,
                    "lockedOos": True,
                    "holdout": True,
                    "snapshotBound": True,
                    "targetRFixed": True,
                },
                evidence={"formalReportSha256": "formal_report_sha"},
            )

        return DualLayerDependencies(
            runResearchSmoke=smoke,
            collectOfficialHistory=collect,
            freezeFormalSnapshot=freeze,
            buildValidationPack=pack,
            runFormalBacktest=backtest,
        )

    def test_phase_order_smoke_failure_continues_and_binding_separates_evidence(self) -> None:
        completed = run_dual_layer_backtest_workflow(
            self.workflow,
            self.registry,
            self.run.workflowRunId,
            warehouse_root=self.root / "warehouse",
            output_root=self.root / "output",
            dependencies=self.dependencies(),
        )

        self.assertEqual(completed.status, "passed")
        self.assertEqual(completed.progress["phaseHistory"], EXPECTED_PHASES)
        self.assertEqual(self.calls, ["smoke", "collect", "freeze", "pack", "backtest"])
        binding = self.workflow.get_evaluation_binding_for_run(
            completed.workflowRunId
        )
        self.assertIsNotNone(binding)
        assert binding is not None
        self.assertEqual(binding.dataSnapshotId, "data_snapshot_dual_test")
        self.assertEqual(
            binding.evidence["researchSmoke"]["reportHash"],
            "research_smoke_hash",
        )
        self.assertFalse(
            binding.evidence["researchSmoke"]["formalPromotionEligible"]
        )
        self.assertTrue(binding.evidence["formalEvidenceOnly"])

        calls_before = list(self.calls)
        same = run_dual_layer_backtest_workflow(
            self.workflow,
            self.registry,
            self.run.workflowRunId,
            warehouse_root=self.root / "warehouse",
            output_root=self.root / "output",
            dependencies=self.dependencies(),
        )
        self.assertEqual(same.workflowRunId, completed.workflowRunId)
        self.assertEqual(self.calls, calls_before)

    def test_selection_challenger_persists_only_development_and_walk_forward_metrics(self) -> None:
        challenger = create_challenger_version(
            self.workflow,
            parent_strategy_version_id=self.version.strategyVersionId,
            display_name="Selection challenger",
            source_type="bounded_auto_optimization_selection",
            definition={
                **self.version.definition,
                "optimizationLineage": {
                    "phase": "selection",
                    "rootStrategyVersionId": self.version.strategyVersionId,
                    "attemptNumber": 1,
                    "maxAttempts": 3,
                },
            },
            parameters={**self.version.parameters, "stopLossPct": 0.055},
        )
        challenger_run = self.workflow.get_latest_workflow_run(
            challenger.strategyVersionId,
            stage="backtest",
        )
        assert challenger_run is not None
        queued = queue_workflow_run(
            self.workflow,
            challenger_run.workflowRunId,
            actor="system",
        )
        dependencies = self.dependencies()

        def selection_backtest(*args, **kwargs):
            split = {
                "tradeCount": 40,
                "profitFactor": 1.3,
                "averageNetR": 0.1,
                "maximumDrawdownR": 5.0,
            }
            stress = {"tradeCount": 40, "averageNetR": 0.05}
            return BacktestAdapterResult(
                metrics={
                    "tradeCount": 160,
                    "profitFactor": 0.2,
                    "averageNetR": -5.0,
                    "maximumDrawdownR": 999.0,
                    "bySplit": {
                        "development": dict(split),
                        "walk_forward": dict(split),
                        "holdout": {"profitFactor": 0.0, "averageNetR": -99.0},
                        "locked_oos": {"profitFactor": 0.0, "averageNetR": -99.0},
                    },
                    "costStress": {
                        "bySplit": {
                            "development": dict(stress),
                            "walk_forward": dict(stress),
                            "holdout": {"averageNetR": -99.0},
                            "locked_oos": {"averageNetR": -99.0},
                        }
                    },
                },
                checks={"lockedOos": False, "holdout": False},
                evidence={"formalReportSha256": "selection_fixture"},
            )

        completed = run_dual_layer_backtest_workflow(
            self.workflow,
            self.registry,
            queued.workflowRunId,
            warehouse_root=self.root / "warehouse-selection",
            output_root=self.root / "output-selection",
            dependencies=DualLayerDependencies(
                runResearchSmoke=dependencies.runResearchSmoke,
                collectOfficialHistory=dependencies.collectOfficialHistory,
                freezeFormalSnapshot=dependencies.freezeFormalSnapshot,
                buildValidationPack=dependencies.buildValidationPack,
                runFormalBacktest=selection_backtest,
            ),
        )

        self.assertEqual(completed.status, "passed")
        self.assertEqual(
            set(completed.result["metrics"]["bySplit"]),
            {"development", "walk_forward"},
        )
        self.assertNotIn("holdout", repr(completed.result["metrics"]))
        self.assertNotIn("locked", repr(completed.result["metrics"]))

    def test_data_preparation_can_stop_before_formal_backtest_and_resume(self) -> None:
        dependencies = self.dependencies()

        prepared = run_dual_layer_backtest_workflow(
            self.workflow,
            self.registry,
            self.run.workflowRunId,
            warehouse_root=self.root / "warehouse",
            output_root=self.root / "output",
            dependencies=dependencies,
            stop_after_phase="building_validation_manifests",
        )

        self.assertEqual(prepared.status, "running")
        self.assertEqual(
            prepared.progress["completedPhases"], EXPECTED_PHASES[:6]
        )
        self.assertEqual(self.calls, ["smoke", "collect", "freeze", "pack"])

        completed = run_dual_layer_backtest_workflow(
            self.workflow,
            self.registry,
            self.run.workflowRunId,
            warehouse_root=self.root / "warehouse",
            output_root=self.root / "output",
            dependencies=dependencies,
        )

        self.assertEqual(completed.status, "passed")
        self.assertEqual(self.calls, ["smoke", "collect", "freeze", "pack", "backtest"])

    def test_default_workflow_dependencies_receive_live_pause_status_callback(self) -> None:
        self.assertIn(
            "stop_requested",
            inspect.signature(dual_layer_module._default_dependencies).parameters,
        )

        def build_dependencies(stop_requested):
            base = self.dependencies()

            def collect(contract, layout):
                self.calls.append("collect")
                pause_workflow_run(
                    self.workflow,
                    self.run.workflowRunId,
                    actor="user",
                )
                self.assertTrue(stop_requested())
                return OfficialCollectionResult(
                    status="paused",
                    strategyDataContractId=contract.strategyDataContractId,
                    instrumentCount=2,
                    completedPartitionCount=0,
                    reusedPartitionCount=0,
                    failedPartitionCount=0,
                    fundingFileCount=0,
                    partitions=(),
                    checkpointPath=str(self.root / "official-checkpoint.json"),
                    generatedAt="2026-07-12T00:00:00+00:00",
                )

            return DualLayerDependencies(
                runResearchSmoke=base.runResearchSmoke,
                collectOfficialHistory=collect,
                freezeFormalSnapshot=base.freezeFormalSnapshot,
                buildValidationPack=base.buildValidationPack,
                runFormalBacktest=base.runFormalBacktest,
                marketData=base.marketData,
                codeCommit=base.codeCommit,
            )

        with patch.object(
            dual_layer_module,
            "_default_dependencies",
            side_effect=build_dependencies,
        ):
            paused = run_dual_layer_backtest_workflow(
                self.workflow,
                self.registry,
                self.run.workflowRunId,
                warehouse_root=self.root / "warehouse",
                output_root=self.root / "output",
            )

        self.assertEqual(paused.status, "paused")
        self.assertNotIn(
            "preparing_official_data",
            paused.progress["completedPhases"],
        )

        queue_workflow_run(
            self.workflow,
            paused.workflowRunId,
            actor="user",
        )
        resumed = run_dual_layer_backtest_workflow(
            self.workflow,
            self.registry,
            paused.workflowRunId,
            warehouse_root=self.root / "warehouse",
            output_root=self.root / "output",
            dependencies=self.dependencies(),
        )

        self.assertEqual(resumed.status, "passed")
        self.assertEqual(self.calls.count("collect"), 2)

    def test_official_data_failure_blocks_and_data_retry_preserves_attempt(self) -> None:
        blocked = run_dual_layer_backtest_workflow(
            self.workflow,
            self.registry,
            self.run.workflowRunId,
            warehouse_root=self.root / "warehouse",
            output_root=self.root / "output",
            dependencies=self.dependencies(collection_status="blocked"),
        )

        self.assertEqual(blocked.status, "blocked")
        self.assertIn("formal_collection_not_complete", blocked.result["blocker"])
        self.assertEqual(self.calls, ["smoke", "collect"])
        retry = retry_backtest_for_data_preparation(
            self.workflow, blocked.workflowRunId, actor="user"
        )
        same_retry = retry_backtest_for_data_preparation(
            self.workflow, blocked.workflowRunId, actor="user"
        )

        self.assertEqual(retry, same_retry)
        self.assertEqual(retry.strategyVersionId, blocked.strategyVersionId)
        self.assertEqual(retry.attemptNumber, 2)
        self.assertEqual(retry.status, "queued")
        original = self.workflow.get_workflow_run(blocked.workflowRunId)
        assert original is not None
        self.assertEqual(original.status, "cancelled")
        self.assertEqual(len(self.workflow.list_workflow_runs(
            strategy_version_id=blocked.strategyVersionId
        )), 2)

    def test_running_recovery_skips_checksum_persisted_completed_phases(self) -> None:
        running = start_workflow_run(
            self.workflow, self.run.workflowRunId, actor="worker"
        )
        contract = derive_strategy_data_contract(self.version, self.workflow)
        run_root = self.root / "output" / running.workflowRunId
        smoke_path = run_root / "research-smoke.json"
        collection_path = run_root / "official-collection.json"
        write_json_atomic(
            smoke_path,
            {
                "status": "blocked",
                "implementationValid": False,
                "formalPromotionEligible": False,
                "reportHash": "persisted_smoke_hash",
                "blockers": [],
            },
        )
        collection = OfficialCollectionResult(
            status="completed",
            strategyDataContractId=contract.strategyDataContractId,
            instrumentCount=20,
            completedPartitionCount=40,
            reusedPartitionCount=40,
            failedPartitionCount=0,
            fundingFileCount=20,
            partitions=(),
            checkpointPath=str(self.root / "official-checkpoint.json"),
            generatedAt="2026-07-11T00:00:00+00:00",
        )
        write_json_atomic(collection_path, collection.to_dict())
        checkpoint_workflow_run(
            self.workflow,
            running.workflowRunId,
            progress={
                "phase": "preparing_official_data",
                "phaseHistory": EXPECTED_PHASES[:3],
                "completedPhases": EXPECTED_PHASES[:3],
                "artifacts": {
                    "strategyDataContractId": contract.strategyDataContractId,
                    "researchSmokePath": str(smoke_path),
                    "officialCollectionPath": str(collection_path),
                },
            },
            actor="worker",
        )
        dependencies = self.dependencies()
        completed = run_dual_layer_backtest_workflow(
            self.workflow,
            self.registry,
            running.workflowRunId,
            warehouse_root=self.root / "warehouse",
            output_root=self.root / "output",
            dependencies=dependencies,
        )

        self.assertEqual(completed.status, "passed")
        self.assertEqual(self.calls, ["freeze", "pack", "backtest"])
        self.assertEqual(completed.progress["phaseHistory"], EXPECTED_PHASES)

    def test_running_recovery_recollects_legacy_paused_completed_phase(self) -> None:
        running = start_workflow_run(
            self.workflow, self.run.workflowRunId, actor="worker"
        )
        contract = derive_strategy_data_contract(self.version, self.workflow)
        run_root = self.root / "output" / running.workflowRunId
        smoke_path = run_root / "research-smoke.json"
        collection_path = run_root / "official-collection.json"
        write_json_atomic(
            smoke_path,
            {
                "status": "blocked",
                "implementationValid": False,
                "formalPromotionEligible": False,
                "reportHash": "persisted_smoke_hash",
                "blockers": [],
            },
        )
        paused_collection = OfficialCollectionResult(
            status="paused",
            strategyDataContractId=contract.strategyDataContractId,
            instrumentCount=20,
            completedPartitionCount=12,
            reusedPartitionCount=12,
            failedPartitionCount=0,
            fundingFileCount=0,
            partitions=(),
            checkpointPath=str(self.root / "official-checkpoint.json"),
            generatedAt="2026-07-12T00:00:00+00:00",
        )
        write_json_atomic(collection_path, paused_collection.to_dict())
        checkpoint_workflow_run(
            self.workflow,
            running.workflowRunId,
            progress={
                "phase": "preparing_official_data",
                "phaseHistory": EXPECTED_PHASES[:3],
                "completedPhases": EXPECTED_PHASES[:3],
                "artifacts": {
                    "strategyDataContractId": contract.strategyDataContractId,
                    "researchSmokePath": str(smoke_path),
                    "officialCollectionPath": str(collection_path),
                },
            },
            actor="worker",
        )

        completed = run_dual_layer_backtest_workflow(
            self.workflow,
            self.registry,
            running.workflowRunId,
            warehouse_root=self.root / "warehouse",
            output_root=self.root / "output",
            dependencies=self.dependencies(),
        )

        self.assertEqual(completed.status, "passed")
        self.assertEqual(self.calls, ["collect", "freeze", "pack", "backtest"])


if __name__ == "__main__":
    unittest.main()
