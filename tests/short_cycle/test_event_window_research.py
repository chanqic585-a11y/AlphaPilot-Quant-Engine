from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from alphapilot.short_cycle.event_window_candidates import (
    event_window_learned_candidate_pool,
)
from alphapilot.short_cycle.event_window_research import (
    EventWindowPrescreenConfig,
    _load_frames,
    _load_raw_frame,
    latest_canonical_partition,
    prescreen_robustness_reasons,
    run_event_window_prescreen,
)


class EventWindowResearchTests(unittest.TestCase):
    def test_robustness_rejects_narrow_pair_breadth(self) -> None:
        narrow_metrics = {
            "tradeCount": 40,
            "expectancyR": 0.1,
            "profitFactor": 1.2,
            "largestPairShare": 0.25,
            "pairMetrics": {
                "A/USDT:USDT": {"expectancyR": 0.4},
                "B/USDT:USDT": {"expectancyR": -0.1},
                "C/USDT:USDT": {"expectancyR": -0.1},
                "D/USDT:USDT": {"expectancyR": -0.1},
            },
        }

        reasons = prescreen_robustness_reasons(
            {
                "derivationTrain": narrow_metrics,
                "derivationValidation": narrow_metrics,
                "symbolHoldback": narrow_metrics,
            }
        )

        self.assertIn("symbol_holdback_positive_pair_share_below_50pct", reasons)

    @staticmethod
    def _write_partition(
        root: Path,
        instrument: str,
        timeframe: str,
        start: str,
        periods: int,
        frequency: str,
    ) -> Path:
        dates = pd.date_range(start, periods=periods, freq=frequency, tz="UTC")
        close = np.linspace(90.0, 110.0, periods)
        frame = pd.DataFrame(
            {
                "timestamp_ms": [int(value.timestamp() * 1000) for value in dates],
                "date": dates,
                "open": close - 0.1,
                "high": close + 0.4,
                "low": close - 0.4,
                "close": close,
                "volume": np.full(periods, 1000.0),
                "confirmed": np.ones(periods, dtype=int),
                "instrument_id": instrument,
                "timeframe": timeframe,
            }
        )
        directory = root / instrument / timeframe
        directory.mkdir(parents=True, exist_ok=True)
        first = int(frame["timestamp_ms"].iloc[0])
        last = int(frame["timestamp_ms"].iloc[-1])
        path = directory / f"{first}-{last}-test.parquet"
        frame.to_parquet(path, index=False)
        return path

    def test_latest_partition_must_cover_the_requested_window(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            full = self._write_partition(
                root, "BTC-USDT-SWAP", "15m", "2021-12-01", 120_000, "15min"
            )
            self._write_partition(
                root, "BTC-USDT-SWAP", "15m", "2025-01-01", 100, "15min"
            )

            selected = latest_canonical_partition(
                root,
                "BTC-USDT-SWAP",
                "15m",
                required_start=pd.Timestamp("2022-01-01", tz="UTC"),
                required_end=pd.Timestamp("2025-01-01", tz="UTC"),
            )

            self.assertEqual(selected, full)

    def test_holdback_failure_prevents_prescreen_eligibility(self) -> None:
        reasons = prescreen_robustness_reasons(
            {
                "derivationTrain": {
                    "tradeCount": 80,
                    "profitFactor": 1.2,
                    "expectancyR": 0.08,
                },
                "derivationValidation": {
                    "tradeCount": 35,
                    "profitFactor": 1.1,
                    "expectancyR": 0.04,
                },
                "symbolHoldback": {
                    "tradeCount": 30,
                    "profitFactor": 0.8,
                    "expectancyR": -0.12,
                },
            }
        )

        self.assertIn("symbol_holdback_expectancy_not_positive", reasons)
        self.assertIn("symbol_holdback_profit_factor_not_above_one", reasons)

    def test_runner_records_rejected_candidate_without_promoting_it(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "canonical"
            output = Path(temp) / "report.json"
            for instrument in ("BTC-USDT-SWAP", "ETH-USDT-SWAP"):
                self._write_partition(
                    root, instrument, "15m", "2021-12-20", 36_000, "15min"
                )
            candidate = next(
                item
                for item in event_window_learned_candidate_pool()
                if item.timeframe == "15m"
            )
            config = EventWindowPrescreenConfig(
                canonicalRoot=root,
                derivationSymbols=("BTC-USDT-SWAP",),
                holdbackSymbols=("ETH-USDT-SWAP",),
                trainStart="2022-01-01",
                trainEnd="2022-06-01",
                validationEnd="2022-12-01",
                outputPath=output,
            )

            report = run_event_window_prescreen((candidate,), config)

            self.assertEqual(report["status"], "completed")
            self.assertEqual(report["eligibleCandidateKeys"], [])
            self.assertEqual(report["results"][0]["candidateKey"], candidate.familyKey)
            self.assertFalse(report["results"][0]["eligible"])
            self.assertTrue(report["results"][0]["rejectionReasons"])
            holdback_metrics = report["results"][0]["segmentMetrics"]["symbolHoldback"]
            self.assertIn("pairMetrics", holdback_metrics)
            self.assertIn("ETH/USDT:USDT", holdback_metrics["pairMetrics"])
            self.assertTrue(output.is_file())

    def test_loader_adds_btc_context_without_evaluating_btc_as_a_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "canonical"
            for instrument in (
                "BTC-USDT-SWAP",
                "ETH-USDT-SWAP",
                "SOL-USDT-SWAP",
            ):
                self._write_partition(
                    root, instrument, "5m", "2021-12-20", 120_000, "5min"
                )
            config = EventWindowPrescreenConfig(
                canonicalRoot=root,
                derivationSymbols=("ETH-USDT-SWAP",),
                holdbackSymbols=("SOL-USDT-SWAP",),
                trainStart="2022-01-01",
                trainEnd="2022-06-01",
                validationEnd="2022-12-01",
            )

            frames, sources = _load_frames(config, "5m")

            self.assertEqual(set(frames), {"ETH-USDT-SWAP", "SOL-USDT-SWAP"})
            self.assertIn("BTC-USDT-SWAP", sources)
            self.assertIn("btc_trend50_200", frames["ETH-USDT-SWAP"])
            self.assertTrue(frames["ETH-USDT-SWAP"]["btc_ret_3"].notna().any())

    def test_loader_resamples_four_closed_15m_candles_into_one_1h_candle(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "canonical"
            path = self._write_partition(
                root, "BTC-USDT-SWAP", "15m", "2021-11-01", 10_000, "15min"
            )
            source = pd.read_parquet(path)
            source.loc[source.index[-1], "confirmed"] = 0
            source.to_parquet(path, index=False)
            config = EventWindowPrescreenConfig(
                canonicalRoot=root,
                derivationSymbols=("BTC-USDT-SWAP",),
                holdbackSymbols=(),
                trainStart="2022-01-01",
                trainEnd="2022-01-15",
                validationEnd="2022-02-01",
            )

            frame, selected_source = _load_raw_frame(
                config, "BTC-USDT-SWAP", "1h"
            )

            self.assertIn("/15m/", selected_source)
            self.assertTrue((frame["date"].dt.minute == 0).all())
            self.assertTrue((frame["confirmed"] == 1).all())
            first_hour = frame.iloc[0]
            first_source = source[
                (source["date"] >= first_hour.date)
                & (source["date"] < first_hour.date + pd.Timedelta(hours=1))
            ]
            self.assertEqual(len(first_source), 4)
            self.assertAlmostEqual(first_hour.open, first_source.iloc[0].open)
            self.assertAlmostEqual(first_hour.high, first_source.high.max())
            self.assertAlmostEqual(first_hour.low, first_source.low.min())
            self.assertAlmostEqual(first_hour.close, first_source.iloc[-1].close)
            self.assertAlmostEqual(first_hour.volume, first_source.volume.sum())

    def test_loader_reads_direct_4h_partition_without_resampling(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "canonical"
            self._write_partition(
                root, "BTC-USDT-SWAP", "4h", "2021-10-01", 1_000, "4h"
            )
            config = EventWindowPrescreenConfig(
                canonicalRoot=root,
                derivationSymbols=("BTC-USDT-SWAP",),
                holdbackSymbols=(),
                trainStart="2022-01-01",
                trainEnd="2022-02-01",
                validationEnd="2022-03-01",
            )

            frame, selected_source = _load_raw_frame(
                config, "BTC-USDT-SWAP", "4h"
            )

            self.assertIn("/4h/", selected_source)
            self.assertTrue((frame["date"].dt.hour % 4 == 0).all())
            self.assertEqual(set(frame["pair"]), {"BTC/USDT:USDT"})

    def test_loader_resamples_only_complete_4h_groups_into_1d_candles(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "canonical"
            path = self._write_partition(
                root, "BTC-USDT-SWAP", "4h", "2021-01-01", 3_000, "4h"
            )
            source = pd.read_parquet(path)
            source.loc[source.index[-1], "confirmed"] = 0
            source.to_parquet(path, index=False)
            config = EventWindowPrescreenConfig(
                canonicalRoot=root,
                derivationSymbols=("BTC-USDT-SWAP",),
                holdbackSymbols=(),
                trainStart="2022-01-01",
                trainEnd="2022-02-01",
                validationEnd="2022-03-01",
            )

            frame, selected_source = _load_raw_frame(
                config, "BTC-USDT-SWAP", "1d"
            )

            self.assertIn("/4h/", selected_source)
            self.assertTrue((frame["date"].dt.hour == 0).all())
            self.assertTrue((frame["confirmed"] == 1).all())
            self.assertEqual(
                len(frame),
                len(source[
                    (source["confirmed"] == 1)
                    & (source["date"] >= frame["date"].min())
                    & (source["date"] < pd.Timestamp("2022-03-01", tz="UTC"))
                ])
                // 6,
            )


if __name__ == "__main__":
    unittest.main()
