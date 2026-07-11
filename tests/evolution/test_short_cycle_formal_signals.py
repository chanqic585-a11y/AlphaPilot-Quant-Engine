from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from alphapilot.evolution.evaluation.short_cycle_signals import (
    build_short_cycle_formal_signals,
)


def make_frame(
    instrument: str,
    *,
    timeframe: str = "5m",
    crash_final: bool = False,
) -> pd.DataFrame:
    interval = 300_000 if timeframe == "5m" else 900_000
    timestamps = np.arange(260, dtype="int64") * interval + 1_700_000_000_000
    close = 100.0 + np.sin(np.arange(260) / 6.0) * 0.1
    close[-1] = 94.0 if crash_final else 102.0
    frame = pd.DataFrame(
        {
            "timestamp_ms": timestamps,
            "date": pd.to_datetime(timestamps, unit="ms", utc=True),
            "open": close - 0.05,
            "high": close + 0.2,
            "low": close - 0.2,
            "close": close,
            "volume": np.full(260, 100.0),
            "confirmed": np.ones(260, dtype="int64"),
            "instrument_id": instrument,
            "timeframe": timeframe,
        }
    )
    frame.loc[frame.index[-1], "volume"] = 250.0
    return frame


class ShortCycleFormalSignalTests(unittest.TestCase):
    def parameters(self) -> dict:
        return {
            "lookback": 20,
            "breakout_buffer": 0.0,
            "rsi_max": 100,
            "volume_min": 1.1,
            "stop_atr": 1.2,
            "max_hold": 24,
        }

    def test_builds_one_completed_signal_with_signal_bar_atr_stop(self) -> None:
        btc = make_frame("BTC-USDT-SWAP")
        eth = make_frame("ETH-USDT-SWAP")

        signals = build_short_cycle_formal_signals(
            {"BTC-USDT-SWAP": btc, "ETH-USDT-SWAP": eth},
            signal_timeframe="5m",
            family="breakout_volume_long",
            expected_direction="long",
            parameters=self.parameters(),
        )

        eth_signal = signals.loc[signals["pair"] == "ETH/USDT:USDT"].iloc[-1]
        source_timestamp = int(eth["timestamp_ms"].iloc[-1])
        self.assertEqual(int(eth_signal["sourceTimestampMs"]), source_timestamp)
        self.assertEqual(int(eth_signal["signalTimestampMs"]), source_timestamp + 300_000 - 1)
        self.assertEqual(int(eth_signal["signalIndex"]), 259)
        self.assertEqual(eth_signal["direction"], "long")
        self.assertGreater(float(eth_signal["stopLossPct"]), 0)

    def test_15m_signal_uses_the_completed_15m_boundary(self) -> None:
        btc = make_frame("BTC-USDT-SWAP", timeframe="15m")
        eth = make_frame("ETH-USDT-SWAP", timeframe="15m")

        signals = build_short_cycle_formal_signals(
            {"BTC-USDT-SWAP": btc, "ETH-USDT-SWAP": eth},
            signal_timeframe="15m",
            family="breakout_volume_long",
            expected_direction="long",
            parameters=self.parameters(),
        )

        row = signals.loc[signals["pair"] == "ETH/USDT:USDT"].iloc[-1]
        self.assertEqual(
            int(row["signalTimestampMs"]),
            int(row["sourceTimestampMs"]) + 900_000 - 1,
        )

    def test_btc_crash_blocks_long_signal(self) -> None:
        signals = build_short_cycle_formal_signals(
            {
                "BTC-USDT-SWAP": make_frame("BTC-USDT-SWAP", crash_final=True),
                "ETH-USDT-SWAP": make_frame("ETH-USDT-SWAP"),
            },
            signal_timeframe="5m",
            family="breakout_volume_long",
            expected_direction="long",
            parameters=self.parameters(),
        )

        self.assertNotIn("ETH/USDT:USDT", set(signals["pair"]))

    def test_missing_btc_unknown_family_and_direction_mismatch_fail_closed(self) -> None:
        eth = make_frame("ETH-USDT-SWAP")
        with self.assertRaisesRegex(ValueError, "short_cycle_btc_context_missing"):
            build_short_cycle_formal_signals(
                {"ETH-USDT-SWAP": eth},
                signal_timeframe="5m",
                family="breakout_volume_long",
                expected_direction="long",
                parameters=self.parameters(),
            )
        with self.assertRaisesRegex(ValueError, "short_cycle_signal_family_not_supported"):
            build_short_cycle_formal_signals(
                {"BTC-USDT-SWAP": make_frame("BTC-USDT-SWAP")},
                signal_timeframe="5m",
                family="not-a-family",
                expected_direction="long",
                parameters=self.parameters(),
            )
        with self.assertRaisesRegex(ValueError, "short_cycle_signal_direction_mismatch"):
            build_short_cycle_formal_signals(
                {
                    "BTC-USDT-SWAP": make_frame("BTC-USDT-SWAP"),
                    "ETH-USDT-SWAP": eth,
                },
                signal_timeframe="5m",
                family="breakout_volume_long",
                expected_direction="short",
                parameters=self.parameters(),
            )


if __name__ == "__main__":
    unittest.main()
