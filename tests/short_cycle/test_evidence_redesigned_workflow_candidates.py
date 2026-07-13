from __future__ import annotations

import unittest
from collections import Counter

import numpy as np
import pandas as pd

from alphapilot.short_cycle.parameter_search import build_signal
from alphapilot.short_cycle.workflow_candidates import (
    evidence_redesigned_short_cycle_workflow_candidates,
)


class EvidenceRedesignedShortCycleCandidateTests(unittest.TestCase):
    @staticmethod
    def _frame(*, descending: bool = False) -> pd.DataFrame:
        size = 280
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
                "close": np.full(size, 100.0),
                "ema20": ema20,
                "ema50": ema50,
                "ema200": ema200,
                "rsi14": np.full(size, 55.0),
                "atr14": np.full(size, 1.0),
                "volume_ratio": np.full(size, 1.0),
                "macd_hist": np.full(size, -0.1 if descending else 0.1),
                "bb_upper": np.full(size, 102.0),
                "bb_lower": np.full(size, 98.0),
                "bb_width": np.full(size, 0.04),
                "btc_long_block": np.zeros(size, dtype=bool),
                "btc_short_block": np.zeros(size, dtype=bool),
            }
        )

    def test_catalog_contains_three_candidates_per_timeframe(self) -> None:
        items = evidence_redesigned_short_cycle_workflow_candidates()

        self.assertEqual(len(items), 6)
        self.assertEqual(Counter(item.timeframe for item in items), {"5m": 3, "15m": 3})
        self.assertEqual(Counter(item.direction for item in items), {"long": 4, "short": 2})
        self.assertEqual(len({item.familyKey for item in items}), 6)
        self.assertEqual(len({item.displayName for item in items}), 6)

    def test_candidates_are_research_only_two_r_event_setups(self) -> None:
        expected_families = {
            "liquidity_sweep_reclaim_long",
            "breakout_retest_continuation_long",
            "failed_breakout_reversal_short",
        }

        for item in evidence_redesigned_short_cycle_workflow_candidates():
            with self.subTest(candidate=item.displayName):
                definition = item.definition()
                self.assertIn(item.signalFamily, expected_families)
                self.assertEqual(definition["targetR"], 2.0)
                self.assertEqual(definition["exitPolicy"], "two_r_half_atr_runner_v1")
                self.assertEqual(definition["formalUniverseTarget"], 50)
                self.assertTrue(definition["researchOnly"])
                self.assertFalse(definition["executionEnabled"])

    def test_event_families_trigger_once_and_volume_or_btc_guard_blocks(self) -> None:
        items = {
            item.signalFamily: item
            for item in evidence_redesigned_short_cycle_workflow_candidates()[:3]
        }

        sweep = self._frame()
        sweep.loc[sweep.index[-2], ["open", "high", "low", "close", "rsi14"]] = [
            99.4,
            99.8,
            98.6,
            98.8,
            33.0,
        ]
        sweep.loc[sweep.index[-1], ["open", "high", "low", "close", "rsi14", "volume_ratio"]] = [
            99.1,
            100.5,
            99.0,
            100.2,
            40.0,
            2.0,
        ]

        retest = self._frame()
        retest.loc[retest.index[-2], ["open", "high", "low", "close", "volume_ratio"]] = [
            100.2,
            101.6,
            100.1,
            101.4,
            2.2,
        ]
        retest.loc[retest.index[-1], ["open", "high", "low", "close", "rsi14", "volume_ratio"]] = [
            101.0,
            101.5,
            100.9,
            101.3,
            58.0,
            1.0,
        ]

        rejection = self._frame(descending=True)
        rejection.loc[rejection.index[-2], ["open", "high", "low", "close", "rsi14"]] = [
            100.4,
            101.4,
            100.2,
            101.1,
            70.0,
        ]
        rejection.loc[rejection.index[-1], ["open", "high", "low", "close", "rsi14", "volume_ratio"]] = [
            101.1,
            101.2,
            100.0,
            100.6,
            60.0,
            2.0,
        ]

        for frame, family in (
            (sweep, "liquidity_sweep_reclaim_long"),
            (retest, "breakout_retest_continuation_long"),
            (rejection, "failed_breakout_reversal_short"),
        ):
            with self.subTest(family=family):
                item = items[family]
                signal, direction = build_signal(frame, family, item.parameters)
                self.assertEqual(direction, item.direction)
                self.assertTrue(bool(signal.iloc[-1]))
                self.assertEqual(int(signal.sum()), 1)

                frame.loc[frame.index[-1], "volume_ratio"] = 0.1
                low_volume, _ = build_signal(frame, family, item.parameters)
                self.assertFalse(bool(low_volume.iloc[-1]))

                frame.loc[frame.index[-1], "volume_ratio"] = 2.0
                block_column = "btc_short_block" if item.direction == "short" else "btc_long_block"
                frame.loc[frame.index[-1], block_column] = True
                blocked, _ = build_signal(frame, family, item.parameters)
                self.assertFalse(bool(blocked.iloc[-1]))


if __name__ == "__main__":
    unittest.main()
