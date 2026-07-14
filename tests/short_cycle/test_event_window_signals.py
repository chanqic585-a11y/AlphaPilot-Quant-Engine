from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from alphapilot.short_cycle.event_window_candidates import event_window_candidate_pool
from alphapilot.short_cycle.event_window_signals import evaluate_event_window_signal
from alphapilot.short_cycle.parameter_search import build_signal, merge_btc_context


class EventWindowSignalTests(unittest.TestCase):
    @staticmethod
    def _frame(*, descending: bool = False) -> pd.DataFrame:
        size = 280
        if descending:
            close = np.linspace(110.0, 100.0, size)
            ema20 = close + 0.4
            ema50 = close + 1.2
            ema200 = close + 3.0
        else:
            close = np.linspace(90.0, 100.0, size)
            ema20 = close - 0.3
            ema50 = close - 1.2
            ema200 = close - 3.0
        return pd.DataFrame(
            {
                "open": close - (-0.2 if descending else 0.2),
                "high": close + 0.6,
                "low": close - 0.6,
                "close": close,
                "ema20": ema20,
                "ema50": ema50,
                "ema200": ema200,
                "rsi14": np.full(size, 54.0),
                "atr14": np.full(size, 0.8),
                "volume_ratio": np.full(size, 1.1),
                "macd_hist": np.full(size, -0.1 if descending else 0.1),
                "bb_upper": close + 2.0,
                "bb_lower": close - 2.0,
                "bb_width": np.full(size, 0.04),
                "btc_long_block": np.zeros(size, dtype=bool),
                "btc_short_block": np.zeros(size, dtype=bool),
            }
        )

    def test_pullback_setup_can_precede_confirmation_by_three_closed_candles(self) -> None:
        item = next(
            candidate
            for candidate in event_window_candidate_pool()
            if candidate.signalFamily == "windowed_trend_reclaim_long"
            and candidate.parameters["event_window"] == 3
        )
        frame = self._frame()
        event_index = frame.index[-3]
        frame.loc[event_index, "low"] = frame.loc[event_index, "ema20"] * 0.998
        frame.loc[event_index, "close"] = frame.loc[event_index, "ema20"] * 0.999
        frame.loc[frame.index[-1], ["open", "close", "high", "rsi14", "volume_ratio"]] = [
            99.4,
            100.4,
            100.6,
            58.0,
            1.4,
        ]
        frame.loc[frame.index[-2], "high"] = 100.2

        signal, direction = build_signal(frame, item.signalFamily, item.parameters)

        self.assertEqual(direction, "long")
        self.assertTrue(bool(signal.iloc[-1]))

        stale = frame.copy()
        stale.loc[event_index, ["low", "close"]] = [101.0, 101.0]
        stale_index = stale.index[-5]
        stale.loc[stale_index, "low"] = stale.loc[stale_index, "ema20"] * 0.998
        stale.loc[stale_index, "close"] = stale.loc[stale_index, "ema20"] * 0.999
        stale_signal, _ = build_signal(stale, item.signalFamily, item.parameters)
        self.assertFalse(bool(stale_signal.iloc[-1]))

    def test_near_miss_is_shadow_only_and_names_failed_checks(self) -> None:
        item = next(
            candidate
            for candidate in event_window_candidate_pool()
            if candidate.signalFamily == "windowed_trend_reclaim_long"
        )
        frame = self._frame()
        event_index = frame.index[-2]
        frame.loc[event_index, "low"] = frame.loc[event_index, "ema20"] * 0.998
        frame.loc[event_index, "close"] = frame.loc[event_index, "ema20"] * 0.999
        frame.loc[frame.index[-1], ["open", "close", "high", "rsi14", "volume_ratio"]] = [
            99.4,
            100.4,
            100.6,
            58.0,
            0.1,
        ]
        frame.loc[frame.index[-2], "high"] = 100.2

        evaluation = evaluate_event_window_signal(
            frame, item.signalFamily, item.parameters, max_shadow_failures=2
        )

        self.assertFalse(bool(evaluation.signal.iloc[-1]))
        self.assertTrue(bool(evaluation.nearMiss.iloc[-1]))
        self.assertIn("volume_guard", evaluation.failed_checks(-1))
        self.assertEqual(evaluation.executionIntentCount, 0)

    def test_scored_confirmation_allows_one_optional_check_to_fail(self) -> None:
        item = next(
            candidate
            for candidate in event_window_candidate_pool()
            if candidate.signalFamily == "windowed_trend_reclaim_long"
        )
        frame = self._frame()
        event_index = frame.index[-2]
        frame.loc[event_index, "low"] = frame.loc[event_index, "ema20"] * 0.998
        frame.loc[event_index, "close"] = frame.loc[event_index, "ema20"] * 0.999
        frame.loc[frame.index[-1], ["open", "close", "high", "rsi14", "volume_ratio"]] = [
            99.4,
            100.4,
            100.6,
            58.0,
            0.1,
        ]
        frame.loc[frame.index[-2], "high"] = 100.2
        parameters = {**item.parameters, "minimum_optional_checks": 4}

        evaluation = evaluate_event_window_signal(
            frame, item.signalFamily, parameters
        )

        self.assertTrue(bool(evaluation.signal.iloc[-1]))
        self.assertIn("volume_guard", evaluation.failed_checks(-1))

    def test_scored_confirmation_never_bypasses_required_event(self) -> None:
        item = next(
            candidate
            for candidate in event_window_candidate_pool()
            if candidate.signalFamily == "windowed_trend_reclaim_long"
        )
        frame = self._frame()
        parameters = {**item.parameters, "minimum_optional_checks": 0}

        evaluation = evaluate_event_window_signal(
            frame, item.signalFamily, parameters
        )

        self.assertFalse(bool(evaluation.signal.iloc[-1]))
        self.assertIn("event_window", evaluation.failed_checks(-1))

    def test_upper_band_rejection_uses_a_five_candle_setup_window(self) -> None:
        frame = self._frame(descending=True)
        frame["btc_ret_3"] = 0.0
        event_index = frame.index[-5]
        frame.loc[event_index, "high"] = frame.loc[event_index, "bb_upper"] * 1.001
        frame.loc[event_index, "rsi14"] = 66.0
        frame.loc[frame.index[-2], "rsi14"] = 58.0
        frame.loc[frame.index[-1], ["open", "close", "rsi14", "volume_ratio"]] = [
            100.4,
            99.8,
            54.0,
            1.1,
        ]
        parameters = {
            "event_window": 5,
            "upper_buffer": 0.006,
            "trend_tolerance": 1.01,
            "rsi_high": 60,
            "rsi_reversal_max": 60,
            "volume_min": 0.8,
            "volume_max": 3.5,
            "atr_pct_min": 0.003,
            "atr_pct_max": 0.08,
            "btc_shock_threshold": 0.03,
            "minimum_optional_checks": 2,
        }

        evaluation = evaluate_event_window_signal(
            frame, "windowed_upper_band_rejection_short", parameters
        )

        self.assertTrue(bool(evaluation.signal.iloc[-1]))
        self.assertEqual(float(evaluation.eventAge.iloc[-1]), 4.0)

    def test_upper_band_rejection_ignores_stale_setup(self) -> None:
        frame = self._frame(descending=True)
        frame["btc_ret_3"] = 0.0
        event_index = frame.index[-7]
        frame.loc[event_index, "high"] = frame.loc[event_index, "bb_upper"] * 1.001
        frame.loc[event_index, "rsi14"] = 66.0
        frame.loc[frame.index[-1], ["open", "close", "rsi14", "volume_ratio"]] = [
            100.4,
            99.8,
            54.0,
            1.1,
        ]
        parameters = {
            "event_window": 5,
            "upper_buffer": 0.006,
            "trend_tolerance": 1.01,
            "rsi_high": 60,
            "rsi_reversal_max": 60,
            "volume_min": 0.8,
            "volume_max": 3.5,
            "atr_pct_min": 0.003,
            "atr_pct_max": 0.08,
            "btc_shock_threshold": 0.03,
            "minimum_optional_checks": 2,
        }

        evaluation = evaluate_event_window_signal(
            frame, "windowed_upper_band_rejection_short", parameters
        )

        self.assertFalse(bool(evaluation.signal.iloc[-1]))
        self.assertIn("event_window", evaluation.failed_checks(-1))

    def test_timeframe_specific_btc_threshold_can_allow_non_shock_move(self) -> None:
        item = next(
            candidate
            for candidate in event_window_candidate_pool()
            if candidate.signalFamily == "windowed_trend_reclaim_long"
        )
        frame = self._frame()
        event_index = frame.index[-2]
        frame.loc[event_index, "low"] = frame.loc[event_index, "ema20"] * 0.998
        frame.loc[event_index, "close"] = frame.loc[event_index, "ema20"] * 0.999
        frame.loc[frame.index[-1], ["open", "close", "high", "rsi14", "volume_ratio"]] = [
            99.4,
            100.4,
            100.6,
            58.0,
            1.4,
        ]
        frame.loc[frame.index[-2], "high"] = 100.2
        frame["btc_ret_3"] = -0.02
        frame["btc_long_block"] = True
        parameters = {**item.parameters, "btc_shock_threshold": 0.04}

        evaluation = evaluate_event_window_signal(
            frame, item.signalFamily, parameters
        )

        self.assertTrue(bool(evaluation.signal.iloc[-1]))

    def test_btc_guard_blocks_a_valid_event(self) -> None:
        item = next(
            candidate
            for candidate in event_window_candidate_pool()
            if candidate.signalFamily == "windowed_trend_reclaim_long"
        )
        frame = self._frame()
        event_index = frame.index[-2]
        frame.loc[event_index, "low"] = frame.loc[event_index, "ema20"] * 0.998
        frame.loc[event_index, "close"] = frame.loc[event_index, "ema20"] * 0.999
        frame.loc[frame.index[-1], ["open", "close", "high", "rsi14", "volume_ratio"]] = [
            99.4,
            100.4,
            100.6,
            58.0,
            1.4,
        ]
        frame.loc[frame.index[-2], "high"] = 100.2
        frame.loc[frame.index[-1], "btc_long_block"] = True

        signal, _ = build_signal(frame, item.signalFamily, item.parameters)

        self.assertFalse(bool(signal.iloc[-1]))

    def test_learned_factor_guard_is_explicit_and_blocks_out_of_regime_event(self) -> None:
        item = next(
            candidate
            for candidate in event_window_candidate_pool()
            if candidate.signalFamily == "windowed_trend_reclaim_long"
            and candidate.parameters["event_window"] == 3
        )
        frame = self._frame()
        event_index = frame.index[-3]
        frame.loc[event_index, "low"] = frame.loc[event_index, "ema20"] * 0.998
        frame.loc[event_index, "close"] = frame.loc[event_index, "ema20"] * 0.999
        frame.loc[frame.index[-1], ["open", "close", "high", "rsi14", "volume_ratio"]] = [
            99.4,
            100.4,
            100.6,
            58.0,
            1.4,
        ]
        frame.loc[frame.index[-2], "high"] = 100.2
        parameters = {
            **item.parameters,
            "factor_lookback": 12,
            "aligned_trend20_50_min": 0.05,
        }

        evaluation = evaluate_event_window_signal(
            frame, item.signalFamily, parameters
        )

        self.assertFalse(bool(evaluation.signal.iloc[-1]))
        self.assertIn("learned_factor_guard", evaluation.failed_checks(-1))

    def test_adaptive_factor_quantile_uses_prior_closed_candles(self) -> None:
        item = next(
            candidate
            for candidate in event_window_candidate_pool()
            if candidate.signalFamily == "windowed_trend_reclaim_long"
            and candidate.parameters["event_window"] == 3
        )
        frame = self._frame()
        frame["atr14"] = np.linspace(0.4, 0.8, len(frame))
        event_index = frame.index[-3]
        frame.loc[event_index, "low"] = frame.loc[event_index, "ema20"] * 0.998
        frame.loc[event_index, "close"] = frame.loc[event_index, "ema20"] * 0.999
        frame.loc[frame.index[-1], ["open", "close", "high", "rsi14", "volume_ratio", "atr14"]] = [
            99.4,
            100.4,
            100.6,
            58.0,
            1.4,
            1.2,
        ]
        frame.loc[frame.index[-2], "high"] = 100.2
        parameters = {
            **item.parameters,
            "adaptive_factor_window": 40,
            "atr_pct_quantile_min": 0.8,
        }

        strong = evaluate_event_window_signal(frame, item.signalFamily, parameters)
        weak_frame = frame.copy()
        weak_frame.loc[weak_frame.index[-1], "atr14"] = 0.3
        weak = evaluate_event_window_signal(
            weak_frame, item.signalFamily, parameters
        )

        self.assertTrue(bool(strong.signal.iloc[-1]))
        self.assertFalse(bool(weak.signal.iloc[-1]))
        self.assertIn("learned_factor_guard", weak.failed_checks(-1))

    def test_btc_context_exposes_transparent_trend_features(self) -> None:
        frame = self._frame()
        frame.insert(0, "date", pd.date_range("2024-01-01", periods=len(frame), freq="5min", tz="UTC"))
        btc = frame.loc[:, ["date", "close"]].copy()
        btc["close"] = np.linspace(80.0, 120.0, len(btc))

        merged = merge_btc_context(frame, btc)

        self.assertIn("btc_trend20_50", merged)
        self.assertIn("btc_trend50_200", merged)
        self.assertIn("btc_slope20_12", merged)
        self.assertGreater(float(merged["btc_trend20_50"].iloc[-1]), 0)
        self.assertGreater(float(merged["btc_slope20_12"].iloc[-1]), 0)

    def test_btc_trend_factor_guard_blocks_out_of_regime_event(self) -> None:
        item = next(
            candidate
            for candidate in event_window_candidate_pool()
            if candidate.signalFamily == "windowed_trend_reclaim_long"
            and candidate.parameters["event_window"] == 3
        )
        frame = self._frame()
        event_index = frame.index[-3]
        frame.loc[event_index, "low"] = frame.loc[event_index, "ema20"] * 0.998
        frame.loc[event_index, "close"] = frame.loc[event_index, "ema20"] * 0.999
        frame.loc[frame.index[-1], ["open", "close", "high", "rsi14", "volume_ratio"]] = [
            99.4,
            100.4,
            100.6,
            58.0,
            1.4,
        ]
        frame.loc[frame.index[-2], "high"] = 100.2
        frame["btc_trend50_200"] = 0.01
        parameters = {**item.parameters, "btc_trend50_200_min": 0.5}

        evaluation = evaluate_event_window_signal(
            frame, item.signalFamily, parameters
        )

        self.assertFalse(bool(evaluation.signal.iloc[-1]))
        self.assertIn("learned_factor_guard", evaluation.failed_checks(-1))


if __name__ == "__main__":
    unittest.main()
