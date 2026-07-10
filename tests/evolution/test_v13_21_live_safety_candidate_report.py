from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from alphapilot.evolution.registry.database import connect_registry
from alphapilot.evolution.registry.hashing import stable_hash
from alphapilot.evolution.registry.repositories import RegistryRepository
from alphapilot.evolution.registry.types import DemoReleaseRecord, StrategyCandidateRecord, StrategyFamilyRecord
from alphapilot.reports.generate_v13_21_live_safety_candidate_report import build_v13_21_report


def demo_evidence() -> dict:
    return {
        "demoClosedTrades": 80,
        "demoCalendarDays": 45,
        "netProfitFactor": 1.22,
        "maxDrawdownPercent": 3.4,
        "feeCostUsdt": 18.0,
        "slippageCostUsdt": 12.0,
        "unresolvedCriticalDriftEvents": 0,
        "ledgerMatched": True,
        "checksumsMatch": True,
        "symbolStabilityPassed": True,
        "regimeStabilityPassed": True,
        "timeStabilityPassed": True,
        "outcomeSampleManifestHash": "demo_outcomes_abc123",
    }


class V1321LiveSafetyCandidateReportTests(unittest.TestCase):
    def test_empty_registry_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report, readiness = build_v13_21_report(
                registry_path=Path(directory) / "registry.sqlite",
                code_commit="test-commit",
                package_directory=Path(directory) / "packages",
            )

        self.assertEqual(report["status"], "blocked_no_validated_demo_release")
        self.assertEqual(report["liveCandidatePackageCount"], 0)
        self.assertFalse(readiness["approvalEnablesExecution"])
        self.assertFalse(readiness["liveExecutionAdapterPresent"])

    def test_only_validated_demo_evidence_builds_review_package(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            connection = connect_registry(root / "registry.sqlite")
            repository = RegistryRepository(connection)
            family_payload = {"familyKey": "live_safety_test"}
            repository.create_strategy_family(
                StrategyFamilyRecord(
                    strategyFamilyId="family-live-safety",
                    familyKey="live_safety_test",
                    name="Live Safety Test",
                    status="research_validated",
                    metadata=family_payload,
                    contentHash=stable_hash(family_payload),
                )
            )
            candidate_payload = {"direction": "long", "entryRules": ["factor_test"]}
            repository.create_strategy_candidate(
                StrategyCandidateRecord(
                    strategyCandidateId="candidate-live-safety",
                    strategyFamilyId="family-live-safety",
                    name="Live Safety Test Candidate",
                    status="demo_validated",
                    candidate=candidate_payload,
                    contentHash=stable_hash(candidate_payload),
                )
            )
            release_payload = {
                "schemaVersion": "demo_release_contract_v1",
                "strategy": candidate_payload,
                "checksums": {"codeCommit": "code", "data": "data", "model": "model"},
                "demoValidationEvidence": demo_evidence(),
                "rollbackTargetDemoReleaseId": "demo-release-prior",
                "liveExecutionAllowed": False,
            }
            repository.create_demo_release(
                DemoReleaseRecord(
                    demoReleaseId="demo-release-validated",
                    strategyCandidateId="candidate-live-safety",
                    status="demo_validated",
                    riskEnvelope={"initialEquityUsdt": 1000.0},
                    release=release_payload,
                    contentHash=stable_hash(release_payload),
                )
            )
            connection.close()

            report, readiness = build_v13_21_report(
                registry_path=root / "registry.sqlite",
                code_commit="test-commit",
                package_directory=root / "packages",
            )

            package_files = list((root / "packages").glob("live_candidate_package_*.json"))

        self.assertEqual(report["status"], "live_candidate_review_ready")
        self.assertEqual(report["liveCandidatePackageCount"], 1)
        self.assertEqual(len(package_files), 1)
        package = report["packages"][0]["package"]
        self.assertEqual(package["schemaVersion"], "live_candidate_package_v2")
        self.assertFalse(package["safetyPolicy"]["approvalEnablesExecution"])
        self.assertFalse(readiness["liveExecutionEnabled"])


if __name__ == "__main__":
    unittest.main()
