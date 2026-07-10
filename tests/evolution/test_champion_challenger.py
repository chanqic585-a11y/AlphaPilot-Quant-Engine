from __future__ import annotations

import unittest

from alphapilot.evolution.models.champion_challenger import compare_champion_challenger


class ChampionChallengerTests(unittest.TestCase):
    def test_better_challenger_can_only_request_shadow(self) -> None:
        decision = compare_champion_challenger(
            champion_model_id="champion",
            challenger_model_id="challenger",
            champion_metrics={"logLoss": 0.5, "brierScore": 0.18},
            challenger_metrics={
                "logLoss": 0.42,
                "brierScore": 0.14,
                "foldCount": 4,
                "costStressPassed": True,
                "stabilityPassed": True,
                "calibrationPassed": True,
            },
            minimum_relative_improvement=0.05,
            minimum_folds=3,
        )

        self.assertTrue(decision.approvedForShadow)
        self.assertEqual(decision.requestedStatus, "shadow_approved")
        self.assertFalse(decision.autoReplacesDemo)
        self.assertFalse(decision.createsOrders)

    def test_weak_challenger_is_rejected(self) -> None:
        decision = compare_champion_challenger(
            champion_model_id="champion",
            challenger_model_id="challenger",
            champion_metrics={"logLoss": 0.5, "brierScore": 0.18},
            challenger_metrics={
                "logLoss": 0.52,
                "brierScore": 0.2,
                "foldCount": 2,
                "costStressPassed": False,
                "stabilityPassed": False,
                "calibrationPassed": False,
            },
        )

        self.assertFalse(decision.approvedForShadow)
        self.assertEqual(decision.requestedStatus, "rejected")
        self.assertGreater(len(decision.reasons), 0)


if __name__ == "__main__":
    unittest.main()
