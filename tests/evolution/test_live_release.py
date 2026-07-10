from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from alphapilot.evolution.promotion.live_candidate import (
    DemoValidationEvidence,
    LiveRiskBudgetProposal,
    build_live_candidate_package,
)
from alphapilot.evolution.promotion.live_release import (
    LiveReleaseNotEligible,
    ManualLiveApprovalEvidence,
    build_live_release,
    export_live_release,
)
from alphapilot.evolution.registry.database import connect_registry
from alphapilot.evolution.registry.hashing import stable_hash
from alphapilot.evolution.registry.repositories import RegistryRepository
from alphapilot.evolution.registry.types import DemoReleaseRecord, StrategyCandidateRecord, StrategyFamilyRecord
from alphapilot.evolution.risk_profiles import activate_risk_profile


class LiveReleaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.connection = connect_registry(Path(self.directory.name) / "registry.sqlite")
        self.repository = RegistryRepository(self.connection)
        family = {"familyKey": "live_release_family"}
        self.repository.create_strategy_family(
            StrategyFamilyRecord("family_live_release", "live_release_family", "Live Release", "validated", family, stable_hash(family))
        )
        strategy = {"direction": "long", "entryRules": ["test_rule"]}
        self.repository.create_strategy_candidate(
            StrategyCandidateRecord("candidate_live_release", "family_live_release", "Candidate", "shadow_candidate", strategy, stable_hash(strategy))
        )
        release_payload = {
            "schemaVersion": "demo_release_contract_v1",
            "strategy": strategy,
            "checksums": {"codeCommit": "abc", "data": "data", "model": "model"},
            "liveExecutionAllowed": False,
        }
        demo = self.repository.create_demo_release(
            DemoReleaseRecord("demo_live_release", "candidate_live_release", "demo_validated", {"initialEquityUsdt": 1000.0}, release_payload, stable_hash(release_payload))
        )
        evidence = DemoValidationEvidence(80, 45, 1.25, 3.0, 10.0, 5.0, 0, True, True, True, True, True, "demo_outcomes_test")
        self.package = build_live_candidate_package(
            demoRelease=demo,
            demoEvidence=evidence,
            proposedRiskBudget=LiveRiskBudgetProposal(),
            rollbackTargetReleaseId="demo_previous",
            repository=self.repository,
        )
        self.profile = self.repository.get_risk_profile(self.package.package["riskProfileId"])
        assert self.profile is not None
        activate_risk_profile(self.repository, self.profile, actor="user_manual", reason="unit_test")

    def tearDown(self) -> None:
        self.connection.close()
        self.directory.cleanup()

    def _approval(self, **overrides: str) -> ManualLiveApprovalEvidence:
        values = {
            "liveCandidatePackageId": self.package.liveCandidatePackageId,
            "packageHash": self.package.contentHash,
            "riskProfileId": self.profile.riskProfileId,
            "riskProfileHash": self.profile.contentHash,
            "actor": "user_manual",
            "approvedAt": "2026-07-11T00:00:00+00:00",
            "confirmationHash": hashlib.sha256(b"APPROVE").hexdigest(),
        }
        values.update(overrides)
        return ManualLiveApprovalEvidence(**values)

    def test_manual_approval_builds_immutable_canary_release(self) -> None:
        release = build_live_release(
            package=self.package,
            riskProfile=self.profile,
            approval=self._approval(),
            repository=self.repository,
        )
        exported = export_live_release(release)

        self.assertEqual(release.status, "live_canary_approved")
        self.assertEqual(self.repository.count("LiveReleases"), 1)
        self.assertTrue(release.release["protectionPolicy"]["attachedStopLossRequired"])
        self.assertFalse(exported["executionBoundary"]["withdrawAllowed"])

    def test_checksum_mismatch_is_rejected(self) -> None:
        with self.assertRaises(LiveReleaseNotEligible):
            build_live_release(
                package=self.package,
                riskProfile=self.profile,
                approval=self._approval(packageHash="wrong"),
                repository=self.repository,
            )


if __name__ == "__main__":
    unittest.main()
