from __future__ import annotations

import unittest
from collections import Counter

from alphapilot.short_cycle.workflow_candidates import (
    short_cycle_workflow_candidates,
)


REQUIRED_PARAMETERS = {
    "breakout_volume_long": {
        "lookback",
        "breakout_buffer",
        "rsi_max",
        "volume_min",
    },
    "ema_reclaim_long": {
        "trend_tolerance",
        "reclaim_buffer",
        "rsi_min",
        "rsi_max",
        "volume_min",
    },
    "mean_reversion_reclaim_long": {
        "rsi_low",
        "volume_min",
        "max_range_pct",
    },
    "short_breakdown_momentum": {
        "lookback",
        "trend_tolerance",
        "breakdown_buffer",
        "rsi_max",
        "volume_min",
    },
    "short_rejection": {
        "upper_buffer",
        "trend_tolerance",
        "rsi_high",
        "volume_min",
    },
    "momentum_continuation_long": {
        "trend_tolerance",
        "macd_tolerance",
        "rsi_min",
        "rsi_max",
        "volume_min",
    },
    "squeeze_breakout_long": {
        "lookback",
        "squeeze_window",
        "squeeze_ratio",
        "volume_min",
    },
}


class ShortCycleWorkflowCandidateTests(unittest.TestCase):
    def test_catalog_contains_ten_unique_candidates_split_five_and_five(self) -> None:
        items = short_cycle_workflow_candidates()

        self.assertEqual(len(items), 10)
        self.assertEqual(Counter(item.timeframe for item in items), {"5m": 5, "15m": 5})
        self.assertEqual(len({item.familyKey for item in items}), 10)
        self.assertEqual(len({item.displayName for item in items}), 10)
        self.assertEqual(Counter(item.direction for item in items), {"long": 6, "short": 4})

    def test_every_candidate_is_complete_two_r_dynamic_top50_research(self) -> None:
        for item in short_cycle_workflow_candidates():
            with self.subTest(candidate=item.displayName):
                definition = item.definition()
                self.assertEqual(definition["targetR"], 2.0)
                self.assertEqual(definition["signalEngine"], "short_cycle_v1")
                self.assertEqual(
                    definition["universePolicy"],
                    "point_in_time_dynamic_liquid_usdt_swap",
                )
                self.assertEqual(definition["formalUniverseTarget"], 50)
                self.assertTrue(definition["researchOnly"])
                self.assertFalse(definition["executionEnabled"])
                self.assertGreater(float(item.parameters["stop_atr"]), 0)
                self.assertGreater(int(item.parameters["max_hold"]), 0)
                self.assertTrue(
                    REQUIRED_PARAMETERS[item.signalFamily].issubset(item.parameters)
                )
                policy = definition["forwardSignalPolicy"]
                self.assertEqual(
                    policy["schemaVersion"], "short_cycle_forward_policy_v1"
                )
                self.assertEqual(policy["signalFamily"], item.signalFamily)
                self.assertEqual(policy["direction"], item.direction)
                self.assertEqual(policy["timeframe"], item.timeframe)
                self.assertEqual(policy["parameters"], item.parameters)

    def test_display_names_match_the_approved_candidate_pack(self) -> None:
        self.assertEqual(
            [item.displayName for item in short_cycle_workflow_candidates()],
            [
                "5m 放量突破延续 ATR1.2",
                "5m EMA20 回收反弹 ATR1.2",
                "5m 极端超卖收回 ATR1.2",
                "5m 跌破放量延续 ATR1.2",
                "5m 上影拒绝回落 ATR1.2",
                "15m 趋势动量延续 ATR1.4",
                "15m EMA20 回收反弹 ATR1.4",
                "15m 低波压缩突破 ATR1.4",
                "15m 跌破放量延续 ATR1.4",
                "15m 上影拒绝回落 ATR1.4",
            ],
        )


if __name__ == "__main__":
    unittest.main()
