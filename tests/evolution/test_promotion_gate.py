from __future__ import annotations

import unittest

from alphapilot.evolution.promotion.gate import (
    PromotionEvidence,
    evaluate_demo_promotion,
)


def passing_evidence(**overrides: object) -> PromotionEvidence:
    values = {
        "frequency": "short_cycle",
        "pointInTimePassed": True,
        "leakageCheckPassed": True,
        "fdrPassed": True,
        "deflatedSharpePassed": True,
        "pboPassed": True,
        "validWalkForwardFolds": 4,
        "lockedOosProfitFactor": 1.31,
        "doubledCostProfitFactor": 1.08,
        "maxDrawdownPercent": 12.0,
        "realizedRewardRisk": 2.05,
        "largestSymbolShare": 0.20,
        "largestMonthShare": 0.18,
        "largestRegimeShare": 0.55,
        "lockedOosClosedSamples": 220,
        "shadowClosedSamples": 55,
        "shadowCalendarDays": 16,
        "shadowPublicMarketDriven": True,
        "inputsFrozen": True,
        "checksumsMatch": True,
    }
    values.update(overrides)
    return PromotionEvidence(**values)


class PromotionGateTests(unittest.TestCase):
    def test_complete_short_cycle_evidence_passes(self) -> None:
        result = evaluate_demo_promotion(passing_evidence())

        self.assertTrue(result.passed)
        self.assertEqual(result.targetStatus, "demo_eligible")
        self.assertTrue(all(check.passed for check in result.checks))

    def test_sample_and_concentration_failures_are_explicit(self) -> None:
        result = evaluate_demo_promotion(
            passing_evidence(shadowClosedSamples=12, largestSymbolShare=0.41)
        )

        self.assertFalse(result.passed)
        self.assertEqual(result.targetStatus, "shadow_observation")
        self.assertIn("shadow_closed_samples", result.failedCheckIds)
        self.assertIn("symbol_concentration", result.failedCheckIds)

    def test_unknown_frequency_fails_closed(self) -> None:
        with self.assertRaises(ValueError):
            evaluate_demo_promotion(passing_evidence(frequency="unknown"))


if __name__ == "__main__":
    unittest.main()
