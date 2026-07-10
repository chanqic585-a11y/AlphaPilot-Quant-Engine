from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from alphapilot.reports.generate_v13_26_execution_feedback_report import (
    build_v13_26_execution_feedback_report,
)


class V1326ExecutionFeedbackReportTests(unittest.TestCase):
    def test_missing_export_and_empty_registry_stay_honestly_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report = build_v13_26_execution_feedback_report(
                registry_path=Path(directory) / "registry.sqlite",
                execution_outcome_export=Path(directory) / "missing.json",
                code_commit="unit-test",
            )

        self.assertEqual(report["status"], "blocked_no_formal_execution_outcomes")
        self.assertEqual(
            report["executionOutcomeImport"]["status"],
            "blocked_execution_outcome_export_missing",
        )
        self.assertEqual(report["executionEvidence"]["formalExecutionOutcomeCount"], 0)
        self.assertTrue(report["releaseLineage"]["unchanged"])
        self.assertFalse(report["safetyBoundary"]["createsOrders"])
        self.assertFalse(report["safetyBoundary"]["onlineModelMutation"])


if __name__ == "__main__":
    unittest.main()
