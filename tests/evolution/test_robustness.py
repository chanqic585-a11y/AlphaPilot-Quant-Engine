from __future__ import annotations

import unittest

from alphapilot.evolution.evaluation.robustness import (
    block_bootstrap_confidence_interval,
    evaluate_group_stability,
    evaluate_parameter_neighborhood,
)


class RobustnessTests(unittest.TestCase):
    def test_block_bootstrap_is_seeded_and_preserves_positive_interval(self) -> None:
        values = [0.1, 0.2, 0.05, 0.15, 0.3, 0.1, 0.2, 0.25]
        first = block_bootstrap_confidence_interval(
            values, block_size=3, iterations=500, confidence=0.9, seed=17
        )
        second = block_bootstrap_confidence_interval(
            values, block_size=3, iterations=500, confidence=0.9, seed=17
        )

        self.assertEqual(first, second)
        self.assertGreater(first.lower, 0)
        self.assertLessEqual(first.lower, first.estimate)
        self.assertGreaterEqual(first.upper, first.estimate)

    def test_parameter_neighborhood_separates_stable_and_fragile_peaks(self) -> None:
        stable = evaluate_parameter_neighborhood(
            center_score=1.0,
            neighbor_scores=[0.9, 1.05, 0.95, 0.85],
            minimum_median_ratio=0.75,
        )
        fragile = evaluate_parameter_neighborhood(
            center_score=1.0,
            neighbor_scores=[0.1, -0.1, 0.2, 0.05],
            minimum_median_ratio=0.75,
        )

        self.assertTrue(stable.stable)
        self.assertFalse(fragile.stable)

    def test_group_stability_reports_pair_month_exchange_and_regime(self) -> None:
        rows = [
            {"pair": "BTC", "month": "2026-01", "exchange": "okx", "regime": "trend", "score": 0.3},
            {"pair": "ETH", "month": "2026-02", "exchange": "binance", "regime": "trend", "score": 0.2},
            {"pair": "SOL", "month": "2026-03", "exchange": "bybit", "regime": "range", "score": -0.1},
            {"pair": "BTC", "month": "2026-03", "exchange": "okx", "regime": "range", "score": 0.1},
        ]
        result = evaluate_group_stability(
            rows,
            dimensions=["pair", "month", "exchange", "regime"],
            metric="score",
            minimum_positive_fraction=0.5,
        )

        self.assertEqual(set(result), {"pair", "month", "exchange", "regime"})
        self.assertTrue(all(item.groupCount >= 2 for item in result.values()))
        self.assertEqual(result["regime"].worstGroup, "range")
        self.assertTrue(result["pair"].stable)


if __name__ == "__main__":
    unittest.main()
