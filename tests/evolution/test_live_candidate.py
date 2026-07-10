from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from alphapilot.evolution.promotion.live_candidate import (
    DemoValidationEvidence,
    LiveCandidateNotEligible,
    LiveRiskBudgetProposal,
    build_live_candidate_package,
)
from alphapilot.evolution.registry.database import connect_registry
from alphapilot.evolution.registry.hashing import stable_hash
from alphapilot.evolution.registry.repositories import RegistryRepository
from alphapilot.evolution.registry.types import DemoReleaseRecord, StrategyCandidateRecord, StrategyFamilyRecord


def passing_demo_evidence(**overrides: object) -> DemoValidationEvidence:
    values = {
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
    values.update(overrides)
    return DemoValidationEvidence(**values)


class LiveCandidateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.connection = connect_registry(Path(self.directory.name) / "registry.sqlite")
        self.repository = RegistryRepository(self.connection)
        family_payload = {"familyKey": "live_test_family"}
        self.repository.create_strategy_family(
            StrategyFamilyRecord(
                strategyFamilyId="family_live_test",
                familyKey="live_test_family",
                name="Live Test Family",
                status="research_validated",
                metadata=family_payload,
                contentHash=stable_hash(family_payload),
            )
        )
        candidate_payload = {"direction": "long", "entryRules": ["factor_expression_test"]}
        self.repository.create_strategy_candidate(
            StrategyCandidateRecord(
                strategyCandidateId="candidate_live_test",
                strategyFamilyId="family_live_test",
                name="Live Test Candidate",
                status="shadow_candidate",
                candidate=candidate_payload,
                contentHash=stable_hash(candidate_payload),
            )
        )
        release_payload = {
            "schemaVersion": "demo_release_contract_v1",
            "strategy": candidate_payload,
            "checksums": {"codeCommit": "abc123", "data": "data-sha", "model": "model-sha"},
            "liveExecutionAllowed": False,
        }
        self.release = self.repository.create_demo_release(
            DemoReleaseRecord(
                demoReleaseId="demo_release_live_test",
                strategyCandidateId="candidate_live_test",
                status="demo_validated",
                riskEnvelope={"initialEquityUsdt": 1000.0},
                release=release_payload,
                contentHash=stable_hash(release_payload),
            )
        )

    def tearDown(self) -> None:
        self.connection.close()
        self.directory.cleanup()

    def test_validated_demo_builds_manual_approval_only_package(self) -> None:
        package = build_live_candidate_package(
            demoRelease=self.release,
            demoEvidence=passing_demo_evidence(),
            proposedRiskBudget=LiveRiskBudgetProposal(),
            rollbackTargetReleaseId="demo_release_previous",
            repository=self.repository,
        )
        repeated = build_live_candidate_package(
            demoRelease=self.release,
            demoEvidence=passing_demo_evidence(),
            proposedRiskBudget=LiveRiskBudgetProposal(),
            rollbackTargetReleaseId="demo_release_previous",
            repository=self.repository,
        )

        self.assertEqual(package, repeated)
        self.assertEqual(package.status, "awaiting_manual_approval")
        self.assertTrue(package.package["manualApprovalRequired"])
        self.assertFalse(package.package["automaticApprovalAllowed"])
        self.assertFalse(package.package["liveExecutionAdapterPresent"])
        self.assertEqual(self.repository.count("LiveCandidatePackages"), 1)

    def test_unresolved_drift_or_eligible_only_release_is_rejected(self) -> None:
        with self.assertRaises(LiveCandidateNotEligible):
            build_live_candidate_package(
                demoRelease=self.release,
                demoEvidence=passing_demo_evidence(unresolvedCriticalDriftEvents=1),
                proposedRiskBudget=LiveRiskBudgetProposal(),
                rollbackTargetReleaseId="demo_release_previous",
                repository=self.repository,
            )
        eligible_only = DemoReleaseRecord(**{**self.release.__dict__, "status": "demo_eligible"})
        with self.assertRaises(LiveCandidateNotEligible):
            build_live_candidate_package(
                demoRelease=eligible_only,
                demoEvidence=passing_demo_evidence(),
                proposedRiskBudget=LiveRiskBudgetProposal(),
                rollbackTargetReleaseId="demo_release_previous",
                repository=self.repository,
            )


if __name__ == "__main__":
    unittest.main()
