from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from alphapilot.reports.generate_live_candidate_boundary_report import build_report


class LiveCandidateBoundaryReportTests(unittest.TestCase):
    def test_empty_registry_has_no_automatic_approval_or_adapter(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report = build_report(Path(directory) / "registry.sqlite")

        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["summary"]["liveCandidatePackageCount"], 0)
        self.assertEqual(report["summary"]["automaticApprovalCount"], 0)
        self.assertEqual(report["summary"]["liveExecutionAdapterCount"], 0)
        self.assertFalse(report["safetyBoundary"]["automaticLivePromotionAllowed"])


if __name__ == "__main__":
    unittest.main()
