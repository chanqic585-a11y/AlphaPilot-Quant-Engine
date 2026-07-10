from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from alphapilot.reports.generate_v13_25_live_canary_report import (
    build_v13_25_live_canary_report,
)


class V1325LiveCanaryReportTests(unittest.TestCase):
    def test_empty_registry_reports_real_blockers_without_orders(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report = build_v13_25_live_canary_report(
                registry_path=Path(directory) / "registry.sqlite",
                code_commit="test",
                export_directory=Path(directory) / "exports",
            )

        self.assertEqual(report["status"], "blocked_no_live_release")
        self.assertEqual(report["liveReleaseCount"], 0)
        self.assertEqual(report["executionEvidence"]["realOrdersPlacedByReport"], 0)
        self.assertFalse(report["executionEvidence"]["liveCredentialsReadByReport"])
        self.assertFalse(report["runtimeContract"]["withdrawAllowed"])


if __name__ == "__main__":
    unittest.main()
