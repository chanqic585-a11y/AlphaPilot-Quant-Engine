from __future__ import annotations

import unittest
from unittest.mock import patch
import os

from alphapilot.research_service.worker_boundary import ResearchWorkerBoundary


class ResearchWorkerBoundaryTests(unittest.TestCase):
    def test_sanitized_environment_removes_private_exchange_credentials(self) -> None:
        boundary = ResearchWorkerBoundary.default()
        environment = boundary.sanitize_environment({
            "PATH": "runtime-bin",
            "OKX_API_KEY": "secret-key",
            "OKX_SECRET_KEY": "secret-value",
            "OKX_PASSPHRASE": "secret-passphrase",
            "ALPHAPILOT_EXECUTION_TOKEN": "authority-token",
        })

        self.assertEqual(environment, {"PATH": "runtime-bin"})

    def test_projection_is_read_only_and_has_no_execution_authority(self) -> None:
        projection = ResearchWorkerBoundary.default().projection()

        self.assertEqual(projection["marketDataAccess"], "read_only")
        self.assertFalse(projection["privateApiAccess"])
        self.assertFalse(projection["orderAccess"])
        self.assertFalse(projection["approvalAccess"])
        self.assertFalse(projection["armAccess"])
        self.assertEqual(projection["maxConcurrentCampaigns"], 1)
        self.assertEqual(projection["processPriority"], "below_normal")

    def test_execution_side_effects_are_rejected(self) -> None:
        boundary = ResearchWorkerBoundary.default()

        with self.assertRaisesRegex(ValueError, "research_worker_crossed_execution_boundary"):
            boundary.assert_result({"status": "completed", "orderCount": 1})

    def test_current_worker_process_can_drop_private_credentials(self) -> None:
        boundary = ResearchWorkerBoundary.default()
        with patch.dict(os.environ, {"PATH": "runtime-bin", "OKX_API_KEY": "secret"}, clear=True):
            removed = boundary.enforce_current_process_environment()
            self.assertEqual(os.environ.get("PATH"), "runtime-bin")
            self.assertNotIn("OKX_API_KEY", os.environ)
            self.assertEqual(removed, ["OKX_API_KEY"])


if __name__ == "__main__":
    unittest.main()
