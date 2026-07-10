from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from alphapilot.reports.generate_demo_promotion_readiness_report import build_report


class DemoPromotionReadinessReportTests(unittest.TestCase):
    def test_empty_registry_reports_real_blocker_without_fabricated_release(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report = build_report(Path(directory) / "registry.sqlite")

        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["summary"]["demoReleaseCount"], 0)
        self.assertEqual(report["summary"]["strategyCandidateCount"], 0)
        self.assertTrue(report["blockers"])
        self.assertFalse(report["safetyBoundary"]["liveAutomaticPromotionAllowed"])


if __name__ == "__main__":
    unittest.main()
