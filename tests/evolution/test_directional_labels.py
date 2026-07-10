from __future__ import annotations

import unittest

import pandas as pd

from alphapilot.evolution.factor_runs.labels import (
    DirectionalLabelConfig,
    build_directional_labels,
)


class DirectionalLabelTests(unittest.TestCase):
    def _frame(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "timestamp_ms": [0, 1, 2, 3, 4, 5, 6],
                "open": [90.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0],
                "high": [91.0, 103.0, 101.0, 101.0, 101.0, 101.0, 101.0],
                "low": [89.0, 99.0, 99.5, 99.5, 99.5, 99.5, 99.5],
                "close": [90.0, 100.5, 100.2, 100.1, 100.0, 100.0, 100.0],
            }
        )

    def test_entry_uses_next_bar_and_same_bar_ambiguity_is_stop_first(self) -> None:
        labels = build_directional_labels(
            self._frame(),
            risk_distance=pd.Series([1.0] * 7),
            config=DirectionalLabelConfig(maxHoldingBars=3),
        )
        self.assertTrue(bool(labels.loc[0, "label_long_available"]))
        self.assertEqual(labels.loc[0, "label_long_entry_price"], 100.0)
        self.assertEqual(labels.loc[0, "label_long_outcome"], "stop")
        self.assertEqual(labels.loc[0, "label_long_target_hit"], 0)
        self.assertTrue(bool(labels.loc[0, "label_long_same_bar_ambiguous"]))
        self.assertLess(labels.loc[0, "label_long_net_r"], -1.0)

    def test_incomplete_future_path_is_unavailable(self) -> None:
        labels = build_directional_labels(
            self._frame(),
            risk_distance=pd.Series([1.0] * 7),
            config=DirectionalLabelConfig(maxHoldingBars=3),
        )
        self.assertFalse(bool(labels.loc[6, "label_long_available"]))
        self.assertEqual(labels.loc[6, "label_long_outcome"], "unavailable")

    def test_reward_risk_below_two_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "at least 2R"):
            build_directional_labels(
                self._frame(),
                risk_distance=pd.Series([1.0] * 7),
                config=DirectionalLabelConfig(takeProfitR=1.5),
            )


if __name__ == "__main__":
    unittest.main()
