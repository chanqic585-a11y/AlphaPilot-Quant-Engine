from __future__ import annotations

import unittest

import pandas as pd

from alphapilot.evolution.replay import ReplayConfig, ReplaySignal, run_historical_replay


class HistoricalReplayEngineTests(unittest.TestCase):
    def _frame(self, *, ambiguous: bool = False) -> pd.DataFrame:
        high_at_entry = 103.0
        low_at_entry = 98.5 if ambiguous else 99.5
        return pd.DataFrame(
            {
                "timestamp_ms": [0, 1, 2, 3, 4, 5],
                "open": [90.0, 100.0, 100.0, 100.0, 100.0, 100.0],
                "high": [91.0, high_at_entry, 101.0, 101.0, 101.0, 101.0],
                "low": [89.0, low_at_entry, 99.5, 99.5, 99.5, 99.5],
                "close": [90.0, 100.5, 100.5, 100.5, 100.5, 100.5],
            }
        )

    def _signal(self, signal_id: str = "signal_1", decision: int = 0) -> ReplaySignal:
        return ReplaySignal(
            signalId=signal_id,
            instrumentId="BTC-USDT-SWAP",
            timeframe="4h",
            direction="long",
            decisionTimestampMs=decision,
            riskDistance=1.0,
            sourceEntityId="probe_v1",
        )

    def test_next_bar_fill_target_and_excursion_metrics(self) -> None:
        result = run_historical_replay(
            [self._signal()],
            bars_by_instrument={"BTC-USDT-SWAP": self._frame()},
            config=ReplayConfig(maxHoldingBars=3, feeRate=0, slippageRate=0),
        )
        self.assertEqual(len(result.trades), 1)
        trade = result.trades[0]
        self.assertEqual(trade.entryTimestampMs, 1)
        self.assertEqual(trade.entryFillPrice, 100.0)
        self.assertEqual(trade.exitReason, "target")
        self.assertEqual(trade.grossR, 2.0)
        self.assertGreaterEqual(trade.mfeR, 2.0)
        self.assertGreater(trade.maeR, 0)
        self.assertFalse(trade.fundingDataAvailable)

    def test_same_bar_target_and_stop_is_conservatively_stopped(self) -> None:
        result = run_historical_replay(
            [self._signal()],
            bars_by_instrument={"BTC-USDT-SWAP": self._frame(ambiguous=True)},
            config=ReplayConfig(maxHoldingBars=3, feeRate=0, slippageRate=0),
        )
        trade = result.trades[0]
        self.assertEqual(trade.exitReason, "stop")
        self.assertEqual(trade.grossR, -1.0)
        self.assertTrue(trade.sameBarAmbiguous)

    def test_overlapping_same_instrument_signal_is_skipped(self) -> None:
        frame = self._frame()
        frame.loc[1, "high"] = 100.5
        first = self._signal("signal_1", 0)
        second = self._signal("signal_2", 1)
        result = run_historical_replay(
            [first, second],
            bars_by_instrument={"BTC-USDT-SWAP": frame},
            config=ReplayConfig(maxHoldingBars=3, feeRate=0, slippageRate=0),
        )
        self.assertEqual(len(result.trades), 1)
        self.assertEqual(len(result.skippedSignals), 1)
        self.assertEqual(
            result.skippedSignals[0].reason, "instrument_position_already_open"
        )

    def test_reward_risk_below_two_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "at least 2R"):
            run_historical_replay(
                [self._signal()],
                bars_by_instrument={"BTC-USDT-SWAP": self._frame()},
                config=ReplayConfig(takeProfitR=1.5),
            )


if __name__ == "__main__":
    unittest.main()
