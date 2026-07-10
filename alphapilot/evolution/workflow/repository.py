"""SQLite persistence for workflow records using the evolution registry."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from alphapilot.evolution.registry.hashing import canonical_json, stable_hash
from alphapilot.evolution.registry.repositories import ImmutableRecordConflict
from alphapilot.evolution.registry.types import utc_now

from .states import WorkflowConflict, validate_stage, validate_status
from .types import (
    FailureDiagnosisRecord,
    GateProfileRecord,
    StageEventRecord,
    StrategyVersionRecord,
    WorkflowRunRecord,
)


WORKFLOW_TABLES = {
    "StrategyVersions",
    "GateProfiles",
    "WorkflowRuns",
    "StageEvents",
    "FailureDiagnoses",
}

def _decode_json(value: str) -> Any:
    return json.loads(value)


class WorkflowRepository:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def count(self, table: str) -> int:
        if table not in WORKFLOW_TABLES:
            raise ValueError(f"Unsupported workflow table: {table}")
        return int(self.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])

    def strategy_family_exists(self, strategy_family_id: str) -> bool:
        row = self.connection.execute(
            "SELECT 1 FROM StrategyFamilies WHERE strategyFamilyId = ?",
            (strategy_family_id,),
        ).fetchone()
        return row is not None

    def create_strategy_version(
        self, record: StrategyVersionRecord
    ) -> StrategyVersionRecord:
        existing = self.get_strategy_version(record.strategyVersionId)
        if existing:
            self._assert_same_hash(
                record.strategyVersionId, existing.contentHash, record.contentHash
            )
            return existing
        same_content = self.connection.execute(
            "SELECT * FROM StrategyVersions WHERE strategyFamilyId = ? AND contentHash = ?",
            (record.strategyFamilyId, record.contentHash),
        ).fetchone()
        if same_content is not None:
            stored = self._strategy_version_from_row(same_content)
            if (
                record.parentStrategyVersionId is not None
                and stored.parentStrategyVersionId != record.parentStrategyVersionId
            ):
                raise WorkflowConflict(
                    f"strategy_content_already_registered:{stored.strategyVersionId}"
                )
            return stored
        try:
            with self.connection:
                self.connection.execute(
                    """
                    INSERT INTO StrategyVersions(
                      strategyVersionId, strategyFamilyId, parentStrategyVersionId,
                      strategyCandidateId, displayName, sourceType, status,
                      definitionJson, parametersJson, modelArtifactId, contentHash, createdAt
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record.strategyVersionId,
                        record.strategyFamilyId,
                        record.parentStrategyVersionId,
                        record.strategyCandidateId,
                        record.displayName,
                        record.sourceType,
                        record.status,
                        canonical_json(record.definition),
                        canonical_json(record.parameters),
                        record.modelArtifactId,
                        record.contentHash,
                        record.createdAt,
                    ),
                )
        except sqlite3.IntegrityError as error:
            raise WorkflowConflict(f"strategy_version_insert_conflict:{error}") from error
        return record

    def get_strategy_version(self, record_id: str) -> StrategyVersionRecord | None:
        row = self.connection.execute(
            "SELECT * FROM StrategyVersions WHERE strategyVersionId = ?",
            (record_id,),
        ).fetchone()
        return self._strategy_version_from_row(row) if row else None

    def list_strategy_versions(self) -> list[StrategyVersionRecord]:
        rows = self.connection.execute(
            "SELECT * FROM StrategyVersions ORDER BY createdAt, strategyVersionId"
        ).fetchall()
        return [self._strategy_version_from_row(row) for row in rows]

    def create_gate_profile(self, record: GateProfileRecord) -> GateProfileRecord:
        validate_stage(record.stage)
        if record.version < 1:
            raise WorkflowConflict("gate_profile_version_must_be_positive")
        existing = self.get_gate_profile(record.gateProfileId)
        if existing:
            self._assert_same_hash(
                record.gateProfileId, existing.contentHash, record.contentHash
            )
            return existing
        if stable_hash(record.rules) != record.contentHash:
            raise WorkflowConflict("gate_profile_rules_hash_mismatch")
        try:
            with self.connection:
                self.connection.execute(
                    """
                    INSERT INTO GateProfiles(
                      gateProfileId, profileKey, version, stage, status,
                      rulesJson, contentHash, createdAt
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record.gateProfileId,
                        record.profileKey,
                        record.version,
                        record.stage,
                        record.status,
                        canonical_json(record.rules),
                        record.contentHash,
                        record.createdAt,
                    ),
                )
        except sqlite3.IntegrityError as error:
            raise WorkflowConflict(f"gate_profile_insert_conflict:{error}") from error
        return record

    def get_gate_profile(self, record_id: str) -> GateProfileRecord | None:
        row = self.connection.execute(
            "SELECT * FROM GateProfiles WHERE gateProfileId = ?", (record_id,)
        ).fetchone()
        if row is None:
            return None
        return GateProfileRecord(
            gateProfileId=row["gateProfileId"],
            profileKey=row["profileKey"],
            version=int(row["version"]),
            stage=row["stage"],
            status=row["status"],
            rules=_decode_json(row["rulesJson"]),
            contentHash=row["contentHash"],
            createdAt=row["createdAt"],
        )

    def create_workflow_run(
        self,
        *,
        strategy_version_id: str,
        stage: str,
        status: str,
        attempt_number: int,
        gate_profile_id: str | None,
        risk_profile_id: str | None,
        idempotency_key: str,
        progress: dict[str, Any],
        result: dict[str, Any],
    ) -> WorkflowRunRecord:
        validate_stage(stage)
        validate_status(status)
        if attempt_number < 1:
            raise WorkflowConflict("workflow_attempt_number_must_be_positive")
        core = {
            "strategyVersionId": strategy_version_id,
            "stage": stage,
            "attemptNumber": attempt_number,
            "gateProfileId": gate_profile_id,
            "riskProfileId": risk_profile_id,
            "idempotencyKey": idempotency_key,
        }
        content_hash = stable_hash(core)
        workflow_run_id = stable_hash(
            {"idempotencyKey": idempotency_key, "contentHash": content_hash},
            prefix="workflow_run",
        )
        existing = self.get_workflow_run_by_idempotency_key(idempotency_key)
        if existing:
            self._assert_same_hash(workflow_run_id, existing.contentHash, content_hash)
            return existing
        now = utc_now()
        record = WorkflowRunRecord(
            workflowRunId=workflow_run_id,
            strategyVersionId=strategy_version_id,
            stage=stage,
            status=status,
            attemptNumber=attempt_number,
            gateProfileId=gate_profile_id,
            riskProfileId=risk_profile_id,
            idempotencyKey=idempotency_key,
            progress=progress,
            result=result,
            startedAt=now if status == "running" else None,
            checkpointAt=None,
            completedAt=now if status in {"passed", "failed", "cancelled", "retired"} else None,
            contentHash=content_hash,
            createdAt=now,
            updatedAt=now,
        )
        try:
            with self.connection:
                self.connection.execute(
                    """
                    INSERT INTO WorkflowRuns(
                      workflowRunId, strategyVersionId, stage, status, attemptNumber,
                      gateProfileId, riskProfileId, idempotencyKey, progressJson,
                      resultJson, startedAt, checkpointAt, completedAt, contentHash,
                      createdAt, updatedAt
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record.workflowRunId,
                        record.strategyVersionId,
                        record.stage,
                        record.status,
                        record.attemptNumber,
                        record.gateProfileId,
                        record.riskProfileId,
                        record.idempotencyKey,
                        canonical_json(record.progress),
                        canonical_json(record.result),
                        record.startedAt,
                        record.checkpointAt,
                        record.completedAt,
                        record.contentHash,
                        record.createdAt,
                        record.updatedAt,
                    ),
                )
        except sqlite3.IntegrityError as error:
            raise WorkflowConflict(f"active_workflow_run_conflict:{error}") from error
        return record

    def get_workflow_run(self, record_id: str) -> WorkflowRunRecord | None:
        row = self.connection.execute(
            "SELECT * FROM WorkflowRuns WHERE workflowRunId = ?", (record_id,)
        ).fetchone()
        return self._workflow_run_from_row(row) if row else None

    def get_workflow_run_by_idempotency_key(
        self, idempotency_key: str
    ) -> WorkflowRunRecord | None:
        row = self.connection.execute(
            "SELECT * FROM WorkflowRuns WHERE idempotencyKey = ?",
            (idempotency_key,),
        ).fetchone()
        return self._workflow_run_from_row(row) if row else None

    def get_latest_workflow_run(
        self, strategy_version_id: str, *, stage: str | None = None
    ) -> WorkflowRunRecord | None:
        query = "SELECT * FROM WorkflowRuns WHERE strategyVersionId = ?"
        params: list[Any] = [strategy_version_id]
        if stage is not None:
            query += " AND stage = ?"
            params.append(stage)
        query += " ORDER BY createdAt DESC, attemptNumber DESC, workflowRunId DESC LIMIT 1"
        row = self.connection.execute(query, params).fetchone()
        return self._workflow_run_from_row(row) if row else None

    def list_workflow_runs(
        self,
        *,
        strategy_version_id: str | None = None,
        stage: str | None = None,
        status: str | None = None,
    ) -> list[WorkflowRunRecord]:
        clauses: list[str] = []
        params: list[Any] = []
        if strategy_version_id is not None:
            clauses.append("strategyVersionId = ?")
            params.append(strategy_version_id)
        if stage is not None:
            clauses.append("stage = ?")
            params.append(stage)
        if status is not None:
            clauses.append("status = ?")
            params.append(status)
        query = "SELECT * FROM WorkflowRuns"
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY createdAt, attemptNumber, workflowRunId"
        rows = self.connection.execute(query, params).fetchall()
        return [self._workflow_run_from_row(row) for row in rows]

    def create_stage_event(self, record: StageEventRecord) -> StageEventRecord:
        existing = self.connection.execute(
            "SELECT contentHash FROM StageEvents WHERE stageEventId = ?",
            (record.stageEventId,),
        ).fetchone()
        if existing:
            self._assert_same_hash(
                record.stageEventId, existing["contentHash"], record.contentHash
            )
            return record
        with self.connection:
            self._insert_stage_event(record)
        return record

    def list_stage_events(
        self,
        *,
        workflow_run_id: str | None = None,
        strategy_version_id: str | None = None,
    ) -> list[StageEventRecord]:
        clauses: list[str] = []
        params: list[Any] = []
        if workflow_run_id is not None:
            clauses.append("workflowRunId = ?")
            params.append(workflow_run_id)
        if strategy_version_id is not None:
            clauses.append("strategyVersionId = ?")
            params.append(strategy_version_id)
        query = "SELECT * FROM StageEvents"
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY createdAt, stageEventId"
        rows = self.connection.execute(query, params).fetchall()
        return [self._stage_event_from_row(row) for row in rows]

    def get_latest_failure_diagnosis(
        self, workflow_run_id: str
    ) -> FailureDiagnosisRecord | None:
        row = self.connection.execute(
            """
            SELECT * FROM FailureDiagnoses
            WHERE workflowRunId = ?
            ORDER BY createdAt DESC, failureDiagnosisId DESC
            LIMIT 1
            """,
            (workflow_run_id,),
        ).fetchone()
        return self._failure_diagnosis_from_row(row) if row else None

    def list_failure_diagnoses(
        self, *, workflow_run_id: str | None = None
    ) -> list[FailureDiagnosisRecord]:
        query = "SELECT * FROM FailureDiagnoses"
        params: list[Any] = []
        if workflow_run_id is not None:
            query += " WHERE workflowRunId = ?"
            params.append(workflow_run_id)
        query += " ORDER BY createdAt, failureDiagnosisId"
        rows = self.connection.execute(query, params).fetchall()
        return [self._failure_diagnosis_from_row(row) for row in rows]

    def apply_workflow_update(
        self,
        *,
        updated: WorkflowRunRecord,
        expected_status: str,
        event: StageEventRecord,
        diagnosis: FailureDiagnosisRecord | None = None,
    ) -> WorkflowRunRecord:
        try:
            with self.connection:
                cursor = self.connection.execute(
                    """
                    UPDATE WorkflowRuns SET
                      status = ?, progressJson = ?, resultJson = ?, startedAt = ?,
                      checkpointAt = ?, completedAt = ?, updatedAt = ?
                    WHERE workflowRunId = ? AND status = ?
                    """,
                    (
                        updated.status,
                        canonical_json(updated.progress),
                        canonical_json(updated.result),
                        updated.startedAt,
                        updated.checkpointAt,
                        updated.completedAt,
                        updated.updatedAt,
                        updated.workflowRunId,
                        expected_status,
                    ),
                )
                if cursor.rowcount != 1:
                    raise WorkflowConflict(
                        f"workflow_status_changed:{updated.workflowRunId}:{expected_status}"
                    )
                if diagnosis is not None:
                    self._insert_failure_diagnosis(diagnosis)
                self._insert_stage_event(event)
        except sqlite3.IntegrityError as error:
            raise WorkflowConflict(f"workflow_update_conflict:{error}") from error
        stored = self.get_workflow_run(updated.workflowRunId)
        if stored is None:
            raise WorkflowConflict(f"workflow_run_missing_after_update:{updated.workflowRunId}")
        return stored

    def _insert_stage_event(self, record: StageEventRecord) -> None:
        self.connection.execute(
            """
            INSERT INTO StageEvents(
              stageEventId, workflowRunId, strategyVersionId, previousStage,
              nextStage, previousStatus, nextStatus, reasonCode, actor,
              evidenceJson, contentHash, createdAt
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.stageEventId,
                record.workflowRunId,
                record.strategyVersionId,
                record.previousStage,
                record.nextStage,
                record.previousStatus,
                record.nextStatus,
                record.reasonCode,
                record.actor,
                canonical_json(record.evidence),
                record.contentHash,
                record.createdAt,
            ),
        )

    def _insert_failure_diagnosis(self, record: FailureDiagnosisRecord) -> None:
        self.connection.execute(
            """
            INSERT INTO FailureDiagnoses(
              failureDiagnosisId, workflowRunId, category, summary,
              retryDisposition, metricsJson, suggestionsJson, contentHash, createdAt
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.failureDiagnosisId,
                record.workflowRunId,
                record.category,
                record.summary,
                record.retryDisposition,
                canonical_json(record.metrics),
                canonical_json(record.suggestions),
                record.contentHash,
                record.createdAt,
            ),
        )

    @staticmethod
    def _assert_same_hash(record_id: str, existing_hash: str, incoming_hash: str) -> None:
        if existing_hash != incoming_hash:
            raise ImmutableRecordConflict(
                f"Immutable record conflict for {record_id}: existing and incoming hashes differ"
            )

    @staticmethod
    def _strategy_version_from_row(row: sqlite3.Row) -> StrategyVersionRecord:
        return StrategyVersionRecord(
            strategyVersionId=row["strategyVersionId"],
            strategyFamilyId=row["strategyFamilyId"],
            parentStrategyVersionId=row["parentStrategyVersionId"],
            strategyCandidateId=row["strategyCandidateId"],
            displayName=row["displayName"],
            sourceType=row["sourceType"],
            status=row["status"],
            definition=_decode_json(row["definitionJson"]),
            parameters=_decode_json(row["parametersJson"]),
            modelArtifactId=row["modelArtifactId"],
            contentHash=row["contentHash"],
            createdAt=row["createdAt"],
        )

    @staticmethod
    def _workflow_run_from_row(row: sqlite3.Row) -> WorkflowRunRecord:
        return WorkflowRunRecord(
            workflowRunId=row["workflowRunId"],
            strategyVersionId=row["strategyVersionId"],
            stage=row["stage"],
            status=row["status"],
            attemptNumber=int(row["attemptNumber"]),
            gateProfileId=row["gateProfileId"],
            riskProfileId=row["riskProfileId"],
            idempotencyKey=row["idempotencyKey"],
            progress=_decode_json(row["progressJson"]),
            result=_decode_json(row["resultJson"]),
            startedAt=row["startedAt"],
            checkpointAt=row["checkpointAt"],
            completedAt=row["completedAt"],
            contentHash=row["contentHash"],
            createdAt=row["createdAt"],
            updatedAt=row["updatedAt"],
        )

    @staticmethod
    def _stage_event_from_row(row: sqlite3.Row) -> StageEventRecord:
        return StageEventRecord(
            stageEventId=row["stageEventId"],
            workflowRunId=row["workflowRunId"],
            strategyVersionId=row["strategyVersionId"],
            previousStage=row["previousStage"],
            nextStage=row["nextStage"],
            previousStatus=row["previousStatus"],
            nextStatus=row["nextStatus"],
            reasonCode=row["reasonCode"],
            actor=row["actor"],
            evidence=_decode_json(row["evidenceJson"]),
            contentHash=row["contentHash"],
            createdAt=row["createdAt"],
        )

    @staticmethod
    def _failure_diagnosis_from_row(row: sqlite3.Row) -> FailureDiagnosisRecord:
        return FailureDiagnosisRecord(
            failureDiagnosisId=row["failureDiagnosisId"],
            workflowRunId=row["workflowRunId"],
            category=row["category"],
            summary=row["summary"],
            retryDisposition=row["retryDisposition"],
            metrics=_decode_json(row["metricsJson"]),
            suggestions=list(_decode_json(row["suggestionsJson"])),
            contentHash=row["contentHash"],
            createdAt=row["createdAt"],
        )
