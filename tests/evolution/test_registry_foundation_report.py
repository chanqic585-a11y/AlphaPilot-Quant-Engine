from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from alphapilot.reports.generate_evolution_registry_foundation_report import (
    generate_registry_foundation_report,
)


class RegistryFoundationReportTests(unittest.TestCase):
    def test_report_uses_temporary_registry_and_keeps_execution_locked(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            reports = root / "reports"
            reports.mkdir()
            (reports / "factor.json").write_text(
                json.dumps({"reportId": "factor", "factorCount": 1, "factorReports": []}),
                encoding="utf-8",
            )
            output_json = root / "output.json"
            output_markdown = root / "output.md"
            payload = generate_registry_foundation_report(
                reports_dir=reports,
                registry_path=root / "registry.sqlite",
                output_json=output_json,
                output_markdown=output_markdown,
            )

            persisted = json.loads(output_json.read_text(encoding="utf-8"))
            markdown = output_markdown.read_text(encoding="utf-8")

        self.assertEqual(payload, persisted)
        self.assertTrue(payload["safetyBoundary"]["researchOnly"])
        self.assertFalse(payload["safetyBoundary"]["createsStrategyCandidate"])
        self.assertFalse(payload["safetyBoundary"]["createsDemoRelease"])
        self.assertFalse(payload["safetyBoundary"]["createsOrders"])
        assessment = payload["summary"]["candidateFormationAssessment"]
        self.assertFalse(assessment["automaticCreationAllowed"])
        self.assertEqual(assessment["legacyCandidateEvidenceCount"], 0)
        self.assertGreater(assessment["blockedFromRunnableCandidateCount"], 0)
        self.assertIn("formal_strategy_contract_required", assessment["blockingReasons"])
        self.assertIn("nonCandidateReasonCounts", payload["summary"])
        self.assertIn("duplicateFamilyMembers", payload["summary"])
        self.assertIn("Registry Foundation", markdown)


if __name__ == "__main__":
    unittest.main()
