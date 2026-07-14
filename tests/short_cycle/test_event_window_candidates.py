from __future__ import annotations

import unittest
from collections import Counter

from alphapilot.short_cycle.event_window_candidates import (
    cross_timeframe_workflow_candidate_pool,
    event_window_candidate_pool,
    event_window_factor_successor_candidate_pool,
    event_window_learned_candidate_pool,
    long_horizon_event_candidate_pool,
    one_hour_factor_successor_candidate_pool,
    research_eligible_event_window_workflow_candidates,
    event_window_short_cycle_workflow_candidates,
)


class EventWindowCandidateTests(unittest.TestCase):
    def test_pool_is_larger_than_registered_pack_and_balanced_by_timeframe(self) -> None:
        pool = event_window_candidate_pool()

        self.assertGreaterEqual(len(pool), 20)
        self.assertGreaterEqual(Counter(item.timeframe for item in pool)["5m"], 10)
        self.assertGreaterEqual(Counter(item.timeframe for item in pool)["15m"], 10)
        self.assertEqual(len({item.familyKey for item in pool}), len(pool))

    def test_selected_pack_has_five_per_timeframe_and_family_diversity(self) -> None:
        selected = event_window_short_cycle_workflow_candidates()

        self.assertEqual(len(selected), 10)
        self.assertEqual(Counter(item.timeframe for item in selected), {"5m": 5, "15m": 5})
        self.assertEqual(len({item.familyKey for item in selected}), 10)
        for timeframe in ("5m", "15m"):
            family_counts = Counter(
                item.signalFamily for item in selected if item.timeframe == timeframe
            )
            self.assertLessEqual(max(family_counts.values()), 2)

    def test_selected_candidates_keep_two_r_and_record_failure_lessons(self) -> None:
        for item in event_window_short_cycle_workflow_candidates():
            with self.subTest(candidate=item.familyKey):
                definition = item.definition()
                metadata = definition["researchMetadata"]
                self.assertEqual(definition["targetR"], 2.0)
                self.assertTrue(definition["researchOnly"])
                self.assertFalse(definition["executionEnabled"])
                self.assertIn(item.parameters["event_window"], (2, 3))
                self.assertEqual(metadata["selectionMethod"], "development_prescreen_v1")
                self.assertIn("archivedFailureLessons", metadata)
                self.assertGreater(len(metadata["archivedFailureLessons"]), 0)
                self.assertEqual(metadata["nearMissPolicy"], "shadow_only_no_execution")

    def test_learned_pool_has_five_per_timeframe_and_auditable_factor_guards(self) -> None:
        learned = event_window_learned_candidate_pool()

        self.assertEqual(len(learned), 10)
        self.assertEqual(Counter(item.timeframe for item in learned), {"5m": 5, "15m": 5})
        for item in learned:
            with self.subTest(candidate=item.familyKey):
                metadata = item.definition()["researchMetadata"]
                self.assertEqual(metadata["variant"], "learned_v1")
                self.assertEqual(
                    metadata["selectionMethod"],
                    "failure_attribution_temporal_symbol_holdback_v1",
                )
                self.assertEqual(metadata["prescreenStatus"], "expanded_validation_pending")
                self.assertIn("developmentFactorAttribution", metadata)
                self.assertTrue(
                    any(
                        key.startswith(("aligned_", "btc_aligned"))
                        for key in item.parameters
                    )
                    or item.parameters["atr_pct_min"]
                    > (0.0018 if item.timeframe == "5m" else 0.0025)
                )

    def test_long_horizon_pool_is_balanced_and_uses_scored_confirmation(self) -> None:
        candidates = long_horizon_event_candidate_pool()

        self.assertEqual(
            Counter(item.timeframe for item in candidates),
            {"1h": 10, "4h": 10, "1d": 10},
        )
        self.assertEqual(len({item.familyKey for item in candidates}), 30)
        for item in candidates:
            with self.subTest(candidate=item.familyKey):
                self.assertGreaterEqual(item.parameters["minimum_optional_checks"], 3)
                self.assertGreater(item.parameters["btc_shock_threshold"], 0.012)
                self.assertEqual(item.definition()["targetR"], 2.0)
                self.assertTrue(item.definition()["researchOnly"])
                self.assertFalse(item.definition()["executionEnabled"])

    def test_factor_successor_pack_has_four_robust_versions_and_one_shadow(self) -> None:
        candidates = event_window_factor_successor_candidate_pool()

        self.assertEqual(5, len(candidates))
        self.assertEqual({"15m"}, {item.timeframe for item in candidates})
        self.assertEqual(5, len({item.familyKey for item in candidates}))
        robust = []
        shadow = []
        for item in candidates:
            metadata = item.definition()["researchMetadata"]
            self.assertEqual(2.0, item.definition()["targetR"])
            self.assertFalse(metadata["lockedOrHoldoutUsedForSelection"])
            if metadata["prescreenStatus"] == "robust_factor_successor_pending_recheck":
                robust.append(item)
                self.assertTrue(metadata["developmentFactorAttribution"]["symbolHoldback"])
                self.assertTrue(
                    any(
                        key.startswith(("aligned_", "btc_", "atr_pct"))
                        and key.endswith(("_min", "_max"))
                        for key in item.parameters
                    )
                )
            else:
                shadow.append(item)
                self.assertEqual(
                    "no_robust_factor_guard_shadow_only",
                    metadata["prescreenStatus"],
                )

        self.assertEqual(4, len(robust))
        self.assertEqual(1, len(shadow))

    def test_one_hour_pack_uses_direct_factor_evidence_without_rigid_checks(self) -> None:
        candidates = one_hour_factor_successor_candidate_pool()

        self.assertEqual(5, len(candidates))
        self.assertEqual({"1h"}, {item.timeframe for item in candidates})
        self.assertEqual(5, len({item.familyKey for item in candidates}))
        statuses = [
            item.definition()["researchMetadata"]["prescreenStatus"]
            for item in candidates
        ]
        self.assertEqual(2, statuses.count("robust_factor_successor_pending_recheck"))
        self.assertEqual(3, statuses.count("no_robust_factor_guard_shadow_only"))
        for item in candidates:
            with self.subTest(candidate=item.familyKey):
                metadata = item.definition()["researchMetadata"]
                self.assertEqual(2, item.parameters["minimum_optional_checks"])
                self.assertEqual(2.0, item.definition()["targetR"])
                self.assertFalse(metadata["lockedOrHoldoutUsedForSelection"])

    def test_research_eligible_workflow_pack_contains_only_directly_supported_versions(self) -> None:
        candidates = research_eligible_event_window_workflow_candidates()

        self.assertEqual(7, len(candidates))
        self.assertEqual(
            Counter(item.timeframe for item in candidates),
            {"5m": 2, "15m": 4, "1h": 1},
        )
        self.assertEqual(len(candidates), len({item.familyKey for item in candidates}))
        for item in candidates:
            with self.subTest(candidate=item.familyKey):
                definition = item.definition()
                self.assertEqual(2.0, definition["targetR"])
                self.assertTrue(definition["researchOnly"])
                self.assertFalse(definition["executionEnabled"])
                self.assertFalse(
                    definition["researchMetadata"]["lockedOrHoldoutUsedForSelection"]
                )

    def test_cross_timeframe_pack_has_five_executable_research_candidates_each(self) -> None:
        candidates = cross_timeframe_workflow_candidate_pool()

        self.assertEqual(len(candidates), 25)
        self.assertEqual(
            Counter(item.timeframe for item in candidates),
            {"5m": 5, "15m": 5, "1h": 5, "4h": 5, "1d": 5},
        )
        self.assertEqual(len(candidates), len({item.familyKey for item in candidates}))
        for item in candidates:
            with self.subTest(candidate=item.familyKey):
                definition = item.definition()
                metadata = definition["researchMetadata"]
                self.assertEqual(definition["targetR"], 2.0)
                self.assertTrue(definition["researchOnly"])
                self.assertFalse(definition["executionEnabled"])
                self.assertFalse(metadata["lockedOrHoldoutUsedForSelection"])
                self.assertIn(metadata["selectionTier"], {"research_eligible", "shadow_only"})
                if item.timeframe in {"1h", "4h", "1d"}:
                    self.assertIn(item.parameters["event_window"], (3, 4, 5))
                    self.assertLessEqual(item.parameters["minimum_optional_checks"], 4)

        four_hour_plans = {
            tuple(sorted(item.definition()["formalDataPlan"].items()))
            for item in candidates
            if item.timeframe == "4h"
        }
        self.assertEqual(
            four_hour_plans,
            {
                tuple(
                    sorted(
                        {
                            "signal": "4h",
                            "execution": "15m",
                            "fallback": "1h",
                        }.items()
                    )
                )
            },
        )
        self.assertTrue(
            all(
                item.definition()["formalDataPlan"]
                == {"signal": "1d", "execution": "1h", "fallback": "4h"}
                for item in candidates
                if item.timeframe == "1d"
            )
        )

    def test_four_hour_pack_uses_bull_recovery_evidence(self) -> None:
        candidates = [
            item
            for item in cross_timeframe_workflow_candidate_pool()
            if item.timeframe == "4h"
        ]

        self.assertEqual({item.signalFamily for item in candidates}, {"windowed_recovery_reclaim_long"})
        for item in candidates:
            metadata = item.definition()["researchMetadata"]
            self.assertEqual(metadata["selectionTier"], "research_eligible")
            self.assertIn("v13_7_20_factory_failure_attribution", metadata["evidenceLineage"])

    def test_one_day_pack_preserves_sparse_candidates_as_shadow_only(self) -> None:
        candidates = [
            item
            for item in cross_timeframe_workflow_candidate_pool()
            if item.timeframe == "1d"
        ]

        self.assertEqual(
            Counter(item.definition()["researchMetadata"]["selectionTier"] for item in candidates),
            {"research_eligible": 3, "shadow_only": 2},
        )
        self.assertEqual(
            Counter(item.signalFamily for item in candidates),
            {
                "windowed_breakout_retest_long": 1,
                "windowed_squeeze_breakout_long": 2,
                "windowed_liquidity_sweep_reclaim_long": 2,
            },
        )


if __name__ == "__main__":
    unittest.main()
