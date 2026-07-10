from __future__ import annotations

import unittest

from alphapilot.reports.generate_v13_24_risk_profile_report import (
    build_v13_24_risk_profile_report,
)


class V1324RiskProfileReportTests(unittest.TestCase):
    def test_report_contains_four_unique_non_executing_profiles(self) -> None:
        report = build_v13_24_risk_profile_report(code_commit="test-commit")

        self.assertEqual(report["status"], "completed")
        self.assertEqual(report["profileCount"], 4)
        self.assertEqual(
            len({row["riskProfileHash"] for row in report["profiles"]}),
            4,
        )
        self.assertFalse(report["safetyBoundary"]["activationEnablesTrading"])
        self.assertFalse(report["safetyBoundary"]["liveExecutionEnabled"])
        self.assertFalse(report["safetyBoundary"]["withdrawApiEnabled"])


if __name__ == "__main__":
    unittest.main()
