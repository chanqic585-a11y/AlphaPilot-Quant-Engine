from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from alphapilot.evolution.registry.database import connect_registry
from alphapilot.evolution.registry.hashing import stable_hash
from alphapilot.evolution.registry.repositories import RegistryRepository
from alphapilot.evolution.registry.types import (
    DataSnapshotRecord,
    ExperimentRecord,
    FactorDefinitionRecord,
    FactorRunRecord,
)
from alphapilot.evolution.strategies.candidate_builder import (
    StrategyCandidateDraft,
    build_strategy_candidate,
)


def valid_draft() -> StrategyCandidateDraft:
    return StrategyCandidateDraft(
        name="Research trend candidate",
        familyKey="trend_research_v1",
        direction="long",
        marketDefinition={
            "exchange": "public_multi_exchange",
            "marketType": "swap",
            "timeframe": "1h",
            "universePolicy": "historical_snapshot",
        },
        entryRules=["factor_expression_abc"],
        exitRules={"stopLossR": 1.0, "takeProfitR": 2.0, "maxHoldingBars": 12},
        riskRules={"riskPerTradePct": 0.25, "maxLeverage": 3, "maxConcurrentPositions": 2},
        evidence={
            "dataSnapshotId": "snapshot_1",
            "factorRunIds": ["run_1"],
            "experimentIds": ["experiment_1"],
            "walkForwardManifestHash": "walk_forward_1",
            "formalGateStatus": "passed",
        },
    )


def register_evidence(repository: RegistryRepository) -> None:
    repository.create_data_snapshot(
        DataSnapshotRecord(
            dataSnapshotId="snapshot_1",
            source="unit_test",
            exchange="okx",
            marketType="swap",
            timeframe="1h",
            startTime=None,
            endTime=None,
            pointInTimeCutoff="2026-01-01T00:00:00+00:00",
            manifest={"files": []},
            contentHash=stable_hash({"snapshot": 1}),
        )
    )
    repository.create_factor_definition(
        FactorDefinitionRecord(
            factorDefinitionId="factor_1",
            name="Factor",
            version="v1",
            expression="close",
            definition={"researchOnly": True},
            contentHash=stable_hash({"factor": 1}),
        )
    )
    run_payload = {"pointInTimeValidated": True}
    repository.create_factor_run(
        FactorRunRecord(
            factorRunId="run_1",
            factorDefinitionId="factor_1",
            dataSnapshotId="snapshot_1",
            codeCommit="unit_test",
            configHash=stable_hash({"config": 1}),
            resultPath=None,
            resultSha256=None,
            status="research_validated",
            payload=run_payload,
            contentHash=stable_hash(run_payload),
        )
    )
    experiment_payload = {"formalGateStatus": "passed"}
    repository.create_experiment(
        ExperimentRecord(
            experimentId="experiment_1",
            experimentType="formal_factor_evaluation",
            status="research_validated",
            dataSnapshotId="snapshot_1",
            splitDefinition={"foldManifestHash": "walk_forward_1"},
            costModel={"stressPassed": True},
            parameters={},
            codeCommit="unit_test",
            payload=experiment_payload,
            contentHash=stable_hash(experiment_payload),
        )
    )


class CandidateBuilderTests(unittest.TestCase):
    def test_complete_candidate_is_persisted_in_shadow_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            connection = connect_registry(Path(directory) / "registry.sqlite")
            try:
                repository = RegistryRepository(connection)
                register_evidence(repository)
                first = build_strategy_candidate(valid_draft(), repository=repository)
                second = build_strategy_candidate(valid_draft(), repository=repository)
                candidate_count = repository.count("StrategyCandidates")
                family_count = repository.count("StrategyFamilies")
                release_count = repository.count("DemoReleases")
            finally:
                connection.close()

        self.assertEqual(first, second)
        self.assertEqual(first.status, "shadow_candidate")
        self.assertEqual(candidate_count, 1)
        self.assertEqual(family_count, 1)
        self.assertEqual(release_count, 0)
        self.assertFalse(first.candidate["executionEnabled"])
        self.assertFalse(first.candidate["demoPromotionAllowed"])

    def test_incomplete_contract_weak_reward_risk_and_missing_evidence_fail(self) -> None:
        bad_drafts = [
            replace(valid_draft(), exitRules={}),
            replace(
                valid_draft(),
                exitRules={"stopLossR": 1.0, "takeProfitR": 1.5, "maxHoldingBars": 12},
            ),
            replace(valid_draft(), evidence={**valid_draft().evidence, "formalGateStatus": "blocked"}),
            replace(
                valid_draft(),
                riskRules={
                    "riskPerTradePct": 0.25,
                    "maxLeverage": 2.5,
                    "maxConcurrentPositions": 2,
                },
            ),
        ]
        with tempfile.TemporaryDirectory() as directory:
            connection = connect_registry(Path(directory) / "registry.sqlite")
            try:
                repository = RegistryRepository(connection)
                register_evidence(repository)
                for draft in bad_drafts:
                    with self.subTest(draft=draft):
                        with self.assertRaises(ValueError):
                            build_strategy_candidate(draft, repository=repository)
                self.assertEqual(repository.count("StrategyCandidates"), 0)
            finally:
                connection.close()


if __name__ == "__main__":
    unittest.main()
