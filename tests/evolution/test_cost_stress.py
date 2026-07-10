from __future__ import annotations

import unittest

from alphapilot.evolution.evaluation.cost_stress import evaluate_cost_stress


class CostStressTests(unittest.TestCase):
    def test_standard_cost_matrix_includes_latency_and_gap(self) -> None:
        report = evaluate_cost_stress(
            gross_returns=[0.03, -0.01, 0.02, -0.005],
            base_fee_rate=0.001,
            base_slippage_rate=0.001,
            delayed_returns=[0.02, -0.015, 0.01, -0.01],
            extreme_gap_shock=0.02,
        )

        self.assertEqual(
            set(report.scenarios),
            {"baseline", "cost_2x", "cost_3x", "one_bar_delay", "extreme_gap"},
        )
        self.assertTrue(all(item.evaluated for item in report.scenarios.values()))
        self.assertGreater(
            report.scenarios["baseline"].totalReturn,
            report.scenarios["cost_3x"].totalReturn,
        )
        self.assertLess(
            report.scenarios["extreme_gap"].worstTrade,
            report.scenarios["baseline"].worstTrade,
        )
        self.assertEqual(report.scenarios["one_bar_delay"].returnSource, "delayed_returns")

    def test_missing_delayed_returns_is_explicit_not_fabricated(self) -> None:
        report = evaluate_cost_stress(
            gross_returns=[0.03, -0.01, 0.02],
            base_fee_rate=0.001,
            base_slippage_rate=0.001,
        )

        delayed = report.scenarios["one_bar_delay"]
        self.assertFalse(delayed.evaluated)
        self.assertEqual(delayed.blockedReason, "missing_delayed_returns")

    def test_invalid_cost_or_non_finite_return_fails(self) -> None:
        with self.assertRaises(ValueError):
            evaluate_cost_stress(
                gross_returns=[0.01, float("nan")],
                base_fee_rate=0.001,
                base_slippage_rate=0.001,
            )
        with self.assertRaises(ValueError):
            evaluate_cost_stress(
                gross_returns=[0.01],
                base_fee_rate=-0.001,
                base_slippage_rate=0.001,
            )


if __name__ == "__main__":
    unittest.main()
