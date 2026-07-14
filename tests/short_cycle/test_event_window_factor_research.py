from __future__ import annotations

import unittest

import pandas as pd

from alphapilot.short_cycle.event_window_factor_research import (
    enrich_trade_rows_with_factors,
    segment_factor_rows,
)


class EventWindowFactorResearchTests(unittest.TestCase):
    def test_enrichment_uses_closed_signal_bar_before_entry(self) -> None:
        dates = pd.date_range("2024-01-01", periods=20, freq="15min", tz="UTC")
        frame = pd.DataFrame(
            {
                "date": dates,
                "close": [100 + index for index in range(20)],
                "ema20": [100 + index for index in range(20)],
                "ema50": [99 + index for index in range(20)],
                "ema200": [98 + index for index in range(20)],
                "atr14": [2.0] * 20,
                "btc_ret_3": [0.01] * 20,
                "btc_trend20_50": [0.02] * 20,
                "btc_trend50_200": [0.03] * 20,
                "btc_slope20_12": [0.04] * 20,
            }
        )
        trades = [
            {
                "pair": "ETH/USDT:USDT",
                "entryDate": dates[13].isoformat(),
                "exitDate": dates[16].isoformat(),
                "netR": 0.5,
            }
        ]

        enriched = enrich_trade_rows_with_factors(
            frame,
            trades,
            direction="long",
            lookback=12,
        )

        self.assertEqual(1, len(enriched))
        self.assertAlmostEqual((112 / 100) - 1, enriched[0]["aligned_return"])
        self.assertEqual(0.02, enriched[0]["btc_trend20_50"])
        self.assertEqual(2.0 / 112, enriched[0]["atr_pct"])

    def test_short_direction_aligns_directional_factors(self) -> None:
        dates = pd.date_range("2024-01-01", periods=15, freq="1h", tz="UTC")
        frame = pd.DataFrame(
            {
                "date": dates,
                "close": [100 + index for index in range(15)],
                "ema20": [100 + index for index in range(15)],
                "ema50": [99 + index for index in range(15)],
                "ema200": [98 + index for index in range(15)],
                "atr14": [1.0] * 15,
                "btc_ret_3": [0.01] * 15,
                "btc_trend20_50": [0.02] * 15,
                "btc_trend50_200": [0.03] * 15,
                "btc_slope20_12": [0.04] * 15,
            }
        )
        trades = [
            {
                "pair": "ETH/USDT:USDT",
                "entryDate": dates[13].isoformat(),
                "exitDate": dates[14].isoformat(),
                "netR": 0.2,
            }
        ]

        enriched = enrich_trade_rows_with_factors(
            frame,
            trades,
            direction="short",
            lookback=12,
        )

        self.assertLess(enriched[0]["aligned_return"], 0)
        self.assertEqual(-0.02, enriched[0]["btc_trend20_50"])
        self.assertGreater(enriched[0]["atr_pct"], 0)

    def test_segmentation_excludes_rows_outside_declared_window(self) -> None:
        rows = [
            {
                "pair": "ETH/USDT:USDT",
                "entryDate": "2023-06-01T00:00:00+00:00",
                "exitDate": "2023-06-01T01:00:00+00:00",
            },
            {
                "pair": "ETH/USDT:USDT",
                "entryDate": "2025-06-01T00:00:00+00:00",
                "exitDate": "2025-06-01T01:00:00+00:00",
            },
        ]

        selected = segment_factor_rows(
            rows,
            pairs=("ETH/USDT:USDT",),
            start=pd.Timestamp("2023-01-01", tz="UTC"),
            end=pd.Timestamp("2024-01-01", tz="UTC"),
        )

        self.assertEqual(1, len(selected))
        self.assertEqual("2023-06-01T00:00:00+00:00", selected[0]["entryDate"])


if __name__ == "__main__":
    unittest.main()
