from __future__ import annotations

import unittest

from alphapilot.evolution.models.calibrator import calibrate_scores


class ModelCalibratorTests(unittest.TestCase):
    def test_platt_calibration_is_deterministic_and_improves_underconfident_scores(self) -> None:
        scores = [-0.4, -0.3, -0.2, -0.1, 0.1, 0.2, 0.3, 0.4]
        labels = [0, 0, 0, 0, 1, 1, 1, 1]

        first = calibrate_scores(scores, labels, bin_count=4)
        second = calibrate_scores(scores, labels, bin_count=4)

        self.assertEqual(first, second)
        self.assertLessEqual(first.brierAfter, first.brierBefore)
        self.assertTrue(all(0 <= value <= 1 for value in first.calibratedProbabilities))
        self.assertGreater(len(first.reliabilityBins), 0)

    def test_invalid_labels_and_non_finite_scores_fail(self) -> None:
        with self.assertRaises(ValueError):
            calibrate_scores([0.1, 0.2], [0, 2])
        with self.assertRaises(ValueError):
            calibrate_scores([0.1, float("nan")], [0, 1])


if __name__ == "__main__":
    unittest.main()
