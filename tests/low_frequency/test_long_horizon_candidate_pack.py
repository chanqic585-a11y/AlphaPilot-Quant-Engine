from __future__ import annotations

import unittest

from alphapilot.low_frequency.long_horizon_candidate_pack import (
    build_long_horizon_report,
    build_long_horizon_candidate_specs,
    classify_event_window_prescreen_result,
    classify_research_evidence,
    deterministic_symbol_split,
    select_timeframe_pack,
)


class LongHorizonCandidatePackTests(unittest.TestCase):
    def test_candidate_specs_have_five_per_timeframe_and_keep_two_r(self) -> None:
        specs = build_long_horizon_candidate_specs()

        for timeframe in ("1h", "4h", "1d"):
            selected = [item for item in specs if item["timeframe"] == timeframe]
            self.assertEqual(5, len(selected))
            self.assertTrue(all(item["targetR"] >= 2.0 for item in selected))

        one_hour = [item for item in specs if item["timeframe"] == "1h"]
        self.assertTrue(
            all(item["parameters"]["minimum_optional_checks"] <= 2 for item in one_hour)
        )

    def test_classification_requires_declared_selection_checks(self) -> None:
        result = classify_research_evidence(
            {
                "targetR": 2.0,
                "selectionChecks": {
                    "developmentPositive": True,
                    "temporalValidationPositive": True,
                    "symbolHoldbackPositive": False,
                },
                "metrics": {"tradeCount": 120, "profitFactor": 1.3},
                "lockedEvidence": {"profitFactor": 9.0},
            }
        )

        self.assertEqual("shadow_only", result["selectionTier"])
        self.assertIn("symbolHoldbackPositive", result["failedSelectionChecks"])

    def test_locked_evidence_never_turns_candidate_into_research_eligible(self) -> None:
        result = classify_research_evidence(
            {
                "targetR": 2.0,
                "selectionChecks": {
                    "developmentPositive": False,
                    "temporalValidationPositive": False,
                },
                "metrics": {"tradeCount": 500, "profitFactor": 0.8},
                "lockedEvidence": {"tradeCount": 1000, "profitFactor": 4.0},
            }
        )

        self.assertEqual("rejected", result["selectionTier"])
        self.assertFalse(result["lockedOrHoldoutUsedForSelection"])

    def test_pack_prefers_research_eligible_then_shadow_and_limits_to_five(self) -> None:
        rows = []
        for index in range(8):
            rows.append(
                {
                    "candidateId": f"candidate_{index}",
                    "timeframe": "4h",
                    "targetR": 2.0,
                    "selectionTier": "research_eligible" if index in {1, 3} else "shadow_only",
                    "selectionScore": 100 - index,
                }
            )

        selected = select_timeframe_pack(rows, timeframe="4h", limit=5)

        self.assertEqual(5, len(selected))
        self.assertEqual(
            ["candidate_1", "candidate_3"],
            [item["candidateId"] for item in selected[:2]],
        )

    def test_report_keeps_candidate_count_separate_from_eligibility(self) -> None:
        rows = []
        for timeframe in ("1h", "4h", "1d"):
            for index in range(5):
                rows.append(
                    {
                        "candidateId": f"{timeframe}_{index}",
                        "displayName": f"{timeframe} candidate {index}",
                        "timeframe": timeframe,
                        "targetR": 2.0,
                        "selectionTier": (
                            "research_eligible" if timeframe != "1h" else "shadow_only"
                        ),
                        "selectionScore": 10 - index,
                    }
                )

        report = build_long_horizon_report(rows)

        self.assertEqual(15, report["summary"]["selectedCandidateCount"])
        self.assertEqual(0, report["summary"]["researchEligibleByTimeframe"]["1h"])
        self.assertEqual(5, report["summary"]["shadowOnlyByTimeframe"]["1h"])
        self.assertFalse(report["lockedOrHoldoutUsedForSelection"])

    def test_symbol_holdback_split_is_deterministic_disjoint_and_nonempty(self) -> None:
        pairs = [f"PAIR-{index}" for index in range(12)]

        first = deterministic_symbol_split(pairs)
        second = deterministic_symbol_split(reversed(pairs))

        self.assertEqual(first, second)
        self.assertTrue(first["development"])
        self.assertTrue(first["holdback"])
        self.assertFalse(set(first["development"]) & set(first["holdback"]))

    def test_direct_event_result_uses_weakest_segment_and_preserves_rejection(self) -> None:
        candidate = {
            "candidateId": "direct_1h",
            "displayName": "Direct 1H",
            "timeframe": "1h",
            "targetR": 2.0,
        }
        result = {
            "eligible": False,
            "rejectionReasons": ["symbol_holdback_positive_pair_share_below_50pct"],
            "segmentMetrics": {
                "derivationTrain": {
                    "tradeCount": 100,
                    "expectancyR": 0.2,
                    "profitFactor": 1.3,
                },
                "derivationValidation": {
                    "tradeCount": 50,
                    "expectancyR": 0.1,
                    "profitFactor": 1.2,
                },
                "symbolHoldback": {
                    "tradeCount": 40,
                    "expectancyR": 0.01,
                    "profitFactor": 1.01,
                },
            },
        }

        classified = classify_event_window_prescreen_result(candidate, result)

        self.assertEqual("shadow_only", classified["selectionTier"])
        self.assertTrue(classified["directCandidateBacktestCompleted"])
        self.assertEqual(190, classified["metrics"]["tradeCount"])
        self.assertEqual(1.01, classified["metrics"]["profitFactor"])
        self.assertIn(
            "symbol_holdback_positive_pair_share_below_50pct",
            classified["failedSelectionChecks"],
        )


if __name__ == "__main__":
    unittest.main()
