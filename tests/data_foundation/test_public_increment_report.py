from __future__ import annotations

import argparse
import unittest

from alphapilot.data_foundation.okx_public import PublicIncrement
from alphapilot.reports.generate_v13_16_public_increment_report import (
    build_report,
    parse_timeframes,
)


def _increment(
    *,
    status: str,
    continuity_status: str | None = None,
) -> PublicIncrement:
    return PublicIncrement(
        instrumentId="BTC-USDT-SWAP",
        timeframe="15m",
        startExclusiveMs=0,
        rows=1 if status == "collected" else 0,
        startTime=None,
        endTime=None,
        requestCount=1,
        outputPath=None,
        outputSha256=None,
        status=status,
        sourceEndpoint="https://example.test/api/v5/market/history-candles",
        continuityStatus=continuity_status,
    )


class PublicIncrementReportTests(unittest.TestCase):
    def test_timeframes_reject_powershell_decimal_suffix_regression(self) -> None:
        self.assertEqual(parse_timeframes("15m,1h,4h,1d"), ["15m", "1h", "4h", "1d"])
        with self.assertRaises(argparse.ArgumentTypeError):
            parse_timeframes("15m,1h,4h,1")

    def test_blocked_row_cannot_produce_completed_report(self) -> None:
        report = build_report(
            [
                _increment(status="collected", continuity_status="contiguous"),
                _increment(status="blocked_missing_local_cutoff"),
            ]
        )

        self.assertEqual(report["status"], "completed_with_errors")
        self.assertEqual(report["requestedCount"], 2)
        self.assertEqual(report["blockedCount"], 1)

    def test_continuity_gap_cannot_produce_completed_report(self) -> None:
        report = build_report([_increment(status="collected", continuity_status="gap")])

        self.assertEqual(report["status"], "completed_with_errors")
        self.assertEqual(report["continuityFailureCount"], 1)


if __name__ == "__main__":
    unittest.main()
