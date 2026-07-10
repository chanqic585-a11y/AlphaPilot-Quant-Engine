from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from alphapilot.data_foundation.quality import inspect_quality
from alphapilot.data_foundation.readers import clean_ohlcv_frame, read_ohlcv


class OhlcvReaderTests(unittest.TestCase):
    def test_timestamp_ms_wins_and_unconfirmed_tail_is_removed(self) -> None:
        raw = pd.DataFrame(
            {
                "timestamp_ms": [1577836800000, 1577837700000, 1577838600000],
                "utc_time": [43831.0, 43831.0104166667, 43831.0208333333],
                "open": [10, 11, 12],
                "high": [12, 13, 14],
                "low": [9, 10, 11],
                "close": [11, 12, 13],
                "volume_quote_currency": [100, 110, 120],
                "confirmed": [1, 1, 0],
            }
        )

        result = clean_ohlcv_frame(raw)

        self.assertEqual(len(result.frame), 2)
        self.assertEqual(result.unconfirmedDroppedCount, 1)
        self.assertEqual(result.frame.iloc[0]["date"].isoformat(), "2020-01-01T00:00:00+00:00")

    def test_excel_serial_fallback_is_not_parsed_as_epoch_nanoseconds(self) -> None:
        raw = pd.DataFrame(
            {
                "utc_time": [43831.0, 43831.0104166667],
                "open": [10, 11],
                "high": [12, 13],
                "low": [9, 10],
                "close": [11, 12],
                "volume_quote_currency": [100, 110],
                "confirmed": [1, 1],
            }
        )

        result = clean_ohlcv_frame(raw)

        self.assertEqual(result.frame.iloc[0]["date"].isoformat(), "2020-01-01T00:00:00+00:00")
        self.assertEqual(result.frame.iloc[1]["date"].isoformat(), "2020-01-01T00:15:00+00:00")

    def test_quality_reports_gaps_without_filling_them(self) -> None:
        raw = pd.DataFrame(
            {
                "timestamp": [1577836800000, 1577837700000, 1577839500000],
                "open": [10, 11, 12],
                "high": [12, 13, 14],
                "low": [9, 10, 11],
                "close": [11, 12, 13],
                "vol": [100, 110, 120],
                "confirm": [1, 1, 1],
            }
        )

        quality = inspect_quality(clean_ohlcv_frame(raw), "15m")

        self.assertEqual(quality.gapEventCount, 1)
        self.assertEqual(quality.missingBarCount, 1)
        self.assertIn("missing_intervals_present", quality.warnings)

    def test_xlsx_reader_uses_same_canonical_rules(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.xlsx"
            pd.DataFrame(
                {
                    "timestamp_ms": [1577836800000, 1577837700000],
                    "open": [10, 11],
                    "high": [12, 13],
                    "low": [9, 10],
                    "close": [11, 12],
                    "volume_quote_currency": [100, 110],
                    "confirmed": [1, 1],
                }
            ).to_excel(path, index=False)

            result = read_ohlcv(path)

        self.assertEqual(len(result.frame), 2)
        self.assertEqual(result.frame.iloc[-1]["date"].isoformat(), "2020-01-01T00:15:00+00:00")


if __name__ == "__main__":
    unittest.main()
