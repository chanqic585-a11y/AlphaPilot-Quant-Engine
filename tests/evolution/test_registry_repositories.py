from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from alphapilot.evolution.registry.database import connect_registry
from alphapilot.evolution.registry.repositories import ImmutableRecordConflict, RegistryRepository
from alphapilot.evolution.registry.hashing import stable_hash
from alphapilot.evolution.registry.types import (
    DataSnapshotRecord,
    FactorDefinitionRecord,
    OutcomeLedgerRecord,
)


class RegistryRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.connection = connect_registry(Path(self.directory.name) / "registry.sqlite")
        self.repository = RegistryRepository(self.connection)

    def tearDown(self) -> None:
        self.connection.close()
        self.directory.cleanup()

    def test_data_snapshot_create_is_idempotent(self) -> None:
        record = DataSnapshotRecord(
            dataSnapshotId="data_snapshot_test",
            source="unit_test",
            exchange="okx",
            marketType="swap",
            timeframe="1h",
            startTime="2026-01-01T00:00:00+00:00",
            endTime="2026-01-02T00:00:00+00:00",
            pointInTimeCutoff="2026-01-02T00:00:00+00:00",
            manifest={"files": []},
            contentHash="hash-a",
            createdAt="2026-01-02T01:00:00+00:00",
        )

        first = self.repository.create_data_snapshot(record)
        second = self.repository.create_data_snapshot(record)

        self.assertEqual(first, second)
        self.assertEqual(self.repository.count("DataSnapshots"), 1)

    def test_same_id_with_different_content_fails_closed(self) -> None:
        first = DataSnapshotRecord(
            dataSnapshotId="data_snapshot_conflict",
            source="unit_test",
            exchange="okx",
            marketType="swap",
            timeframe="1h",
            startTime=None,
            endTime=None,
            pointInTimeCutoff=None,
            manifest={"files": []},
            contentHash="hash-a",
            createdAt="2026-01-02T01:00:00+00:00",
        )
        conflict = DataSnapshotRecord(**{**first.__dict__, "contentHash": "hash-b"})

        self.repository.create_data_snapshot(first)
        with self.assertRaises(ImmutableRecordConflict):
            self.repository.create_data_snapshot(conflict)

    def test_factor_definition_and_audit_events_are_persisted(self) -> None:
        factor = FactorDefinitionRecord(
            factorDefinitionId="factor_test",
            name="Test Factor",
            version="1",
            expression="rolling_mean(close, 5)",
            definition={"requiredFields": ["close"]},
            contentHash="factor-hash",
            createdAt="2026-01-02T01:00:00+00:00",
        )
        self.repository.create_factor_definition(factor)
        first_event = self.repository.append_audit_event(
            eventType="factor_registered",
            entityType="FactorDefinition",
            entityId=factor.factorDefinitionId,
            payload={"source": "unit_test"},
        )
        second_event = self.repository.append_audit_event(
            eventType="factor_reviewed",
            entityType="FactorDefinition",
            entityId=factor.factorDefinitionId,
            payload={"status": "research_only"},
        )

        self.assertEqual(self.repository.get_factor_definition("factor_test"), factor)
        self.assertNotEqual(first_event.auditEventId, second_event.auditEventId)
        self.assertEqual(self.repository.count("AuditEvents"), 2)

    def test_outcome_ledger_is_immutable_and_filterable(self) -> None:
        snapshot = DataSnapshotRecord(
            dataSnapshotId="data_snapshot_outcome",
            source="unit_test",
            exchange="okx",
            marketType="swap",
            timeframe="4h",
            startTime="2026-01-01T00:00:00+00:00",
            endTime="2026-01-03T00:00:00+00:00",
            pointInTimeCutoff="2026-01-03T00:00:00+00:00",
            manifest={"files": []},
            contentHash="snapshot-hash",
        )
        self.repository.create_data_snapshot(snapshot)
        payload = {"netR": 1.8, "evidenceClass": "historical_path_replay"}
        record = OutcomeLedgerRecord(
            outcomeId="outcome_test",
            evidenceClass="historical_path_replay",
            sourceEntityType="engine_probe",
            sourceEntityId="probe_v1",
            dataSnapshotId=snapshot.dataSnapshotId,
            strategyCandidateId=None,
            instrumentId="BTC-USDT-SWAP",
            timeframe="4h",
            direction="long",
            decisionAt="2026-01-01T00:00:00+00:00",
            entryAt="2026-01-01T04:00:00+00:00",
            exitAt="2026-01-01T08:00:00+00:00",
            status="closed",
            outcome=payload,
            contentHash=stable_hash(payload),
        )
        self.repository.create_outcome(record)
        self.repository.create_outcome(record)

        rows = self.repository.list_outcomes(
            source_entity_type="engine_probe", source_entity_id="probe_v1"
        )

        self.assertEqual(rows, [record])
        self.assertEqual(self.repository.count("OutcomeLedger"), 1)


if __name__ == "__main__":
    unittest.main()
