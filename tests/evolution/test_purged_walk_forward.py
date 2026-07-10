from __future__ import annotations

import unittest

from alphapilot.evolution.evaluation.purged_walk_forward import build_purged_walk_forward


class PurgedWalkForwardTests(unittest.TestCase):
    def test_expanding_folds_include_purge_and_embargo(self) -> None:
        manifest = build_purged_walk_forward(
            sample_count=140,
            min_train_size=40,
            test_size=20,
            step_size=20,
            label_horizon=5,
            embargo_size=5,
            max_holding_period=5,
            mode="expanding",
        )

        self.assertEqual(len(manifest.folds), 4)
        first = manifest.folds[0]
        self.assertEqual(first.trainStart, 0)
        self.assertEqual(first.trainEndExclusive, 40)
        self.assertEqual(first.purgeStart, 40)
        self.assertEqual(first.purgeEndExclusive, 45)
        self.assertEqual(first.embargoStart, 45)
        self.assertEqual(first.embargoEndExclusive, 50)
        self.assertEqual(first.testStart, 50)
        self.assertEqual(first.testEndExclusive, 70)

    def test_rolling_folds_keep_fixed_training_window(self) -> None:
        manifest = build_purged_walk_forward(
            sample_count=180,
            min_train_size=40,
            train_window=50,
            test_size=20,
            step_size=20,
            label_horizon=3,
            embargo_size=4,
            max_holding_period=4,
            mode="rolling",
        )

        self.assertGreaterEqual(len(manifest.folds), 3)
        self.assertTrue(all(fold.trainSize <= 50 for fold in manifest.folds))
        self.assertGreater(manifest.folds[-1].trainStart, 0)

    def test_manifest_is_reproducible_and_has_no_boundary_overlap(self) -> None:
        args = dict(
            sample_count=160,
            min_train_size=50,
            test_size=20,
            step_size=20,
            label_horizon=4,
            embargo_size=6,
            max_holding_period=6,
            mode="expanding",
        )
        first = build_purged_walk_forward(**args)
        second = build_purged_walk_forward(**args)

        self.assertEqual(first.manifestHash, second.manifestHash)
        self.assertEqual(first.to_dict(), second.to_dict())
        for fold in first.folds:
            self.assertLessEqual(fold.trainEndExclusive, fold.purgeStart)
            self.assertLessEqual(fold.purgeEndExclusive, fold.embargoStart)
            self.assertLessEqual(fold.embargoEndExclusive, fold.testStart)

    def test_insufficient_embargo_and_too_few_folds_fail_closed(self) -> None:
        with self.assertRaises(ValueError):
            build_purged_walk_forward(
                sample_count=140,
                min_train_size=40,
                test_size=20,
                label_horizon=5,
                embargo_size=2,
                max_holding_period=5,
            )
        with self.assertRaises(ValueError):
            build_purged_walk_forward(
                sample_count=70,
                min_train_size=40,
                test_size=20,
                label_horizon=5,
                embargo_size=5,
                max_holding_period=5,
                min_folds=3,
            )


if __name__ == "__main__":
    unittest.main()
