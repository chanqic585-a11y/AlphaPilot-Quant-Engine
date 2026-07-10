"""Typed, immutable repository operations for evolution metadata."""

from __future__ import annotations

import json
import sqlite3
import uuid
from typing import Any

from .hashing import canonical_json
from .types import (
    AuditEventRecord,
    DataSnapshotRecord,
    ExperimentRecord,
    FactorDefinitionRecord,
    FactorRunRecord,
    LegacyEvidenceRecord,
    ModelRecord,
    StrategyCandidateRecord,
    StrategyFamilyRecord,
)


class ImmutableRecordConflict(RuntimeError):
    """Raised when an immutable id is reused with different content."""


ALLOWED_COUNT_TABLES = {
    "DataSnapshots",
    "FactorDefinitions",
    "FactorRuns",
    "Experiments",
    "Models",
    "StrategyFamilies",
    "StrategyCandidates",
    "PromotionDecisions",
    "DemoReleases",
    "LiveCandidatePackages",
    "DriftEvents",
    "AuditEvents",
    "LegacyEvidence",
}


def _decode_json(value: str) -> Any:
    return json.loads(value)


class RegistryRepository:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def count(self, table: str) -> int:
        if table not in ALLOWED_COUNT_TABLES:
            raise ValueError(f"Unsupported registry table: {table}")
        return int(self.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])

    def create_data_snapshot(self, record: DataSnapshotRecord) -> DataSnapshotRecord:
        existing = self.get_data_snapshot(record.dataSnapshotId)
        if existing:
            self._assert_same_hash(record.dataSnapshotId, existing.contentHash, record.contentHash)
            return existing
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO DataSnapshots(
                  dataSnapshotId, source, exchange, marketType, timeframe,
                  startTime, endTime, pointInTimeCutoff, manifestJson, contentHash, createdAt
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.dataSnapshotId,
                    record.source,
                    record.exchange,
                    record.marketType,
                    record.timeframe,
                    record.startTime,
                    record.endTime,
                    record.pointInTimeCutoff,
                    canonical_json(record.manifest),
                    record.contentHash,
                    record.createdAt,
                ),
            )
        return record

    def get_data_snapshot(self, record_id: str) -> DataSnapshotRecord | None:
        row = self.connection.execute(
            "SELECT * FROM DataSnapshots WHERE dataSnapshotId = ?",
            (record_id,),
        ).fetchone()
        if not row:
            return None
        return DataSnapshotRecord(
            dataSnapshotId=row["dataSnapshotId"],
            source=row["source"],
            exchange=row["exchange"],
            marketType=row["marketType"],
            timeframe=row["timeframe"],
            startTime=row["startTime"],
            endTime=row["endTime"],
            pointInTimeCutoff=row["pointInTimeCutoff"],
            manifest=_decode_json(row["manifestJson"]),
            contentHash=row["contentHash"],
            createdAt=row["createdAt"],
        )

    def create_factor_definition(self, record: FactorDefinitionRecord) -> FactorDefinitionRecord:
        existing = self.get_factor_definition(record.factorDefinitionId)
        if existing:
            self._assert_same_hash(record.factorDefinitionId, existing.contentHash, record.contentHash)
            return existing
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO FactorDefinitions(
                  factorDefinitionId, name, version, expression,
                  definitionJson, contentHash, createdAt
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.factorDefinitionId,
                    record.name,
                    record.version,
                    record.expression,
                    canonical_json(record.definition),
                    record.contentHash,
                    record.createdAt,
                ),
            )
        return record

    def get_factor_definition(self, record_id: str) -> FactorDefinitionRecord | None:
        row = self.connection.execute(
            "SELECT * FROM FactorDefinitions WHERE factorDefinitionId = ?",
            (record_id,),
        ).fetchone()
        if not row:
            return None
        return FactorDefinitionRecord(
            factorDefinitionId=row["factorDefinitionId"],
            name=row["name"],
            version=row["version"],
            expression=row["expression"],
            definition=_decode_json(row["definitionJson"]),
            contentHash=row["contentHash"],
            createdAt=row["createdAt"],
        )

    def list_factor_definitions(self) -> list[FactorDefinitionRecord]:
        rows = self.connection.execute(
            "SELECT * FROM FactorDefinitions ORDER BY name, factorDefinitionId"
        ).fetchall()
        return [
            FactorDefinitionRecord(
                factorDefinitionId=row["factorDefinitionId"],
                name=row["name"],
                version=row["version"],
                expression=row["expression"],
                definition=_decode_json(row["definitionJson"]),
                contentHash=row["contentHash"],
                createdAt=row["createdAt"],
            )
            for row in rows
        ]

    def create_factor_run(self, record: FactorRunRecord) -> FactorRunRecord:
        existing = self.get_factor_run(record.factorRunId)
        if existing:
            self._assert_same_hash(record.factorRunId, existing.contentHash, record.contentHash)
            return existing
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO FactorRuns(
                  factorRunId, factorDefinitionId, dataSnapshotId, codeCommit,
                  configHash, resultPath, resultSha256, status, payloadJson,
                  contentHash, createdAt
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.factorRunId,
                    record.factorDefinitionId,
                    record.dataSnapshotId,
                    record.codeCommit,
                    record.configHash,
                    record.resultPath,
                    record.resultSha256,
                    record.status,
                    canonical_json(record.payload),
                    record.contentHash,
                    record.createdAt,
                ),
            )
        return record

    def get_factor_run(self, record_id: str) -> FactorRunRecord | None:
        row = self.connection.execute(
            "SELECT * FROM FactorRuns WHERE factorRunId = ?", (record_id,)
        ).fetchone()
        if not row:
            return None
        return FactorRunRecord(
            factorRunId=row["factorRunId"],
            factorDefinitionId=row["factorDefinitionId"],
            dataSnapshotId=row["dataSnapshotId"],
            codeCommit=row["codeCommit"],
            configHash=row["configHash"],
            resultPath=row["resultPath"],
            resultSha256=row["resultSha256"],
            status=row["status"],
            payload=_decode_json(row["payloadJson"]),
            contentHash=row["contentHash"],
            createdAt=row["createdAt"],
        )

    def create_experiment(self, record: ExperimentRecord) -> ExperimentRecord:
        existing = self.get_experiment(record.experimentId)
        if existing:
            self._assert_same_hash(record.experimentId, existing.contentHash, record.contentHash)
            return existing
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO Experiments(
                  experimentId, experimentType, status, dataSnapshotId,
                  splitDefinitionJson, costModelJson, parametersJson, codeCommit,
                  payloadJson, contentHash, createdAt
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.experimentId,
                    record.experimentType,
                    record.status,
                    record.dataSnapshotId,
                    canonical_json(record.splitDefinition),
                    canonical_json(record.costModel),
                    canonical_json(record.parameters),
                    record.codeCommit,
                    canonical_json(record.payload),
                    record.contentHash,
                    record.createdAt,
                ),
            )
        return record

    def get_experiment(self, record_id: str) -> ExperimentRecord | None:
        row = self.connection.execute(
            "SELECT * FROM Experiments WHERE experimentId = ?", (record_id,)
        ).fetchone()
        if not row:
            return None
        return ExperimentRecord(
            experimentId=row["experimentId"],
            experimentType=row["experimentType"],
            status=row["status"],
            dataSnapshotId=row["dataSnapshotId"],
            splitDefinition=_decode_json(row["splitDefinitionJson"]),
            costModel=_decode_json(row["costModelJson"]),
            parameters=_decode_json(row["parametersJson"]),
            codeCommit=row["codeCommit"],
            payload=_decode_json(row["payloadJson"]),
            contentHash=row["contentHash"],
            createdAt=row["createdAt"],
        )

    def create_model(self, record: ModelRecord) -> ModelRecord:
        existing = self.get_model(record.modelId)
        if existing:
            self._assert_same_hash(record.modelId, existing.contentHash, record.contentHash)
            return existing
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO Models(
                  modelId, experimentId, algorithm, status, artifactPath,
                  artifactSha256, payloadJson, contentHash, createdAt
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.modelId,
                    record.experimentId,
                    record.algorithm,
                    record.status,
                    record.artifactPath,
                    record.artifactSha256,
                    canonical_json(record.payload),
                    record.contentHash,
                    record.createdAt,
                ),
            )
        return record

    def get_model(self, record_id: str) -> ModelRecord | None:
        row = self.connection.execute("SELECT * FROM Models WHERE modelId = ?", (record_id,)).fetchone()
        if not row:
            return None
        return ModelRecord(
            modelId=row["modelId"],
            experimentId=row["experimentId"],
            algorithm=row["algorithm"],
            status=row["status"],
            artifactPath=row["artifactPath"],
            artifactSha256=row["artifactSha256"],
            payload=_decode_json(row["payloadJson"]),
            contentHash=row["contentHash"],
            createdAt=row["createdAt"],
        )

    def list_models(self) -> list[ModelRecord]:
        rows = self.connection.execute("SELECT * FROM Models ORDER BY createdAt, modelId").fetchall()
        return [self.get_model(row["modelId"]) for row in rows if row]

    def create_strategy_family(self, record: StrategyFamilyRecord) -> StrategyFamilyRecord:
        existing = self.get_strategy_family(record.strategyFamilyId)
        if existing:
            self._assert_same_hash(record.strategyFamilyId, existing.contentHash, record.contentHash)
            return existing
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO StrategyFamilies(
                  strategyFamilyId, familyKey, name, status, metadataJson, contentHash, createdAt
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.strategyFamilyId,
                    record.familyKey,
                    record.name,
                    record.status,
                    canonical_json(record.metadata),
                    record.contentHash,
                    record.createdAt,
                ),
            )
        return record

    def get_strategy_family(self, record_id: str) -> StrategyFamilyRecord | None:
        row = self.connection.execute(
            "SELECT * FROM StrategyFamilies WHERE strategyFamilyId = ?", (record_id,)
        ).fetchone()
        return self._strategy_family_from_row(row) if row else None

    def get_strategy_family_by_key(self, family_key: str) -> StrategyFamilyRecord | None:
        row = self.connection.execute(
            "SELECT * FROM StrategyFamilies WHERE familyKey = ?", (family_key,)
        ).fetchone()
        return self._strategy_family_from_row(row) if row else None

    def create_strategy_candidate(self, record: StrategyCandidateRecord) -> StrategyCandidateRecord:
        row = self.connection.execute(
            "SELECT * FROM StrategyCandidates WHERE strategyCandidateId = ?",
            (record.strategyCandidateId,),
        ).fetchone()
        if row:
            self._assert_same_hash(record.strategyCandidateId, row["contentHash"], record.contentHash)
            return StrategyCandidateRecord(
                strategyCandidateId=row["strategyCandidateId"],
                strategyFamilyId=row["strategyFamilyId"],
                name=row["name"],
                status=row["status"],
                candidate=_decode_json(row["candidateJson"]),
                contentHash=row["contentHash"],
                createdAt=row["createdAt"],
            )
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO StrategyCandidates(
                  strategyCandidateId, strategyFamilyId, name, status,
                  candidateJson, contentHash, createdAt
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.strategyCandidateId,
                    record.strategyFamilyId,
                    record.name,
                    record.status,
                    canonical_json(record.candidate),
                    record.contentHash,
                    record.createdAt,
                ),
            )
        return record

    def create_legacy_evidence(self, record: LegacyEvidenceRecord) -> LegacyEvidenceRecord:
        existing = self.get_legacy_evidence(record.legacyEvidenceId)
        if existing:
            self._assert_same_hash(record.legacyEvidenceId, existing.contentHash, record.contentHash)
            return existing
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO LegacyEvidence(
                  legacyEvidenceId, sourcePath, sourceSha256, evidenceType,
                  strategyFamilyId, familyFingerprint, ruleFingerprint,
                  classificationReasonsJson, payloadJson, contentHash, importedAt
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.legacyEvidenceId,
                    record.sourcePath,
                    record.sourceSha256,
                    record.evidenceType,
                    record.strategyFamilyId,
                    record.familyFingerprint,
                    record.ruleFingerprint,
                    canonical_json(record.classificationReasons),
                    canonical_json(record.payload),
                    record.contentHash,
                    record.importedAt,
                ),
            )
        return record

    def get_legacy_evidence(self, record_id: str) -> LegacyEvidenceRecord | None:
        row = self.connection.execute(
            "SELECT * FROM LegacyEvidence WHERE legacyEvidenceId = ?",
            (record_id,),
        ).fetchone()
        return self._legacy_evidence_from_row(row) if row else None

    def list_legacy_evidence(self) -> list[LegacyEvidenceRecord]:
        rows = self.connection.execute(
            "SELECT * FROM LegacyEvidence ORDER BY sourcePath, legacyEvidenceId"
        ).fetchall()
        return [self._legacy_evidence_from_row(row) for row in rows]

    def append_audit_event(
        self,
        *,
        eventType: str,
        entityType: str,
        entityId: str | None,
        payload: dict[str, Any],
    ) -> AuditEventRecord:
        record = AuditEventRecord(
            auditEventId=f"audit_{uuid.uuid4().hex}",
            eventType=eventType,
            entityType=entityType,
            entityId=entityId,
            payload=payload,
        )
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO AuditEvents(
                  auditEventId, eventType, entityType, entityId, payloadJson, createdAt
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    record.auditEventId,
                    record.eventType,
                    record.entityType,
                    record.entityId,
                    canonical_json(record.payload),
                    record.createdAt,
                ),
            )
        return record

    @staticmethod
    def _assert_same_hash(record_id: str, existing_hash: str, incoming_hash: str) -> None:
        if existing_hash != incoming_hash:
            raise ImmutableRecordConflict(
                f"Immutable record conflict for {record_id}: existing and incoming hashes differ"
            )

    @staticmethod
    def _strategy_family_from_row(row: sqlite3.Row) -> StrategyFamilyRecord:
        return StrategyFamilyRecord(
            strategyFamilyId=row["strategyFamilyId"],
            familyKey=row["familyKey"],
            name=row["name"],
            status=row["status"],
            metadata=_decode_json(row["metadataJson"]),
            contentHash=row["contentHash"],
            createdAt=row["createdAt"],
        )

    @staticmethod
    def _legacy_evidence_from_row(row: sqlite3.Row) -> LegacyEvidenceRecord:
        return LegacyEvidenceRecord(
            legacyEvidenceId=row["legacyEvidenceId"],
            sourcePath=row["sourcePath"],
            sourceSha256=row["sourceSha256"],
            evidenceType=row["evidenceType"],
            strategyFamilyId=row["strategyFamilyId"],
            familyFingerprint=row["familyFingerprint"],
            ruleFingerprint=row["ruleFingerprint"],
            classificationReasons=_decode_json(row["classificationReasonsJson"]),
            payload=_decode_json(row["payloadJson"]),
            contentHash=row["contentHash"],
            importedAt=row["importedAt"],
        )
