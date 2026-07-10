from __future__ import annotations

import tempfile
import unittest
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from alphapilot.evolution.offline.evidence_feedback import (
    build_failure_attribution,
    build_research_triggers,
    ingest_evidence_classed_outcomes,
)
from alphapilot.evolution.offline.loop import OfflineEvolutionConfig, run_offline_evolution_loop
from alphapilot.evolution.registry.database import connect_registry
from alphapilot.evolution.registry.hashing import stable_hash
from alphapilot.evolution.registry.repositories import RegistryRepository
from alphapilot.evolution.registry.types import (
    DataSnapshotRecord,
    DemoReleaseRecord,
    ExperimentRecord,
    FactorDefinitionRecord,
    FactorRunRecord,
    OutcomeLedgerRecord,
    StrategyCandidateRecord,
    StrategyFamilyRecord,
)
from alphapilot.evolution.strategies.candidate_builder import StrategyCandidateDraft


def outcome_record(
    index: int,
    *,
    evidence_class: str = "historical_path_replay",
    net_r: float = -1.0,
    source_entity_type: str = "historical_replay_run",
) -> OutcomeLedgerRecord:
    decision = datetime(2025, 1, 1, tzinfo=UTC) + timedelta(hours=index * 4)
    payload = {
        "evidenceClass": evidence_class,
        "usesActualCanonicalCandlePath": evidence_class.startswith("historical_path_replay"),
        "publicMarketDriven": evidence_class == "realtime_local_forward",
        "demoReleaseId": "demo-release" if evidence_class == "okx_demo" else None,
        "liveReleaseId": "live-release" if evidence_class == "live" else None,
        "trade": {
            "netR": net_r,
            "grossR": net_r + 0.05,
            "exitReason": "target" if net_r > 0 else "stop",
            "sameBarAmbiguous": False,
        },
    }
    core = {"index": index, "class": evidence_class, "payload": payload}
    return OutcomeLedgerRecord(
        outcomeId=stable_hash(core, prefix="outcome"),
        evidenceClass=evidence_class,
        sourceEntityType=source_entity_type,
        sourceEntityId=f"source-{index}",
        dataSnapshotId="snapshot_1",
        strategyCandidateId=None,
        instrumentId="BTC-USDT-SWAP" if index % 2 == 0 else "ETH-USDT-SWAP",
        timeframe="1h",
        direction="long",
        decisionAt=decision.isoformat(),
        entryAt=(decision + timedelta(hours=1)).isoformat(),
        exitAt=(decision + timedelta(hours=2)).isoformat(),
        status="closed",
        outcome=payload,
        contentHash=stable_hash(core),
    )


def register_research_inputs(repository: RegistryRepository) -> None:
    repository.create_data_snapshot(
        DataSnapshotRecord(
            dataSnapshotId="snapshot_1",
            source="unit_test",
            exchange="okx",
            marketType="swap",
            timeframe="1h",
            startTime="2025-01-01T00:00:00+00:00",
            endTime="2025-02-01T00:00:00+00:00",
            pointInTimeCutoff="2025-02-01T00:00:00+00:00",
            manifest={"files": []},
            contentHash=stable_hash({"snapshot": 1}),
        )
    )
    seed_definition = {
        "dslSupported": True,
        "canonicalExpression": "rolling_mean(close,20)",
        "sourceDefinition": {"requiredFields": ["close"]},
        "seedEligible": True,
        "researchOnly": True,
    }
    repository.create_factor_definition(
        FactorDefinitionRecord(
            factorDefinitionId="factor_1",
            name="Seed factor",
            version="v1",
            expression="rolling_mean(close,20)",
            definition=seed_definition,
            contentHash=stable_hash(seed_definition),
        )
    )
    run_payload = {"pointInTimeValidated": True}
    repository.create_factor_run(
        FactorRunRecord(
            factorRunId="run_1",
            factorDefinitionId="factor_1",
            dataSnapshotId="snapshot_1",
            codeCommit="unit-test",
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
            codeCommit="unit-test",
            payload=experiment_payload,
            contentHash=stable_hash(experiment_payload),
        )
    )


def candidate_draft() -> StrategyCandidateDraft:
    return StrategyCandidateDraft(
        name="Offline feedback shadow candidate",
        familyKey="offline_feedback_v1",
        direction="long",
        marketDefinition={
            "exchange": "public_multi_exchange",
            "marketType": "swap",
            "timeframe": "1h",
            "universePolicy": "historical_snapshot",
        },
        entryRules=["factor_expression_offline_feedback"],
        exitRules={"stopLossR": 1.0, "takeProfitR": 2.0, "maxHoldingBars": 24},
        riskRules={"riskPerTradePct": 0.25, "maxLeverage": 2, "maxConcurrentPositions": 2},
        evidence={
            "dataSnapshotId": "snapshot_1",
            "factorRunIds": ["run_1"],
            "experimentIds": ["experiment_1"],
            "walkForwardManifestHash": "walk_forward_1",
            "formalGateStatus": "passed",
            "correlationAcceptedFactorIds": ["factor_candidate_a"],
        },
    )


class OfflineEvolutionLoopTests(unittest.TestCase):
    def test_probe_and_synthetic_evidence_are_quarantined(self) -> None:
        formal = outcome_record(1)
        probe = outcome_record(
            2,
            evidence_class="historical_path_replay_probe",
            source_entity_type="engine_probe",
        )
        synthetic = outcome_record(3, evidence_class="legacy_synthetic")

        result = ingest_evidence_classed_outcomes([formal, probe, synthetic])

        self.assertEqual(result.formalOutcomeCount, 1)
        self.assertEqual(len(result.quarantined), 2)
        self.assertFalse(result.to_dict()["syntheticEvidencePromoted"])

    def test_failure_attribution_creates_research_only_trigger(self) -> None:
        records = [outcome_record(index, net_r=-1.0) for index in range(30)]
        ingestion = ingest_evidence_classed_outcomes(records)
        attribution = build_failure_attribution(ingestion)
        triggers = build_research_triggers(ingestion, attribution)

        self.assertIn(
            "negative_expectancy",
            {item["triggerType"] for item in triggers},
        )
        self.assertTrue(all(item["researchOnly"] for item in triggers))
        self.assertFalse(attribution["quarantinedEvidenceIncluded"])

        all_wins = ingest_evidence_classed_outcomes(
            [outcome_record(index, net_r=2.0) for index in range(10)]
        )
        json.dumps(build_failure_attribution(all_wins), allow_nan=False)

    def test_bounded_loop_registers_only_shadow_assets_and_preserves_release(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            connection = connect_registry(Path(directory) / "registry.sqlite")
            try:
                repository = RegistryRepository(connection)
                register_research_inputs(repository)
                for index in range(30):
                    repository.create_outcome(outcome_record(index, net_r=-1.0))
                family_payload = {"direction": "long"}
                repository.create_strategy_family(
                    StrategyFamilyRecord(
                        strategyFamilyId="family-existing",
                        familyKey="existing",
                        name="Existing family",
                        status="demo_validated",
                        metadata=family_payload,
                        contentHash=stable_hash(family_payload),
                    )
                )
                candidate_payload = {"direction": "long", "executionEnabled": False}
                repository.create_strategy_candidate(
                    StrategyCandidateRecord(
                        strategyCandidateId="candidate-existing",
                        strategyFamilyId="family-existing",
                        name="Existing Demo candidate",
                        status="demo_validated",
                        candidate=candidate_payload,
                        contentHash=stable_hash(candidate_payload),
                    )
                )
                release_payload = {
                    "schemaVersion": "demo_release_contract_v1",
                    "checksums": {"codeCommit": "code", "data": "data", "model": "model"},
                    "liveExecutionAllowed": False,
                    "rollbackTargetDemoReleaseId": "demo-release-prior",
                }
                release = repository.create_demo_release(
                    DemoReleaseRecord(
                        demoReleaseId="demo-release-current",
                        strategyCandidateId="candidate-existing",
                        status="demo_validated",
                        riskEnvelope={"initialEquityUsdt": 1000.0},
                        release=release_payload,
                        contentHash=stable_hash(release_payload),
                    )
                )
                result = run_offline_evolution_loop(
                    repository=repository,
                    config=OfflineEvolutionConfig(
                        researchBudget=8,
                        maxGeneratedFactors=6,
                        minimumCorrelationObservations=10,
                    ),
                    candidate_factor_series={"factor_candidate_a": list(range(30))},
                    candidate_drafts=[candidate_draft()],
                )
                persisted_release = repository.get_demo_release(release.demoReleaseId)
                candidate_rows = repository.list_strategy_candidates()
            finally:
                connection.close()

        self.assertEqual(result["status"], "completed_shadow_research_only")
        self.assertGreater(result["boundedFactorGeneration"]["generatedCandidateCount"], 0)
        self.assertEqual(result["correlationReview"]["status"], "completed")
        self.assertEqual(result["candidateRegistration"]["registeredCount"], 1)
        registered = next(row for row in candidate_rows if row.name == candidate_draft().name)
        self.assertEqual(registered.status, "shadow_candidate")
        self.assertEqual(persisted_release.contentHash, release.contentHash)
        self.assertTrue(result["releaseLineage"]["unchanged"])
        self.assertFalse(result["safetyBoundary"]["autoReplacesRunningRelease"])
        self.assertFalse(result["safetyBoundary"]["createsOrders"])

    def test_empty_registry_stops_before_generation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            connection = connect_registry(Path(directory) / "registry.sqlite")
            repository = RegistryRepository(connection)
            result = run_offline_evolution_loop(repository=repository)
            connection.close()

        self.assertEqual(result["status"], "blocked_no_formal_feedback_evidence")
        self.assertEqual(result["boundedFactorGeneration"]["generatedCandidateCount"], 0)
        self.assertEqual(result["candidateRegistration"]["registeredCount"], 0)


if __name__ == "__main__":
    unittest.main()
