from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

import pandas as pd

from alphapilot.evolution.evaluation.validation_pack import FormalValidationPack
from alphapilot.evolution.forward.release import create_workflow_forward_release
from alphapilot.evolution.registry.database import connect_registry
from alphapilot.evolution.registry.hashing import stable_hash
from alphapilot.evolution.registry.repositories import RegistryRepository
from alphapilot.evolution.registry.types import (
    DataSnapshotRecord,
    StrategyFamilyRecord,
)
from alphapilot.evolution.risk_profiles import register_default_risk_profiles
from alphapilot.evolution.workflow.data_contract import derive_strategy_data_contract
from alphapilot.evolution.workflow.evaluation_binding import (
    create_formal_evaluation_binding,
)
from alphapilot.evolution.workflow.local_forward_bridge import (
    start_local_forward_after_pass,
)
from alphapilot.evolution.workflow.repository import WorkflowRepository
from alphapilot.evolution.workflow.service import (
    complete_workflow_run,
    queue_workflow_run,
    register_strategy_version,
    start_workflow_run,
)
from alphapilot.short_cycle.workflow_candidates import (
    short_cycle_workflow_candidates,
)


class _PublicMarket:
    def completed_candles(
        self, instrument_id: str, timeframe: str, *, limit: int = 300
    ) -> pd.DataFrame:
        count = 80
        return pd.DataFrame(
            {
                "timestamp_ms": [1_700_000_000_000 + index * 14_400_000 for index in range(count)],
                "open": [100 + index * 0.1 for index in range(count)],
                "high": [101 + index * 0.1 for index in range(count)],
                "low": [99 + index * 0.1 for index in range(count)],
                "close": [100.5 + index * 0.1 for index in range(count)],
                "volume": [1000.0] * count,
            }
        )


class WorkflowLocalForwardBridgeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.connection = connect_registry(self.root / "registry.sqlite")
        self.registry = RegistryRepository(self.connection)
        self.workflow = WorkflowRepository(self.connection)
        family_payload = {"scope": "formal_workflow_forward"}
        self.family = self.registry.create_strategy_family(
            StrategyFamilyRecord(
                strategyFamilyId="family_formal_workflow_forward",
                familyKey="formal_workflow_forward",
                name="Formal workflow forward",
                status="research_only",
                metadata=family_payload,
                contentHash=stable_hash(family_payload),
            )
        )
        from alphapilot.evolution.workflow.bootstrap import (
            ensure_default_backtest_gate_profile,
        )

        self.gate = ensure_default_backtest_gate_profile(self.workflow)
        self.version = register_strategy_version(
            self.workflow,
            strategy_family_id=self.family.strategyFamilyId,
            display_name="Formal forward fixture",
            source_type="test",
            definition={
                "schemaVersion": "strategy_workflow_definition_v1",
                "direction": "long",
                "market": "crypto_usdt_swap",
                "timeframe": "4h",
                "targetR": 2.0,
                "researchOnly": True,
                "forwardSignalPolicy": {
                    "direction": "long",
                    "rules": [
                        {"factorId": "rsi_14", "operator": "gte", "threshold": 30}
                    ],
                },
                "backtest": {
                    "adapterId": "alpha191_crypto_subset_v13_5_23",
                    "costModel": {"feeRate": 0.0005, "slippageRate": 0.0002},
                },
            },
            parameters={
                "overlayId": "a191_long_capitulation_reclaim_v01",
                "stopLossPct": 0.05,
                "horizonBars": 24,
            },
            initial_gate_profile_id=self.gate.gateProfileId,
        )
        initial = self.workflow.get_latest_workflow_run(self.version.strategyVersionId)
        assert initial is not None
        queued = queue_workflow_run(self.workflow, initial.workflowRunId, actor="user")
        running = start_workflow_run(self.workflow, queued.workflowRunId, actor="worker")
        self.contract = derive_strategy_data_contract(self.version, self.workflow)
        manifest = {
            "universeMembers": ["BTC-USDT-SWAP", "ETH-USDT-SWAP"],
            "metadata": {
                "formalResearchEligible": True,
                "formalPromotionEligible": True,
                "pointInTimeValidated": True,
            },
            "files": [],
        }
        self.snapshot = self.registry.create_data_snapshot(
            DataSnapshotRecord(
                dataSnapshotId="snapshot_formal_forward",
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
        pack = FormalValidationPack(
            strategyDataContractId=self.contract.strategyDataContractId,
            dataSnapshotId=self.snapshot.dataSnapshotId,
            walkForwardManifestHash="walk_forward_forward_test",
            holdoutManifestHash="holdout_forward_test",
            lockedOosManifestHash="locked_forward_test",
            regimeManifestHash="regime_forward_test",
            costManifestHash="cost_forward_test",
            holdoutSymbols=("ETH-USDT-SWAP",),
            trainingSymbols=("BTC-USDT-SWAP",),
            walkForwardFoldCount=3,
            lockedStartIndex=300,
            manifestPaths=(),
        )
        self.binding = create_formal_evaluation_binding(
            self.workflow,
            run=running,
            contract=self.contract,
            snapshot=self.snapshot,
            validation_pack=pack,
            canonical_root=str(self.root / "canonical"),
            research_smoke={
                "status": "blocked",
                "formalPromotionEligible": False,
                "reportHash": "smoke_hash",
                "blockers": [],
            },
        )
        evidence = {
            "evaluationBindingId": self.binding.evaluationBindingId,
            "strategyDataContractId": self.contract.strategyDataContractId,
            "dataSnapshotId": self.snapshot.dataSnapshotId,
            "walkForwardManifestHash": self.binding.walkForwardManifestHash,
            "holdoutManifestHash": self.binding.holdoutManifestHash,
            "lockedOosManifestHash": self.binding.lockedOosManifestHash,
            "regimeManifestHash": self.binding.evidence["regimeManifestHash"],
            "costManifestHash": self.binding.evidence["costManifestHash"],
            "formalEvidenceOnly": True,
        }
        self.backtest_run = complete_workflow_run(
            self.workflow,
            running.workflowRunId,
            status="passed",
            actor="worker",
            result={
                "metrics": {"tradeCount": 100, "profitFactor": 1.4},
                "checks": {"allFormalGates": True},
            },
            evidence=evidence,
        )

    def tearDown(self) -> None:
        self.connection.close()
        self.temp.cleanup()

    def test_pass_starts_public_only_local_forward_and_no_demo_or_live(self) -> None:
        local_run = start_local_forward_after_pass(
            self.workflow,
            self.registry,
            self.version,
            self.backtest_run,
            self.binding,
            code_commit="test-commit",
            market_data=_PublicMarket(),
        )
        same = start_local_forward_after_pass(
            self.workflow,
            self.registry,
            self.version,
            self.backtest_run,
            self.binding,
            code_commit="test-commit",
            market_data=_PublicMarket(),
        )

        self.assertEqual(local_run, same)
        self.assertEqual(local_run.stage, "local_forward")
        self.assertEqual(local_run.status, "running")
        self.assertIn("forwardReleaseId", local_run.result)
        self.assertIn("forwardSessionId", local_run.result)
        release = self.registry.get_forward_release(local_run.result["forwardReleaseId"])
        assert release is not None
        self.assertTrue(release.release["virtualAccountOnly"])
        self.assertFalse(release.release["createsOrders"])
        self.assertFalse(release.release["demoExecutionAllowed"])
        self.assertFalse(release.release["liveExecutionAllowed"])
        self.assertEqual(self.registry.list_demo_releases(), [])
        self.assertEqual(self.registry.list_live_releases(), [])

    def test_strict_formal_promotion_rejections(self) -> None:
        with self.subTest("failed gate"):
            with self.assertRaisesRegex(ValueError, "passed backtest"):
                start_local_forward_after_pass(
                    self.workflow,
                    self.registry,
                    self.version,
                    replace(self.backtest_run, status="failed"),
                    self.binding,
                    code_commit="test-commit",
                    market_data=_PublicMarket(),
                )
        with self.subTest("smoke evidence"):
            smoke_binding = replace(
                self.binding,
                evidence={**self.binding.evidence, "evidenceClass": "research_smoke"},
            )
            with self.assertRaisesRegex(ValueError, "formal workflow evidence"):
                start_local_forward_after_pass(
                    self.workflow,
                    self.registry,
                    self.version,
                    self.backtest_run,
                    smoke_binding,
                    code_commit="test-commit",
                    market_data=_PublicMarket(),
                )
        with self.subTest("target below 2R"):
            low_r = replace(
                self.version,
                definition={**self.version.definition, "targetR": 1.5},
            )
            with self.assertRaisesRegex(ValueError, "targetR"):
                start_local_forward_after_pass(
                    self.workflow,
                    self.registry,
                    low_r,
                    self.backtest_run,
                    self.binding,
                    code_commit="test-commit",
                    market_data=_PublicMarket(),
                )
        with self.subTest("hash mismatch"):
            bad_result = replace(
                self.backtest_run,
                result={
                    **self.backtest_run.result,
                    "evidence": {
                        **self.backtest_run.result["evidence"],
                        "dataSnapshotId": "wrong_snapshot",
                    },
                },
            )
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                start_local_forward_after_pass(
                    self.workflow,
                    self.registry,
                    self.version,
                    bad_result,
                    self.binding,
                    code_commit="test-commit",
                    market_data=_PublicMarket(),
                )
        with self.subTest("missing signal policy"):
            no_policy = replace(
                self.version,
                definition={
                    key: value
                    for key, value in self.version.definition.items()
                    if key != "forwardSignalPolicy"
                },
            )
            with self.assertRaisesRegex(ValueError, "signal policy"):
                start_local_forward_after_pass(
                    self.workflow,
                    self.registry,
                    no_policy,
                    self.backtest_run,
                    self.binding,
                    code_commit="test-commit",
                    market_data=_PublicMarket(),
                )
        with self.subTest("non public market"):
            private_market = replace(
                self.version,
                definition={**self.version.definition, "marketDataAccess": "private"},
            )
            with self.assertRaisesRegex(ValueError, "public-only"):
                start_local_forward_after_pass(
                    self.workflow,
                    self.registry,
                    private_market,
                    self.backtest_run,
                    self.binding,
                    code_commit="test-commit",
                    market_data=_PublicMarket(),
                )

    def test_release_rejects_wrong_risk_environment(self) -> None:
        local_run = start_local_forward_after_pass(
            self.workflow,
            self.registry,
            self.version,
            self.backtest_run,
            self.binding,
            code_commit="test-commit",
            market_data=_PublicMarket(),
        )
        candidate = self.registry.get_strategy_candidate(
            self.registry.get_forward_release(
                local_run.result["forwardReleaseId"]
            ).strategyCandidateId
        )
        assert candidate is not None
        wrong_profile = register_default_risk_profiles(self.registry)["okx_demo"]
        with self.assertRaisesRegex(ValueError, "local_forward RiskProfile"):
            create_workflow_forward_release(
                strategy_version=self.version,
                strategy_candidate=candidate,
                evaluation_binding=self.binding,
                backtest_result={"status": "passed", **self.backtest_run.result},
                repository=self.registry,
                code_commit="test-commit",
                risk_profile=wrong_profile,
            )

    def test_short_cycle_policy_creates_public_virtual_forward_release(self) -> None:
        item = short_cycle_workflow_candidates()[0]
        version = register_strategy_version(
            self.workflow,
            strategy_family_id=self.family.strategyFamilyId,
            display_name=item.displayName,
            source_type="short_cycle_candidate_pack_v13_27_3",
            definition=item.definition(),
            parameters=item.parameters,
            initial_gate_profile_id=self.gate.gateProfileId,
        )
        initial = self.workflow.get_latest_workflow_run(version.strategyVersionId)
        assert initial is not None
        running = start_workflow_run(
            self.workflow,
            queue_workflow_run(
                self.workflow, initial.workflowRunId, actor="user"
            ).workflowRunId,
            actor="worker",
        )
        contract = derive_strategy_data_contract(version, self.workflow)
        pack = FormalValidationPack(
            strategyDataContractId=contract.strategyDataContractId,
            dataSnapshotId=self.snapshot.dataSnapshotId,
            walkForwardManifestHash="walk_forward_short_cycle",
            holdoutManifestHash="holdout_short_cycle",
            lockedOosManifestHash="locked_short_cycle",
            regimeManifestHash="regime_short_cycle",
            costManifestHash="cost_short_cycle",
            holdoutSymbols=("ETH-USDT-SWAP",),
            trainingSymbols=("BTC-USDT-SWAP",),
            walkForwardFoldCount=3,
            lockedStartIndex=300,
            manifestPaths=(),
        )
        binding = create_formal_evaluation_binding(
            self.workflow,
            run=running,
            contract=contract,
            snapshot=self.snapshot,
            validation_pack=pack,
            canonical_root=str(self.root / "canonical"),
            research_smoke={
                "status": "blocked",
                "formalPromotionEligible": False,
                "reportHash": "smoke_hash_short_cycle",
                "blockers": [],
            },
        )
        evidence = {
            "evaluationBindingId": binding.evaluationBindingId,
            "strategyDataContractId": contract.strategyDataContractId,
            "dataSnapshotId": self.snapshot.dataSnapshotId,
            "walkForwardManifestHash": binding.walkForwardManifestHash,
            "holdoutManifestHash": binding.holdoutManifestHash,
            "lockedOosManifestHash": binding.lockedOosManifestHash,
            "regimeManifestHash": binding.evidence["regimeManifestHash"],
            "costManifestHash": binding.evidence["costManifestHash"],
            "formalEvidenceOnly": True,
        }
        passed = complete_workflow_run(
            self.workflow,
            running.workflowRunId,
            status="passed",
            actor="worker",
            result={
                "metrics": {"tradeCount": 100, "profitFactor": 1.4},
                "checks": {"allFormalGates": True},
            },
            evidence=evidence,
        )

        local_run = start_local_forward_after_pass(
            self.workflow,
            self.registry,
            version,
            passed,
            binding,
            code_commit="test-short-cycle",
            market_data=_PublicMarket(),
        )

        release = self.registry.get_forward_release(local_run.result["forwardReleaseId"])
        assert release is not None
        candidate = self.registry.get_strategy_candidate(release.strategyCandidateId)
        assert candidate is not None
        self.assertEqual(
            release.release["signalPolicy"]["schemaVersion"],
            "short_cycle_forward_policy_v1",
        )
        self.assertEqual(candidate.candidate["exitRules"]["stopAtr"], 1.2)
        self.assertNotIn("stopLossPct", candidate.candidate["exitRules"])
        self.assertTrue(release.release["virtualAccountOnly"])
        self.assertFalse(release.release["createsOrders"])


if __name__ == "__main__":
    unittest.main()
