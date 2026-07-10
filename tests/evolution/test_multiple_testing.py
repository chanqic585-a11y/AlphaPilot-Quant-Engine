from __future__ import annotations

import unittest

from alphapilot.evolution.evaluation.multiple_testing import (
    benjamini_hochberg,
    deflated_sharpe_probability,
    probability_of_backtest_overfitting,
)


class MultipleTestingTests(unittest.TestCase):
    def test_benjamini_hochberg_controls_false_discovery_rate(self) -> None:
        result = benjamini_hochberg(
            {"factor_a": 0.001, "factor_b": 0.02, "factor_c": 0.2, "factor_d": 0.8},
            q=0.05,
        )

        self.assertEqual(result.discoveries, ["factor_a", "factor_b"])
        decisions = {item.itemId: item for item in result.decisions}
        self.assertAlmostEqual(decisions["factor_a"].adjustedPValue, 0.004)
        self.assertAlmostEqual(decisions["factor_b"].adjustedPValue, 0.04)
        self.assertFalse(decisions["factor_c"].significant)

    def test_benjamini_hochberg_rejects_invalid_inputs(self) -> None:
        with self.assertRaises(ValueError):
            benjamini_hochberg({"bad": -0.1})
        with self.assertRaises(ValueError):
            benjamini_hochberg({"bad": 1.1})
        with self.assertRaises(ValueError):
            benjamini_hochberg({}, q=0.1)

    def test_deflated_sharpe_penalizes_trial_count(self) -> None:
        strong = deflated_sharpe_probability(
            observed_sharpe=1.5,
            n_trials=20,
            observations=500,
            sharpe_std=0.15,
            confidence_threshold=0.95,
        )
        weak = deflated_sharpe_probability(
            observed_sharpe=0.2,
            n_trials=100,
            observations=100,
            sharpe_std=0.2,
            confidence_threshold=0.95,
        )

        self.assertTrue(strong.passes)
        self.assertGreater(strong.probability, 0.95)
        self.assertFalse(weak.passes)
        self.assertLess(weak.probability, 0.5)

    def test_pbo_like_partition_diagnoses_selection_reversal(self) -> None:
        overfit = probability_of_backtest_overfitting(
            train_scores=[[3, 2, 1], [1, 3, 2], [2, 1, 3]],
            test_scores=[[1, 2, 3], [3, 1, 2], [2, 3, 1]],
        )
        stable = probability_of_backtest_overfitting(
            train_scores=[[3, 2, 1], [3, 2, 1], [3, 2, 1]],
            test_scores=[[3, 2, 1], [3, 2, 1], [3, 2, 1]],
        )

        self.assertEqual(overfit.pbo, 1.0)
        self.assertEqual(stable.pbo, 0.0)
        self.assertEqual(len(overfit.selectedIndexes), 3)


if __name__ == "__main__":
    unittest.main()
