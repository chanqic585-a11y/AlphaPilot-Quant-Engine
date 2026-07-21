from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from alphapilot.adaptive_learning.v60_technical_closure import (
    audit_alpha101_compatibility,
    audit_demo_decision_mode,
    build_drift_rollback_engineering_rehearsal,
    build_v60_technical_closure_evidence,
    build_technical_closure_matrix,
    run_alpha101_prefix_invariance_fixture,
    serialize_research_model_artifact,
)


class V60TechnicalClosureTests(unittest.TestCase):
    def test_alpha101_prefix_fixture_is_deterministic_and_non_predictive(self) -> None:
        result = run_alpha101_prefix_invariance_fixture()

        self.assertTrue(result["passed"])
        self.assertTrue(result["deterministic"])
        self.assertTrue(result["prefixInvariant"])
        self.assertFalse(result["predictiveValidationClaimed"])
        self.assertFalse(result["grantsLiveAuthority"])

    def test_alpha101_compatibility_is_point_in_time_but_not_predictive(self) -> None:
        result = audit_alpha101_compatibility(
            production_registry={
                "factors": [
                    {"factorId": "cs_rank", "sourceClass": "alpha101_style"},
                    {"factorId": "volume_corr", "sourceClass": "alpha101_style"},
                ]
            },
            prefix_invariance={
                "status": "passed",
                "passed": True,
                "deterministic": True,
                "prefixInvariant": True,
                "checkedFactorCount": 18,
                "checkedRowCount": 24,
                "checkHash": "prefix-check",
            },
        )

        self.assertTrue(result["passed"])
        self.assertEqual(result["status"], "passed")
        self.assertTrue(result["pointInTimeCompatibilityReady"])
        self.assertFalse(result["predictiveValidationClaimed"])
        self.assertFalse(result["grantsLiveAuthority"])

    def test_model_serialization_is_canonical_and_research_only(self) -> None:
        artifact = {
            "modelType": "logistic_regression",
            "featureNames": ["return_1"],
            "parameters": {"weights": [0.5], "intercept": 0.1},
            "metrics": {"brierScore": 0.2},
            "trainingEvidence": {"foldCount": 4, "sampleCount": 100},
            "modelHash": "model-research",
            "researchOnly": True,
        }
        with tempfile.TemporaryDirectory() as directory:
            first = serialize_research_model_artifact(
                artifact=artifact,
                output_path=Path(directory) / "model-a.json",
            )
            second = serialize_research_model_artifact(
                artifact=json.loads(json.dumps(artifact)),
                output_path=Path(directory) / "model-b.json",
            )

            self.assertEqual(first["artifactSha256"], second["artifactSha256"])
            self.assertEqual(
                (Path(directory) / "model-a.json").read_bytes(),
                (Path(directory) / "model-b.json").read_bytes(),
            )
        self.assertTrue(first["artifactIntegrityReady"])
        self.assertFalse(first["liveEligible"])
        self.assertFalse(first["grantsLiveAuthority"])

    def test_drift_and_rollback_rehearsal_does_not_claim_production_readiness(self) -> None:
        result = build_drift_rollback_engineering_rehearsal(
            champion_model_id=None,
            predecessor_model_id=None,
        )

        self.assertTrue(result["engineeringPassed"])
        self.assertFalse(result["productionDriftMonitoringReady"])
        self.assertFalse(result["productionRollbackReady"])
        self.assertIn("no_live_eligible_champion_model", result["blockers"])
        self.assertIn("no_champion_predecessor_pair", result["blockers"])

    def test_demo_decision_mode_requires_real_reconciled_outcomes(self) -> None:
        result = audit_demo_decision_mode(
            decisions=[{"decisionMode": "observer", "changesOrders": False}],
            reconciled_outcomes=[],
        )

        self.assertFalse(result["passed"])
        self.assertEqual(result["status"], "blocked")
        self.assertIn("no_decision_participating_demo_mode", result["blockers"])
        self.assertIn("no_reconciled_closed_demo_outcomes", result["blockers"])
        self.assertFalse(result["createsOrders"])

    def test_closure_matrix_never_mints_successor_identity_when_blocked(self) -> None:
        result = build_technical_closure_matrix(
            prior_readiness={
                "evidence": {
                    "factorProductionReady": True,
                    "realFactorBenchReady": True,
                    "alpha191CompatibilityReady": True,
                    "boundedFactorMiningReady": True,
                    "shadowInferenceReady": True,
                    "onlineInferenceLatencyReady": True,
                    "liveFeaturePipelineReady": True,
                }
            },
            evidence={
                "alpha101Ready": {"status": "passed", "passed": True},
                "modelDriftMonitoringReady": {"status": "blocked", "passed": False},
            },
        )

        self.assertFalse(result["passed"])
        self.assertIsNone(result["successorIdentity"])
        self.assertFalse(result["approvalRequestActionable"])
        self.assertFalse(result["liveArmAllowed"])
        self.assertFalse(result["createsOrders"])

    def test_evidence_bundle_writes_truthful_blocked_matrix(self) -> None:
        model = {
            "modelId": "research-model-record",
            "status": "shadow_candidate",
            "artifact": {
                "modelType": "logistic_regression",
                "featureNames": ["return_1"],
                "parameters": {"weights": [0.5], "intercept": 0.1},
                "metrics": {"brierScore": 0.2},
                "trainingEvidence": {
                    "foldCount": 0,
                    "purgedWalkForward": True,
                    "sampleCount": 100,
                },
                "modelHash": "model-research",
                "researchOnly": True,
            },
        }
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "evidence"
            result = build_v60_technical_closure_evidence(
                output_dir=output,
                generated_at="2026-07-21T15:00:00Z",
                production_registry={
                    "factors": [
                        {"factorId": "cs_rank", "sourceClass": "alpha101_style"}
                    ]
                },
                prior_readiness={
                    "evidenceStatus": {
                        "factorProductionReady": True,
                        "realFactorBenchReady": True,
                        "alpha191CompatibilityReady": True,
                        "boundedFactorMiningReady": True,
                        "shadowInferenceReady": True,
                        "onlineInferenceLatencyReady": True,
                        "liveFeaturePipelineReady": True,
                    }
                },
                model_record=model,
                factor_campaign={
                    "status": "completed_no_candidate",
                    "formalPromotionEligible": False,
                    "blockers": ["oos_profit_factor_below_threshold"],
                },
                registry_audit={"liveEligibleModelCount": 0},
                factor_benchmark={
                    "status": "completed",
                    "eligibleFactorCount": 0,
                },
                qlib_readiness={
                    "status": "blocked",
                    "qlibCampaignMayRun": False,
                    "modelCampaignRun": False,
                    "blockers": ["fresh_holdout_ready"],
                },
                decisions=[],
                reconciled_outcomes=[],
            )

            matrix = json.loads(
                (output / "adaptive_learning_technical_closure_matrix.json").read_text(
                    encoding="utf-8"
                )
            )
            manifest = json.loads(
                (output / "artifact_manifest.json").read_text(encoding="utf-8")
            )

        self.assertEqual(result["status"], "blocked_not_ready")
        self.assertEqual(matrix["readyCount"], 8)
        self.assertFalse(matrix["passed"])
        self.assertIsNone(matrix["successorIdentity"])
        self.assertFalse(result["approvalRequestActionable"])
        self.assertGreaterEqual(manifest["artifactCount"], 10)
        self.assertTrue(manifest["manifestHash"].startswith("v60_2_manifest_"))


if __name__ == "__main__":
    unittest.main()
