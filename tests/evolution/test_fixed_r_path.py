from __future__ import annotations

import unittest
from unittest.mock import patch

import pandas as pd

from alphapilot.evolution.evaluation.fixed_r_path import (
    FixedRPathConfig,
    evaluate_fixed_r_path,
)
from alphapilot.reports.generate_v13_5_23_alpha191_crypto_subset_replay_report import (
    build_alpha191_observer_signals,
)


def bars(rows: list[tuple[int, float, float, float, float]]) -> pd.DataFrame:
    return pd.DataFrame(
        rows,
        columns=["timestamp_ms", "open", "high", "low", "close"],
    )


class FixedRPathTests(unittest.TestCase):
    def config(self, **overrides: object) -> FixedRPathConfig:
        values = {
            "stopLossPct": 0.05,
            "targetR": 2.0,
            "horizonBars": 3,
            "feeRate": 0.0,
            "slippageRate": 0.0,
            "latencyBars": 0,
            "slippageMultiplier": 1.0,
        }
        values.update(overrides)
        return FixedRPathConfig(**values)

    def test_long_and_short_target_use_next_bar_entry(self) -> None:
        long_result = evaluate_fixed_r_path(
            signalTimestampMs=0,
            direction="long",
            executionFrame=bars(
                [(1, 100, 101, 99, 100), (2, 100, 111, 99, 109)]
            ),
            config=self.config(),
        )
        short_result = evaluate_fixed_r_path(
            signalTimestampMs=0,
            direction="short",
            executionFrame=bars(
                [(1, 100, 101, 99, 100), (2, 100, 101, 89, 91)]
            ),
            config=self.config(),
        )

        self.assertEqual(long_result.entryTimestampMs, 1)
        self.assertEqual(long_result.exitReason, "target")
        self.assertAlmostEqual(long_result.grossR, 2.0)
        self.assertEqual(short_result.exitReason, "target")
        self.assertAlmostEqual(short_result.grossR, 2.0)

    def test_stop_first_gap_stop_time_exit_and_latency_are_conservative(self) -> None:
        both_hit = evaluate_fixed_r_path(
            signalTimestampMs=0,
            direction="long",
            executionFrame=bars([(1, 100, 111, 94, 100)]),
            config=self.config(),
        )
        gap_stop = evaluate_fixed_r_path(
            signalTimestampMs=0,
            direction="long",
            executionFrame=bars(
                [(1, 100, 102, 98, 100), (2, 90, 92, 88, 91)]
            ),
            config=self.config(),
        )
        timed = evaluate_fixed_r_path(
            signalTimestampMs=0,
            direction="long",
            executionFrame=bars(
                [(1, 100, 103, 98, 101), (2, 101, 104, 99, 102)]
            ),
            config=self.config(horizonBars=2),
        )
        delayed = evaluate_fixed_r_path(
            signalTimestampMs=0,
            direction="long",
            executionFrame=bars(
                [(1, 100, 101, 99, 100), (2, 105, 106, 104, 105)]
            ),
            config=self.config(latencyBars=1),
        )

        self.assertEqual(both_hit.exitReason, "stop_both_hit")
        self.assertAlmostEqual(both_hit.grossR, -1.0)
        self.assertEqual(gap_stop.exitReason, "stop_gap")
        self.assertLess(gap_stop.grossR, -1.0)
        self.assertEqual(timed.exitReason, "time")
        self.assertAlmostEqual(timed.grossR, 0.4)
        self.assertEqual(delayed.entryTimestampMs, 2)

    def test_fee_funding_and_stressed_slippage_reduce_net_r(self) -> None:
        frame = bars([(1, 100, 101, 99, 100), (2, 100, 111, 99, 109)])
        funding = pd.DataFrame(
            {"timestamp_ms": [1, 2], "funding_rate": [0.0001, 0.0001]}
        )
        baseline = evaluate_fixed_r_path(
            signalTimestampMs=0,
            direction="long",
            executionFrame=frame,
            config=self.config(feeRate=0.0005, slippageRate=0.0002),
            fundingFrame=funding,
        )
        stressed = evaluate_fixed_r_path(
            signalTimestampMs=0,
            direction="long",
            executionFrame=frame,
            config=self.config(
                feeRate=0.0005,
                slippageRate=0.0002,
                slippageMultiplier=2.0,
            ),
            fundingFrame=funding,
        )

        self.assertGreater(baseline.feeR, 0)
        self.assertGreater(baseline.fundingR, 0)
        self.assertGreater(stressed.slippageR, baseline.slippageR)
        self.assertLess(stressed.netR, baseline.netR)

    def test_public_signal_builder_has_no_label_or_future_path_dependency(self) -> None:
        frame = pd.DataFrame(
            [
                {
                    "date": pd.Timestamp("2025-01-01", tz="UTC"),
                    "pair": "BTC/USDT:USDT",
                    "timeframe": "4h",
                    "hr_short_blowoff_reversal": True,
                    "direction": "ignored",
                    "a191_short_exhaustion_pressure": 0.3,
                    "a191_liquidity_range_quality": 0.5,
                    "volume_ratio": 3.0,
                    "a191_return_volume_corr_24": 0.0,
                },
                {
                    "date": pd.Timestamp("2025-01-01 04:00", tz="UTC"),
                    "pair": "BTC/USDT:USDT",
                    "timeframe": "4h",
                    "hr_short_blowoff_reversal": False,
                    "a191_short_exhaustion_pressure": 999.0,
                    "a191_liquidity_range_quality": 999.0,
                    "volume_ratio": 999.0,
                    "a191_return_volume_corr_24": 999.0,
                    "future_return": 999.0,
                },
            ]
        )
        identity = lambda value: value
        with patch(
            "alphapilot.reports.generate_v13_5_23_alpha191_crypto_subset_replay_report.add_alpha101_style_factors",
            side_effect=identity,
        ), patch(
            "alphapilot.reports.generate_v13_5_23_alpha191_crypto_subset_replay_report.add_alpha191_crypto_safe_factors",
            side_effect=identity,
        ), patch(
            "alphapilot.reports.generate_v13_5_23_alpha191_crypto_subset_replay_report.add_high_reward_event_setups",
            side_effect=identity,
        ):
            first = build_alpha191_observer_signals(
                frame, overlay_id="a191_short_exhaustion_quality_v01"
            )
            changed = frame.copy()
            changed.loc[1, "future_return"] = -999.0
            second = build_alpha191_observer_signals(
                changed, overlay_id="a191_short_exhaustion_quality_v01"
            )

        pd.testing.assert_frame_equal(first, second)
        self.assertEqual(len(first), 1)
        self.assertNotIn("future_return", first.columns)
        self.assertNotIn("label", first.columns)
        self.assertEqual(first.iloc[0]["direction"], "short")


if __name__ == "__main__":
    unittest.main()
