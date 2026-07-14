from __future__ import annotations

import unittest

from alphapilot.reports.cross_timeframe_candidate_inventory import (
    build_cross_timeframe_candidate_inventory,
    classify_event_prescreen_candidate,
    normalize_long_horizon_candidate,
)


class CrossTimeframeCandidateInventoryTests(unittest.TestCase):
    def test_event_prescreen_candidate_is_shadow_when_all_segments_are_positive(self) -> None:
        result = {
            "candidateKey": "candidate_1",
            "displayName": "Candidate 1",
            "timeframe": "15m",
            "signalFamily": "family",
            "direction": "long",
            "targetR": 2.0,
            "eligible": False,
            "rejectionReasons": ["symbol_holdback_positive_pair_share_below_50pct"],
            "segmentMetrics": {
                "derivationTrain": {"tradeCount": 30, "profitFactor": 1.2, "expectancyR": 0.1},
                "derivationValidation": {"tradeCount": 20, "profitFactor": 1.1, "expectancyR": 0.05},
                "symbolHoldback": {"tradeCount": 20, "profitFactor": 1.01, "expectancyR": 0.01},
            },
        }

        row = classify_event_prescreen_candidate(result)

        self.assertEqual("shadow_only", row["selectionTier"])
        self.assertFalse(row["lockedOrHoldoutUsedForSelection"])
        self.assertTrue(row["executableWorkflowAvailable"])

    def test_long_horizon_candidate_is_report_only_and_derives_average_net_r(self) -> None:
        row = normalize_long_horizon_candidate(
            {
                "candidateId": "candidate_4h",
                "displayName": "4H candidate",
                "timeframe": "4h",
                "targetR": 2.0,
                "selectionTier": "research_eligible",
                "metrics": {"tradeCount": 40, "totalNetR": 8.0},
            }
        )

        self.assertFalse(row["executableWorkflowAvailable"])
        self.assertEqual("low_frequency_formal_workflow_adapter_pending", row["workflowBlocker"])
        self.assertEqual(0.2, row["metrics"]["expectancyR"])

    def test_inventory_has_five_per_timeframe_and_separates_eligibility(self) -> None:
        candidates = []
        for timeframe in ("5m", "15m", "1h", "4h", "1d"):
            for index in range(5):
                candidates.append(
                    {
                        "candidateId": f"{timeframe}_{index}",
                        "displayName": f"{timeframe} candidate {index}",
                        "timeframe": timeframe,
                        "targetR": 2.0,
                        "selectionTier": (
                            "research_eligible" if index < 2 else "rejected"
                        ),
                    }
                )

        report = build_cross_timeframe_candidate_inventory(candidates)

        self.assertEqual(25, report["summary"]["candidateCount"])
        self.assertEqual(
            {"5m": 5, "15m": 5, "1h": 5, "4h": 5, "1d": 5},
            report["summary"]["candidateCountByTimeframe"],
        )
        self.assertEqual(10, report["summary"]["researchEligibleCount"])
        self.assertEqual(15, report["summary"]["rejectedCount"])
        self.assertEqual(0, report["summary"]["executableResearchEligibleCount"])
        self.assertFalse(report["lockedOrHoldoutUsedForSelection"])

    def test_inventory_rejects_target_below_two_r(self) -> None:
        rows = [
            {
                "candidateId": f"{timeframe}_{index}",
                "displayName": "candidate",
                "timeframe": timeframe,
                "targetR": 1.5 if timeframe == "5m" and index == 0 else 2.0,
                "selectionTier": "rejected",
            }
            for timeframe in ("5m", "15m", "1h", "4h", "1d")
            for index in range(5)
        ]

        with self.assertRaisesRegex(ValueError, "target_r_below_two"):
            build_cross_timeframe_candidate_inventory(rows)


if __name__ == "__main__":
    unittest.main()
