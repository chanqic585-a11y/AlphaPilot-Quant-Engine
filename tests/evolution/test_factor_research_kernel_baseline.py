from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from alphapilot.reports.generate_factor_research_kernel_baseline import (
    generate_factor_research_kernel_baseline,
)


class FactorResearchKernelBaselineTests(unittest.TestCase):
    def test_report_is_persisted_and_keeps_promotion_locked(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manual = root / "manual.json"
            evaluation = root / "evaluation.json"
            manual.write_text(
                json.dumps(
                    {
                        "version": "V-test",
                        "factorDefinitions": [
                            {
                                "factorId": "momentum",
                                "name": "Momentum",
                                "formula": "ts_return(close, 3)",
                                "requiredFields": ["close"],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            evaluation.write_text(
                json.dumps({"candidateFactors": [], "factorReports": []}),
                encoding="utf-8",
            )
            output_json = root / "report.json"
            output_markdown = root / "report.md"

            payload = generate_factor_research_kernel_baseline(
                manual_report_path=manual,
                evaluation_report_path=evaluation,
                registry_path=root / "registry.sqlite",
                output_json=output_json,
                output_markdown=output_markdown,
            )

            persisted = json.loads(output_json.read_text(encoding="utf-8"))
            markdown = output_markdown.read_text(encoding="utf-8")

        self.assertEqual(payload, persisted)
        self.assertEqual(payload["summary"]["formalResearchReadyCount"], 0)
        self.assertFalse(payload["safetyBoundary"]["createsStrategyCandidate"])
        self.assertFalse(payload["safetyBoundary"]["createsDemoRelease"])
        self.assertFalse(payload["safetyBoundary"]["createsOrders"])
        self.assertIn("Factor Research Kernel", markdown)


if __name__ == "__main__":
    unittest.main()
