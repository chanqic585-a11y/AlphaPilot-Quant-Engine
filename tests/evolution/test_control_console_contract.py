from __future__ import annotations

import unittest

from alphapilot.evolution.adapters.control_console_contract import build_control_console_contract
from alphapilot.evolution.registry.types import DemoReleaseRecord


class ControlConsoleContractTests(unittest.TestCase):
    def test_contract_contains_release_and_no_credentials(self) -> None:
        release = DemoReleaseRecord(
            demoReleaseId="demo_release_test",
            strategyCandidateId="candidate_test",
            status="demo_eligible",
            riskEnvelope={"initialEquityUsdt": 1000.0},
            release={
                "strategy": {"entryRules": ["factor_expression_test"]},
                "checksums": {"data": "data-sha", "model": "model-sha", "codeCommit": "abc123"},
            },
            contentHash="release-sha",
        )

        contract = build_control_console_contract(release)
        serialized = str(contract).lower()

        self.assertEqual(contract["demoReleaseId"], release.demoReleaseId)
        self.assertEqual(contract["riskEnvelope"]["initialEquityUsdt"], 1000.0)
        self.assertNotIn("apikey", serialized)
        self.assertNotIn("passphrase", serialized)
        self.assertNotIn("secretkey", serialized)

    def test_sensitive_release_field_is_rejected(self) -> None:
        release = DemoReleaseRecord(
            demoReleaseId="bad",
            strategyCandidateId="candidate_test",
            status="demo_eligible",
            riskEnvelope={},
            release={"apiKey": "forbidden"},
            contentHash="bad-sha",
        )
        with self.assertRaises(ValueError):
            build_control_console_contract(release)


if __name__ == "__main__":
    unittest.main()
