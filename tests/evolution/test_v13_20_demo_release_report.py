from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from alphapilot.reports.generate_v13_20_okx_demo_release_report import build_v13_20_report


class V1320DemoReleaseReportTests(unittest.TestCase):
    def test_empty_registry_fails_closed_without_writing_release_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report, contract = build_v13_20_report(
                registry_path=root / "registry.sqlite",
                code_commit="test-commit",
                contract_directory=root / "contracts",
            )

            self.assertEqual(report["status"], "blocked_no_formal_strategy_candidate")
            self.assertEqual(report["demoReleaseCount"], 0)
            self.assertEqual(report["generatedContractCount"], 0)
            self.assertEqual(list((root / "contracts").glob("demo_release_contract_*.json")), [])
            self.assertTrue(contract["requiresRuntimeCredentials"])
            self.assertFalse(contract["liveExecutionEnabled"])
            self.assertFalse(contract["withdrawApiEnabled"])


if __name__ == "__main__":
    unittest.main()
