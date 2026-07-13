from __future__ import annotations

import unittest
from collections import Counter

import numpy as np
import pandas as pd

from alphapilot.short_cycle.parameter_search import build_signal
from alphapilot.short_cycle.workflow_candidates import (
    redesigned_short_cycle_workflow_candidates,
)


class RedesignedShortCycleCandidateTests(unittest.TestCase):
    @staticmethod
    def _signal_frame(*, descending: bool = False) -> pd.DataFrame:
        size = 260
        if descending:
            ema20 = np.linspace(101.0, 99.0, size)
            ema50 = np.linspace(102.0, 100.0, size)
            ema200 = np.linspace(104.0, 102.0, size)
        else:
            ema20 = np.linspace(99.0, 100.0, size)
            ema50 = np.linspace(98.0, 99.0, size)
            ema200 = np.linspace(95.0, 96.0, size)
        return pd.DataFrame(
            {
                "open": np.full(size, 100.0),
                "high": np.full(size, 101.0),
                "low": np.full(size, 99.0),
                "close": np.full(size, 100.5),
                "ema20": ema20,
                "ema50": ema50,
                "ema200": ema200,
                "rsi14": np.full(size, 55.0),
                "atr14": np.full(size, 1.0),
                "volume_ratio": np.full(size, 1.5),
                "macd_hist": np.full(size, -0.1 if descending else 0.1),
                "bb_upper": np.full(size, 102.0),
                "bb_lower": np.full(size, 98.0),
                "bb_width": np.full(size, 0.04),
                "btc_long_block": np.zeros(size, dtype=bool),
                "btc_short_block": np.zeros(size, dtype=bool),
            }
        )

    def test_catalog_contains_three_5m_and_three_15m_candidates(self) -> None:
        items = redesigned_short_cycle_workflow_candidates()

        self.assertEqual(len(items), 6)
        self.assertEqual(Counter(item.timeframe for item in items), {"5m": 3, "15m": 3})
        self.assertEqual(len({item.familyKey for item in items}), 6)
        self.assertEqual(len({item.displayName for item in items}), 6)
        self.assertEqual(Counter(item.direction for item in items), {"long": 4, "short": 2})

    def test_candidates_keep_two_r_and_use_structural_filters(self) -> None:
        required = {
            "trend_pullback_confirmation_long": {
                "pullback_lookback",
                "ema_slope_lookback",
                "volume_min",
                "atr_pct_min",
                "atr_pct_max",
            },
            "compression_release_long": {
                "lookback",
                "squeeze_window",
                "squeeze_ratio",
                "expansion_min",
                "volume_min",
                "atr_pct_max",
            },
            "failed_reclaim_short": {
                "reclaim_lookback",
                "ema_slope_lookback",
                "volume_min",
                "atr_pct_min",
                "atr_pct_max",
            },
        }
        for item in redesigned_short_cycle_workflow_candidates():
            with self.subTest(candidate=item.displayName):
                definition = item.definition()
                self.assertEqual(definition["targetR"], 2.0)
                self.assertEqual(definition["exitPolicy"], "two_r_half_atr_runner_v1")
                self.assertEqual(definition["formalUniverseTarget"], 50)
                self.assertTrue(definition["researchOnly"])
                self.assertFalse(definition["executionEnabled"])
                self.assertTrue(required[item.signalFamily].issubset(item.parameters))

    def test_new_signal_families_are_supported_by_the_shared_engine(self) -> None:
        frame = self._signal_frame()

        for item in redesigned_short_cycle_workflow_candidates():
            with self.subTest(candidate=item.displayName):
                signal, direction = build_signal(frame, item.signalFamily, item.parameters)
                self.assertEqual(direction, item.direction)
                self.assertEqual(len(signal), len(frame))
                self.assertEqual(signal.dtype, bool)

    def test_structural_confirmations_can_trigger_and_low_volume_blocks_them(self) -> None:
        items = {item.signalFamily: item for item in redesigned_short_cycle_workflow_candidates()[:3]}

        pullback = self._signal_frame()
        pullback.loc[pullback.index[-1], ["open", "high", "low", "close"]] = [100.0, 102.2, 99.8, 102.0]
        pullback_signal, _ = build_signal(
            pullback,
            "trend_pullback_confirmation_long",
            items["trend_pullback_confirmation_long"].parameters,
        )
        self.assertTrue(bool(pullback_signal.iloc[-1]))

        compression = self._signal_frame()
        compression.loc[compression.index[-2], "bb_width"] = 0.02
        compression.loc[compression.index[-1], ["open", "high", "low", "close", "bb_width", "volume_ratio"]] = [
            100.0,
            102.2,
            99.8,
            102.0,
            0.03,
            2.0,
        ]
        compression_signal, _ = build_signal(
            compression,
            "compression_release_long",
            items["compression_release_long"].parameters,
        )
        self.assertTrue(bool(compression_signal.iloc[-1]))

        rejection = self._signal_frame(descending=True)
        rejection.loc[rejection.index[-1], ["open", "high", "low", "close"]] = [99.0, 100.0, 97.8, 98.0]
        rejection_signal, _ = build_signal(
            rejection,
            "failed_reclaim_short",
            items["failed_reclaim_short"].parameters,
        )
        self.assertTrue(bool(rejection_signal.iloc[-1]))

        for frame, family in (
            (pullback, "trend_pullback_confirmation_long"),
            (compression, "compression_release_long"),
            (rejection, "failed_reclaim_short"),
        ):
            frame.loc[frame.index[-1], "volume_ratio"] = 0.2
            filtered, _ = build_signal(frame, family, items[family].parameters)
            self.assertFalse(bool(filtered.iloc[-1]))

    def test_display_names_explain_the_setup(self) -> None:
        self.assertEqual(
            [item.displayName for item in redesigned_short_cycle_workflow_candidates()],
            [
                "5m 顺势回踩确认 ATR1.0",
                "5m 压缩放量释放 ATR1.1",
                "5m 弱势反抽失败 ATR1.0",
                "15m 顺势回踩确认 ATR1.2",
                "15m 压缩放量释放 ATR1.3",
                "15m 弱势反抽失败 ATR1.2",
            ],
        )


if __name__ == "__main__":
    unittest.main()
