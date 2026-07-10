from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from alphapilot.evolution.offline.execution_outcome_importer import (
    import_execution_outcome_export,
)
from alphapilot.evolution.registry.database import connect_registry
from alphapilot.evolution.registry.hashing import stable_hash
from alphapilot.evolution.registry.repositories import RegistryRepository
from alphapilot.evolution.registry.types import (
    DataSnapshotRecord,
    DemoReleaseRecord,
    LiveCandidatePackageRecord,
    LiveReleaseRecord,
    RiskProfileRecord,
    StrategyCandidateRecord,
    StrategyFamilyRecord,
)


def register_lineage(repository: RegistryRepository, *, live: bool = False) -> dict[str, str]:
    snapshot_payload = {"files": ["BTC-USDT-SWAP-1h.parquet"]}
    repository.create_data_snapshot(
        DataSnapshotRecord(
            dataSnapshotId="snapshot-1",
            source="unit_test",
            exchange="okx",
            marketType="swap",
            timeframe="1h",
            startTime="2026-07-01T00:00:00+00:00",
            endTime="2026-07-11T00:00:00+00:00",
            pointInTimeCutoff="2026-07-11T00:00:00+00:00",
            manifest=snapshot_payload,
            contentHash=stable_hash(snapshot_payload),
        )
    )
    family_payload = {"direction": "long"}
    repository.create_strategy_family(
        StrategyFamilyRecord(
            strategyFamilyId="family-1",
            familyKey="formal_outcome_test",
            name="Formal outcome test",
            status="demo_validated",
            metadata=family_payload,
            contentHash=stable_hash(family_payload),
        )
    )
    candidate_payload = {"direction": "long", "dataSnapshotId": "snapshot-1"}
    repository.create_strategy_candidate(
        StrategyCandidateRecord(
            strategyCandidateId="candidate-1",
            strategyFamilyId="family-1",
            name="Formal outcome candidate",
            status="demo_validated",
            candidate=candidate_payload,
            contentHash=stable_hash(candidate_payload),
        )
    )
    demo_payload = {"schemaVersion": "demo_release_contract_v1", "executionEnabled": True}
    demo = repository.create_demo_release(
        DemoReleaseRecord(
            demoReleaseId="demo-release-1",
            strategyCandidateId="candidate-1",
            status="demo_validated",
            riskEnvelope={"minimumRewardRiskRatio": 2.0},
            release=demo_payload,
            contentHash=stable_hash(demo_payload),
        )
    )
    if not live:
        return {
            "releaseId": demo.demoReleaseId,
            "releaseHash": demo.contentHash,
            "riskProfileId": "",
            "riskProfileHash": "",
        }
    profile_payload = {"capitalLimitUsdt": 1000.0, "minimumRewardRiskRatio": 2.0}
    profile = repository.create_risk_profile(
        RiskProfileRecord(
            riskProfileId="risk-profile-1",
            profileKey="live_canary_test",
            version=1,
            environment="live_canary",
            name="Live Canary test",
            status="active",
            profile=profile_payload,
            safetyEnvelope={"maxCapitalLimitUsdt": 1000.0},
            contentHash=stable_hash(profile_payload),
        )
    )
    package_payload = {"demoReleaseId": demo.demoReleaseId, "approved": True}
    package = repository.create_live_candidate_package(
        LiveCandidatePackageRecord(
            liveCandidatePackageId="live-package-1",
            demoReleaseId=demo.demoReleaseId,
            status="approved",
            package=package_payload,
            contentHash=stable_hash(package_payload),
        )
    )
    live_payload = {"schemaVersion": "live_release_contract_v1", "approved": True}
    release = repository.create_live_release(
        LiveReleaseRecord(
            liveReleaseId="live-release-1",
            liveCandidatePackageId=package.liveCandidatePackageId,
            strategyCandidateId="candidate-1",
            status="approved",
            riskProfileId=profile.riskProfileId,
            release=live_payload,
            contentHash=stable_hash(live_payload),
        )
    )
    return {
        "releaseId": release.liveReleaseId,
        "releaseHash": release.contentHash,
        "riskProfileId": profile.riskProfileId,
        "riskProfileHash": profile.contentHash,
    }


def export_payload(lineage: dict[str, str], *, live: bool = False, snapshot_id: str = "snapshot-1") -> dict:
    evidence_class = "live" if live else "okx_demo"
    base = {
        "schemaVersion": "alphapilot_execution_outcome_v1",
        "evidenceClass": evidence_class,
        "environment": evidence_class,
        "sourceEntityType": "okx_live_execution" if live else "okx_demo_execution",
        "sourceEntityId": "source-record-1",
        "releaseId": lineage["releaseId"],
        "releaseHash": lineage["releaseHash"],
        "riskProfileId": lineage["riskProfileId"],
        "riskProfileHash": lineage["riskProfileHash"],
        "strategyCandidateId": "candidate-1",
        "dataSnapshotId": snapshot_id,
        "instrumentId": "BTC-USDT-SWAP",
        "timeframe": "1h",
        "direction": "long",
        "decisionAt": "2026-07-11T00:00:00+00:00",
        "entryAt": "2026-07-11T00:01:00+00:00",
        "exitAt": "2026-07-11T01:00:00+00:00",
        "status": "closed",
        "trade": {
            "entryPrice": 100.0,
            "exitPrice": 102.0,
            "quantity": 1.0,
            "grossPnl": 2.0,
            "feePaid": 0.1,
            "slippagePaid": 0.1,
            "netPnl": 1.8,
            "riskAmount": 1.0,
            "grossR": 2.0,
            "netR": 1.8,
            "exitReason": "target",
            "sameBarAmbiguous": False,
        },
        "sourcePayloadHash": "source-payload-hash",
        "accountValuesPersisted": False,
    }
    record = {
        **base,
        "executionOutcomeId": "execution-outcome-1",
        "contentHash": stable_hash(base),
        "createdAt": "2026-07-11T01:00:01+00:00",
    }
    core = {
        "schemaVersion": "alphapilot_execution_outcome_export_v1",
        "records": [record],
        "quarantinedExecutionRecords": [],
    }
    return {**core, "manifestHash": stable_hash(core)}


class ExecutionOutcomeImporterTests(unittest.TestCase):
    def test_valid_demo_outcome_is_imported_idempotently(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            connection = connect_registry(Path(directory) / "registry.sqlite")
            try:
                repository = RegistryRepository(connection)
                lineage = register_lineage(repository)
                source = Path(directory) / "outcomes.json"
                source.write_text(json.dumps(export_payload(lineage)), encoding="utf-8")
                first = import_execution_outcome_export(source, repository=repository)
                repeated = import_execution_outcome_export(source, repository=repository)
                rows = repository.list_outcomes()
            finally:
                connection.close()

        self.assertEqual(first.importedCount, 1)
        self.assertEqual(repeated.duplicateCount, 1)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].evidenceClass, "okx_demo")
        self.assertEqual(rows[0].outcome["demoReleaseId"], "demo-release-1")

    def test_live_outcome_requires_matching_release_and_risk_profile(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            connection = connect_registry(Path(directory) / "registry.sqlite")
            try:
                repository = RegistryRepository(connection)
                lineage = register_lineage(repository, live=True)
                source = Path(directory) / "live-outcomes.json"
                source.write_text(json.dumps(export_payload(lineage, live=True)), encoding="utf-8")
                result = import_execution_outcome_export(source, repository=repository)
                row = repository.list_outcomes()[0]
            finally:
                connection.close()

        self.assertEqual(result.importedCount, 1)
        self.assertEqual(row.evidenceClass, "live")
        self.assertEqual(row.outcome["liveReleaseId"], "live-release-1")
        self.assertEqual(row.outcome["riskProfileId"], "risk-profile-1")

    def test_missing_parent_snapshot_is_quarantined_without_fabrication(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            connection = connect_registry(Path(directory) / "registry.sqlite")
            try:
                repository = RegistryRepository(connection)
                lineage = register_lineage(repository)
                source = Path(directory) / "missing-snapshot.json"
                source.write_text(
                    json.dumps(export_payload(lineage, snapshot_id="missing-snapshot")),
                    encoding="utf-8",
                )
                result = import_execution_outcome_export(source, repository=repository)
                count = repository.count("OutcomeLedger")
            finally:
                connection.close()

        self.assertEqual(result.status, "blocked_all_execution_outcomes_quarantined")
        self.assertEqual(result.quarantined[0]["reason"], "data_snapshot_missing")
        self.assertEqual(count, 0)
        self.assertFalse(result.to_dict()["inventedLineage"])

    def test_manifest_tampering_fails_before_import(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            connection = connect_registry(Path(directory) / "registry.sqlite")
            try:
                repository = RegistryRepository(connection)
                lineage = register_lineage(repository)
                payload = export_payload(lineage)
                payload["records"][0]["direction"] = "short"
                source = Path(directory) / "tampered.json"
                source.write_text(json.dumps(payload), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "manifest_mismatch"):
                    import_execution_outcome_export(source, repository=repository)
            finally:
                connection.close()


if __name__ == "__main__":
    unittest.main()
