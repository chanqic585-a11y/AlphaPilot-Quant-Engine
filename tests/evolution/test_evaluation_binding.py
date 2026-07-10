from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from alphapilot.evolution.data_lineage.snapshot_registry import (
    build_data_snapshot_manifest,
    register_data_snapshot,
)
from alphapilot.evolution.registry.database import connect_registry
from alphapilot.evolution.registry.hashing import stable_hash
from alphapilot.evolution.registry.repositories import (
    ImmutableRecordConflict,
    RegistryRepository,
)
from alphapilot.evolution.strategies.family_registry import ensure_strategy_family
from alphapilot.evolution.workflow.repository import WorkflowRepository
from alphapilot.evolution.workflow.service import register_strategy_version
from alphapilot.evolution.workflow.types import (
    EvaluationBindingRecord,
    GateProfileRecord,
    StrategyDataContractRecord,
)


class EvaluationBindingRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.connection = connect_registry(self.root / "registry.sqlite")
        self.registry = RegistryRepository(self.connection)
        self.workflow = WorkflowRepository(self.connection)
        family = ensure_strategy_family(
            repository=self.registry,
            family_key="evaluation-binding-test",
            name="Evaluation Binding Test",
        )
        rules = {"minimumTargetR": 2.0}
        self.gate = self.workflow.create_gate_profile(
            GateProfileRecord(
                gateProfileId="gate_profile_evaluation_binding_test_v1",
                profileKey="evaluation_binding_test",
                version=1,
                stage="backtest",
                status="active",
                rules=rules,
                contentHash=stable_hash(rules),
            )
        )
        self.version = register_strategy_version(
            self.workflow,
            strategy_family_id=family.strategyFamilyId,
            display_name="Binding Test",
            source_type="test",
            definition={
                "direction": "both",
                "market": "crypto_usdt_swap",
                "timeframe": "4h",
                "targetR": 2.0,
            },
            parameters={"threshold": 1.0},
            initial_gate_profile_id=self.gate.gateProfileId,
        )
        self.run = self.workflow.list_workflow_runs(
            strategy_version_id=self.version.strategyVersionId
        )[0]
        snapshot_file = self.root / "official.parquet"
        snapshot_file.write_bytes(b"official-public-data")
        snapshot_manifest = build_data_snapshot_manifest(
            files=[snapshot_file],
            root=self.root,
            source="okx_public_official",
            exchange="okx",
            market_type="swap",
            timeframe="multi",
            start_time="2020-01-01T00:00:00+00:00",
            end_time="2026-07-11T00:00:00+00:00",
            point_in_time_cutoff="2026-07-11T00:00:00+00:00",
            universe_members=["BTC-USDT-SWAP"],
            metadata={
                "pointInTimeValidated": True,
                "formalResearchEligible": True,
            },
        )
        self.snapshot = register_data_snapshot(snapshot_manifest, self.registry)

    def tearDown(self) -> None:
        self.connection.close()
        self.temp.cleanup()

    def test_contract_and_binding_round_trip_and_are_idempotent(self) -> None:
        contract_payload = {
            "schemaVersion": "strategy_data_contract_v1",
            "strategyVersionId": self.version.strategyVersionId,
            "signalTimeframe": "4h",
            "executionTimeframe": "5m",
            "targetR": 2.0,
        }
        contract_hash = stable_hash(
            contract_payload, prefix="strategy_data_contract"
        )
        contract = StrategyDataContractRecord(
            strategyDataContractId=contract_hash,
            strategyVersionId=self.version.strategyVersionId,
            schemaVersion="strategy_data_contract_v1",
            contract=contract_payload,
            contentHash=contract_hash,
        )
        persisted_contract = self.workflow.create_strategy_data_contract(contract)
        repeated_contract = self.workflow.create_strategy_data_contract(contract)

        binding_payload = {
            "workflowRunId": self.run.workflowRunId,
            "strategyDataContractId": contract.strategyDataContractId,
            "dataSnapshotId": self.snapshot.dataSnapshotId,
            "walkForwardManifestHash": "walk_forward_test",
            "holdoutManifestHash": "holdout_test",
            "lockedOosManifestHash": "locked_oos_test",
            "gateProfileId": self.gate.gateProfileId,
            "runnerVersion": "formal_backtest_v1",
            "costModel": {"feeRate": 0.0005, "slippageRate": 0.0002},
            "evidence": {"evidenceClass": "formal_backtest"},
        }
        binding_hash = stable_hash(binding_payload, prefix="evaluation_binding")
        binding = EvaluationBindingRecord(
            evaluationBindingId=binding_hash,
            workflowRunId=self.run.workflowRunId,
            strategyDataContractId=contract.strategyDataContractId,
            dataSnapshotId=self.snapshot.dataSnapshotId,
            walkForwardManifestHash="walk_forward_test",
            holdoutManifestHash="holdout_test",
            lockedOosManifestHash="locked_oos_test",
            gateProfileId=self.gate.gateProfileId,
            runnerVersion="formal_backtest_v1",
            costModel={"feeRate": 0.0005, "slippageRate": 0.0002},
            evidence={"evidenceClass": "formal_backtest"},
            contentHash=binding_hash,
        )
        persisted_binding = self.workflow.create_evaluation_binding(binding)
        repeated_binding = self.workflow.create_evaluation_binding(binding)

        self.assertEqual(persisted_contract, repeated_contract)
        self.assertEqual(
            self.workflow.get_strategy_data_contract(contract.strategyDataContractId),
            contract,
        )
        self.assertEqual(
            self.workflow.list_strategy_data_contracts(
                strategy_version_id=self.version.strategyVersionId
            ),
            [contract],
        )
        self.assertEqual(persisted_binding, repeated_binding)
        self.assertEqual(
            self.workflow.get_evaluation_binding(binding.evaluationBindingId),
            binding,
        )
        self.assertEqual(
            self.workflow.get_evaluation_binding_for_run(self.run.workflowRunId),
            binding,
        )

    def test_conflicting_contract_hash_is_rejected(self) -> None:
        record = StrategyDataContractRecord(
            strategyDataContractId="strategy_data_contract_conflict",
            strategyVersionId=self.version.strategyVersionId,
            schemaVersion="strategy_data_contract_v1",
            contract={"targetR": 2.0},
            contentHash="hash-one",
        )
        self.workflow.create_strategy_data_contract(record)

        with self.assertRaisesRegex(
            ImmutableRecordConflict, "Immutable record conflict"
        ):
            self.workflow.create_strategy_data_contract(
                StrategyDataContractRecord(
                    strategyDataContractId=record.strategyDataContractId,
                    strategyVersionId=record.strategyVersionId,
                    schemaVersion=record.schemaVersion,
                    contract={"targetR": 3.0},
                    contentHash="hash-two",
                )
            )


if __name__ == "__main__":
    unittest.main()
