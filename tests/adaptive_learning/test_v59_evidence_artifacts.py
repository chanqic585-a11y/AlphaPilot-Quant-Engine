from __future__ import annotations

import unittest

from alphapilot.adaptive_learning.v59_evidence_artifacts import (
    build_alpha191_compatibility_audit,
    build_model_validation_report,
    build_qlib_preflight_audit,
    build_training_dataset_manifest,
    run_shadow_inference_engineering_audit,
)


class V59EvidenceArtifactTests(unittest.TestCase):
    def test_alpha191_compatibility_does_not_claim_predictive_validation(self) -> None:
        result = build_alpha191_compatibility_audit(
            production_registry={
                "alpha191Compatibility": {
                    "catalogCount": 191,
                    "formulaReviewedCount": 8,
                    "numericCrossvalidatedCount": 8,
                    "productionValidatedCount": 0,
                }
            },
            numeric_crossvalidation={
                "seedCount": 8,
                "unexpectedMismatchCount": 0,
                "formulaConflictCount": 0,
                "reportHash": "numeric-crosscheck-hash",
            },
        )

        self.assertEqual(result["status"], "passed")
        self.assertTrue(result["passed"])
        self.assertEqual(result["validationScope"], "formula_and_numeric_compatibility_only")
        self.assertFalse(result["predictiveValidationClaimed"])
        self.assertFalse(result["allFactorsProductionValidated"])
        self.assertFalse(result["grantsLiveAuthority"])

    def test_model_validation_preserves_failed_formal_campaign(self) -> None:
        result = build_model_validation_report(
            campaign={
                "status": "completed_no_candidate",
                "reportId": "formal-factor-campaign",
                "dataSnapshotId": "snapshot-1",
                "formalPromotionEligible": False,
                "blockers": ["insufficient_oos_trades", "cost_stress_failed"],
                "experiments": [{"direction": "long"}, {"direction": "short"}],
                "models": [{"modelHash": "model-1"}, {"modelHash": "model-2"}],
                "strategyCandidates": [],
                "walkForwardManifest": {"manifestHash": "walk-forward-hash"},
            },
            registry_audit={
                "auditHash": "audit-hash",
                "liveEligibleModelCount": 0,
            },
        )

        self.assertEqual(result["status"], "completed_failed")
        self.assertFalse(result["passed"])
        self.assertEqual(result["candidateCount"], 0)
        self.assertEqual(result["liveEligibleModelCount"], 0)
        self.assertIn("insufficient_oos_trades", result["blockers"])
        self.assertFalse(result["grantsLiveAuthority"])

    def test_market_matrix_is_not_a_continuous_learning_dataset_without_demo_outcomes(self) -> None:
        result = build_training_dataset_manifest(
            campaign={
                "dataSnapshotId": "snapshot-1",
                "matrix": {
                    "rowCount": 235430,
                    "featureColumns": ["factor_return_1", "factor_rsi_14"],
                    "matrixHash": "matrix-hash",
                },
                "walkForwardManifest": {"manifestHash": "walk-forward-hash"},
            },
            matrix_path="D:/data/factor-matrix.parquet",
            demo_learning_sample_count=0,
            live_learning_sample_count=0,
        )

        self.assertEqual(result["status"], "blocked")
        self.assertFalse(result["passed"])
        self.assertEqual(result["formalMarketRowCount"], 235430)
        self.assertEqual(result["eligibleClosedOutcomeCount"], 0)
        self.assertIn("no_reconciled_closed_strategy_outcomes", result["blockers"])
        self.assertFalse(result["syntheticOutcomesUsed"])

    def test_research_only_model_can_prove_determinism_without_becoming_live_ready(self) -> None:
        result = run_shadow_inference_engineering_audit(
            model_artifact={
                "modelType": "logistic_regression",
                "featureNames": ["factor_return_1"],
                "parameters": {
                    "weights": [0.5],
                    "means": [0.0],
                    "scales": [1.0],
                    "intercept": 0.0,
                },
                "metrics": {},
                "trainingEvidence": {"foldCount": 0, "sampleCount": 10},
                "modelHash": "research-model",
                "researchOnly": True,
            },
            feature_rows=[[0.1], [-0.2], [0.3]],
            iterations=3,
        )

        self.assertTrue(result["deterministic"])
        self.assertTrue(result["engineeringChecksPassed"])
        self.assertFalse(result["passed"])
        self.assertEqual(result["status"], "blocked")
        self.assertIn("research_only_model", result["blockers"])
        self.assertFalse(result["grantsLiveAuthority"])

    def test_qlib_campaign_stays_blocked_when_data_and_runtime_are_not_ready(self) -> None:
        result = build_qlib_preflight_audit(
            readiness_gate={
                "status": "blocked",
                "blockers": [
                    "c_formal_ready",
                    "pit_median_at_least_30",
                    "fresh_holdout_ready",
                ],
            },
            qlib_package_available=False,
            docker_daemon_available=False,
        )

        self.assertEqual(result["status"], "blocked")
        self.assertFalse(result["passed"])
        self.assertFalse(result["campaignExecuted"])
        self.assertIn("qlib_package_unavailable", result["blockers"])
        self.assertIn("docker_daemon_unavailable", result["blockers"])
        self.assertFalse(result["grantsLiveAuthority"])


if __name__ == "__main__":
    unittest.main()
