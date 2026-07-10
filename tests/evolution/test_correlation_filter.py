from __future__ import annotations

import unittest

from alphapilot.evolution.factor_mining.correlation_filter import filter_correlated_candidates


class CorrelationFilterTests(unittest.TestCase):
    def test_absolute_correlation_and_constant_series_are_rejected(self) -> None:
        result = filter_correlated_candidates(
            candidate_series={
                "candidate_a": [1, 2, 3, 4, 5, 6],
                "candidate_b": [6, 5, 4, 3, 2, 1],
                "candidate_c": [1, 1, 1, 1, 1, 1],
                "candidate_d": [1, 3, 2, 5, 4, 7],
            },
            reference_series={"existing": [1, 2, 3, 4, 5, 6]},
            threshold=0.9,
            minimum_observations=5,
        )

        self.assertEqual(result.acceptedIds, ["candidate_d"])
        reasons = {item.candidateId: item.reason for item in result.rejected}
        self.assertEqual(reasons["candidate_a"], "correlation_threshold_exceeded")
        self.assertEqual(reasons["candidate_b"], "correlation_threshold_exceeded")
        self.assertEqual(reasons["candidate_c"], "insufficient_variance")

    def test_missing_values_fail_instead_of_being_imputed(self) -> None:
        with self.assertRaises(ValueError):
            filter_correlated_candidates(
                candidate_series={"bad": [1, float("nan"), 2]},
                minimum_observations=3,
            )


if __name__ == "__main__":
    unittest.main()
