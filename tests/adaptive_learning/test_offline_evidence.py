from __future__ import annotations

import unittest

from alphapilot.adaptive_learning.offline_evidence import build_offline_evidence


class AdaptiveOfflineEvidenceTests(unittest.TestCase):
    def test_completed_bench_with_zero_eligible_factors_stays_blocked(self) -> None:
        result = build_offline_evidence(
            factor_benchmark={
                "schemaVersion": "factor_benchmark_report_v1",
                "status": "completed",
                "controlStatus": "passed",
                "readinessPassed": True,
                "formalTrialCount": 32,
                "eligibleFactorCount": 0,
                "factorShortlistId": "factor-shortlist-1",
                "dataSnapshotId": "snapshot-1",
                "pitStatus": "diagnostic_proxy",
            },
            factor_shortlist={
                "schemaVersion": "factor_shortlist_v1",
                "factorShortlistId": "factor-shortlist-1",
                "eligibleFactors": [],
            },
            qlib_preflight={
                "schemaVersion": "v13_27_1_12_qlib_preflight_v1",
                "qlibCampaignMayRun": False,
                "modelCampaignRun": False,
                "blockers": ["fresh_holdout_ready"],
            },
        )

        self.assertEqual(result["status"], "blocked_no_validated_factor_subset")
        self.assertTrue(result["evidence"]["realFactorBenchReady"])
        self.assertFalse(result["evidence"]["validatedCryptoFactorSubsetReady"])
        self.assertFalse(result["evidence"]["qlibCampaignReady"])
        self.assertEqual(result["eligibleFactorCount"], 0)
        self.assertTrue(result["offlineEvidenceHash"].startswith("adaptive_offline_evidence_"))

    def test_shortlist_identity_mismatch_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "shortlist identity"):
            build_offline_evidence(
                factor_benchmark={
                    "schemaVersion": "factor_benchmark_report_v1",
                    "status": "completed",
                    "controlStatus": "passed",
                    "readinessPassed": True,
                    "formalTrialCount": 1,
                    "eligibleFactorCount": 1,
                    "factorShortlistId": "factor-shortlist-1",
                },
                factor_shortlist={
                    "schemaVersion": "factor_shortlist_v1",
                    "factorShortlistId": "factor-shortlist-2",
                    "eligibleFactors": ["factor-1"],
                },
                qlib_preflight={
                    "schemaVersion": "v13_27_1_12_qlib_preflight_v1",
                    "qlibCampaignMayRun": False,
                    "modelCampaignRun": False,
                    "blockers": [],
                },
            )


if __name__ == "__main__":
    unittest.main()
