from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from alphapilot.evolution.promotion.demo_release import (
    DEFAULT_DEMO_RISK_ENVELOPE,
    promote_candidate_to_demo,
)
from alphapilot.evolution.promotion.gate import evaluate_demo_promotion
from alphapilot.evolution.registry.database import connect_registry
from alphapilot.evolution.registry.hashing import stable_hash
from alphapilot.evolution.registry.repositories import RegistryRepository
from alphapilot.evolution.registry.types import StrategyCandidateRecord, StrategyFamilyRecord
from tests.evolution.test_promotion_gate import passing_evidence


class DemoReleaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.connection = connect_registry(Path(self.directory.name) / "registry.sqlite")
        self.repository = RegistryRepository(self.connection)
        family_payload = {"familyKey": "test_family"}
        self.family = self.repository.create_strategy_family(
            StrategyFamilyRecord(
                strategyFamilyId="family_test",
                familyKey="test_family",
                name="Test Family",
                status="research_validated",
                metadata=family_payload,
                contentHash=stable_hash(family_payload),
            )
        )
        candidate_payload = {
            "schemaVersion": "strategy_candidate_contract_v1",
            "direction": "long",
            "marketDefinition": {"exchange": "okx", "marketType": "swap", "timeframe": "15m"},
            "entryRules": ["factor_expression_test"],
            "exitRules": {"stopLossR": 1, "takeProfitR": 2, "maxHoldingBars": 24},
            "riskRules": {"riskPerTradePct": 0.25, "maxLeverage": 2, "maxConcurrentPositions": 3},
        }
        self.candidate = self.repository.create_strategy_candidate(
            StrategyCandidateRecord(
                strategyCandidateId="candidate_test",
                strategyFamilyId=self.family.strategyFamilyId,
                name="Test Candidate",
                status="shadow_candidate",
                candidate=candidate_payload,
                contentHash=stable_hash(candidate_payload),
            )
        )

    def tearDown(self) -> None:
        self.connection.close()
        self.directory.cleanup()

    def test_passed_gate_creates_immutable_decision_and_release(self) -> None:
        result = promote_candidate_to_demo(
            candidate=self.candidate,
            gateResult=evaluate_demo_promotion(passing_evidence()),
            repository=self.repository,
            codeCommit="abc123",
            dataChecksum="data-sha",
            modelChecksum="model-sha",
        )
        repeated = promote_candidate_to_demo(
            candidate=self.candidate,
            gateResult=evaluate_demo_promotion(passing_evidence()),
            repository=self.repository,
            codeCommit="abc123",
            dataChecksum="data-sha",
            modelChecksum="model-sha",
        )

        self.assertEqual(result.demoRelease, repeated.demoRelease)
        self.assertEqual(self.repository.count("PromotionDecisions"), 1)
        self.assertEqual(self.repository.count("DemoReleases"), 1)
        self.assertEqual(result.demoRelease.riskEnvelope, DEFAULT_DEMO_RISK_ENVELOPE)
        self.assertEqual(result.demoRelease.status, "demo_eligible")

    def test_failed_gate_records_decision_without_release(self) -> None:
        result = promote_candidate_to_demo(
            candidate=self.candidate,
            gateResult=evaluate_demo_promotion(passing_evidence(shadowClosedSamples=1)),
            repository=self.repository,
            codeCommit="abc123",
            dataChecksum="data-sha",
            modelChecksum="model-sha",
        )

        self.assertIsNone(result.demoRelease)
        self.assertFalse(result.promotionDecision.passed)
        self.assertEqual(self.repository.count("PromotionDecisions"), 1)
        self.assertEqual(self.repository.count("DemoReleases"), 0)


if __name__ == "__main__":
    unittest.main()
