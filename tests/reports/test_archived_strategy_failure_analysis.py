from __future__ import annotations

import unittest
from pathlib import Path

from alphapilot.reports.archived_strategy_inventory import (
    build_archived_strategy_inventory,
    normalize_optional_number,
)
from alphapilot.reports.generate_archived_strategy_failure_analysis import (
    build_archived_failure_analysis,
)
from alphapilot.reports.signal_level_failure_attribution import (
    attribute_strategy_failure,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class ArchivedStrategyFailureAnalysisTests(unittest.TestCase):
    def test_optional_numbers_preserve_real_zero_and_missing_values(self) -> None:
        self.assertEqual(0.0, normalize_optional_number(0))
        self.assertEqual(1.25, normalize_optional_number("1.25"))
        self.assertIsNone(normalize_optional_number(None))
        self.assertIsNone(normalize_optional_number("unavailable"))

    def test_inventory_discovers_all_failed_or_rejected_archive_records(self) -> None:
        inventory = build_archived_strategy_inventory(PROJECT_ROOT)
        ids = {row["strategyId"] for row in inventory}

        self.assertEqual(13, len(inventory))
        self.assertIn("alpha_volume_rebound_v01", ids)
        self.assertIn("benchmark_ema_trend", ids)
        self.assertIn("benchmark_bollinger_rebound", ids)
        self.assertIn("rejected_benchmark_martingale", ids)
        self.assertIn("alpha_short_rejection_1h_v01", ids)
        self.assertTrue(all(not row["dryRunApproved"] for row in inventory))
        self.assertTrue(all(not row["liveTradingApproved"] for row in inventory))

    def test_inventory_excludes_neutral_baselines_and_keeps_evidence_provenance(self) -> None:
        inventory = build_archived_strategy_inventory(PROJECT_ROOT)
        ids = {row["strategyId"] for row in inventory}

        self.assertNotIn("benchmark_no_trade", ids)
        self.assertNotIn("benchmark_buy_hold_btc", ids)
        for row in inventory:
            self.assertIn(row["evidenceLevel"], {1, 2, 3, 4})
            self.assertTrue(row["sourceArchive"])
            self.assertIsInstance(row["evidenceFiles"], list)
            self.assertIsInstance(row["missingEvidenceFields"], list)

    def test_missing_metrics_are_null_instead_of_fabricated_zero(self) -> None:
        inventory = build_archived_strategy_inventory(PROJECT_ROOT)
        martingale = next(
            row for row in inventory if row["strategyId"] == "rejected_benchmark_martingale"
        )

        self.assertIsNone(martingale["metrics"]["tradeCount"])
        self.assertIsNone(martingale["metrics"]["profitFactor"])
        self.assertIsNone(martingale["metrics"]["totalReturnPct"])
        self.assertIn("tradeCount", martingale["missingEvidenceFields"])

    def test_failure_attribution_separates_signal_and_account_layers(self) -> None:
        record = {
            "strategyId": "test_strategy",
            "status": "failed_benchmark",
            "reason": "high frequency and cost sensitivity",
            "metrics": {
                "tradeCount": 2500,
                "totalReturnPct": -80.0,
                "slippageAdjustedTotalReturnPct": -120.0,
                "profitFactor": 0.6,
                "slippageAdjustedProfitFactor": 0.4,
                "maxDrawdownPct": 85.0,
                "averageNetR": None,
            },
            "missingEvidenceFields": ["averageNetR"],
        }

        result = attribute_strategy_failure(record)

        self.assertEqual("signal_edge_failure", result["primaryFailureType"])
        self.assertEqual("critical", result["severity"])
        self.assertIn("cost_amplification", result["secondaryFailureTypes"])
        self.assertIn("risk_model_failure", result["secondaryFailureTypes"])
        self.assertIn("overtrading", result["secondaryFailureTypes"])
        self.assertEqual("failed", result["signalLayer"]["assessment"])
        self.assertEqual("failed", result["accountRiskLayer"]["assessment"])
        self.assertFalse(result["causalityProven"])

    def test_report_summary_matches_inventory_and_never_promotes_archives(self) -> None:
        report = build_archived_failure_analysis(PROJECT_ROOT, "2026-07-15T00:00:00Z")

        self.assertEqual(13, report["summary"]["strategyCount"])
        self.assertEqual(0, report["summary"]["dryRunApprovedCount"])
        self.assertEqual(0, report["summary"]["liveTradingApprovedCount"])
        self.assertTrue(report["safetyBoundary"]["reportOnly"])
        self.assertFalse(report["safetyBoundary"]["backtestExecuted"])
        self.assertFalse(report["safetyBoundary"]["strategyModified"])
        self.assertTrue(report["crossStrategyPatterns"])


if __name__ == "__main__":
    unittest.main()
