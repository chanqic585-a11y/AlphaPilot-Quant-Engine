"""Safe, idempotent SQLite migrations for the evolution metadata registry."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Iterable


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    statements: tuple[str, ...]


MIGRATIONS: tuple[Migration, ...] = (
    Migration(
        version=1,
        name="create_evolution_registry_v1",
        statements=(
            """
            CREATE TABLE IF NOT EXISTS DataSnapshots (
              dataSnapshotId TEXT PRIMARY KEY,
              source TEXT NOT NULL,
              exchange TEXT,
              marketType TEXT,
              timeframe TEXT,
              startTime TEXT,
              endTime TEXT,
              pointInTimeCutoff TEXT,
              manifestJson TEXT NOT NULL,
              contentHash TEXT NOT NULL,
              createdAt TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS FactorDefinitions (
              factorDefinitionId TEXT PRIMARY KEY,
              name TEXT NOT NULL,
              version TEXT NOT NULL,
              expression TEXT NOT NULL,
              definitionJson TEXT NOT NULL,
              contentHash TEXT NOT NULL,
              createdAt TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS FactorRuns (
              factorRunId TEXT PRIMARY KEY,
              factorDefinitionId TEXT NOT NULL,
              dataSnapshotId TEXT NOT NULL,
              codeCommit TEXT,
              configHash TEXT NOT NULL,
              resultPath TEXT,
              resultSha256 TEXT,
              status TEXT NOT NULL,
              payloadJson TEXT NOT NULL,
              contentHash TEXT NOT NULL,
              createdAt TEXT NOT NULL,
              FOREIGN KEY (factorDefinitionId) REFERENCES FactorDefinitions(factorDefinitionId),
              FOREIGN KEY (dataSnapshotId) REFERENCES DataSnapshots(dataSnapshotId)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS Experiments (
              experimentId TEXT PRIMARY KEY,
              experimentType TEXT NOT NULL,
              status TEXT NOT NULL,
              dataSnapshotId TEXT,
              splitDefinitionJson TEXT NOT NULL,
              costModelJson TEXT NOT NULL,
              parametersJson TEXT NOT NULL,
              codeCommit TEXT,
              payloadJson TEXT NOT NULL,
              contentHash TEXT NOT NULL,
              createdAt TEXT NOT NULL,
              FOREIGN KEY (dataSnapshotId) REFERENCES DataSnapshots(dataSnapshotId)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS Models (
              modelId TEXT PRIMARY KEY,
              experimentId TEXT NOT NULL,
              algorithm TEXT NOT NULL,
              status TEXT NOT NULL,
              artifactPath TEXT,
              artifactSha256 TEXT,
              payloadJson TEXT NOT NULL,
              contentHash TEXT NOT NULL,
              createdAt TEXT NOT NULL,
              FOREIGN KEY (experimentId) REFERENCES Experiments(experimentId)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS StrategyFamilies (
              strategyFamilyId TEXT PRIMARY KEY,
              familyKey TEXT NOT NULL,
              name TEXT NOT NULL,
              status TEXT NOT NULL,
              metadataJson TEXT NOT NULL,
              contentHash TEXT NOT NULL,
              createdAt TEXT NOT NULL
            )
            """,
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_strategy_families_key ON StrategyFamilies(familyKey)",
            """
            CREATE TABLE IF NOT EXISTS StrategyCandidates (
              strategyCandidateId TEXT PRIMARY KEY,
              strategyFamilyId TEXT NOT NULL,
              name TEXT NOT NULL,
              status TEXT NOT NULL,
              candidateJson TEXT NOT NULL,
              contentHash TEXT NOT NULL,
              createdAt TEXT NOT NULL,
              FOREIGN KEY (strategyFamilyId) REFERENCES StrategyFamilies(strategyFamilyId)
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_strategy_candidates_family ON StrategyCandidates(strategyFamilyId)",
            """
            CREATE TABLE IF NOT EXISTS PromotionDecisions (
              promotionDecisionId TEXT PRIMARY KEY,
              strategyCandidateId TEXT NOT NULL,
              fromStatus TEXT,
              toStatus TEXT NOT NULL,
              passed INTEGER NOT NULL,
              reasonsJson TEXT NOT NULL,
              evidenceJson TEXT NOT NULL,
              contentHash TEXT NOT NULL,
              createdAt TEXT NOT NULL,
              FOREIGN KEY (strategyCandidateId) REFERENCES StrategyCandidates(strategyCandidateId)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS DemoReleases (
              demoReleaseId TEXT PRIMARY KEY,
              strategyCandidateId TEXT NOT NULL,
              status TEXT NOT NULL,
              riskEnvelopeJson TEXT NOT NULL,
              releaseJson TEXT NOT NULL,
              contentHash TEXT NOT NULL,
              createdAt TEXT NOT NULL,
              FOREIGN KEY (strategyCandidateId) REFERENCES StrategyCandidates(strategyCandidateId)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS LiveCandidatePackages (
              liveCandidatePackageId TEXT PRIMARY KEY,
              demoReleaseId TEXT NOT NULL,
              status TEXT NOT NULL,
              packageJson TEXT NOT NULL,
              contentHash TEXT NOT NULL,
              createdAt TEXT NOT NULL,
              FOREIGN KEY (demoReleaseId) REFERENCES DemoReleases(demoReleaseId)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS DriftEvents (
              driftEventId TEXT PRIMARY KEY,
              demoReleaseId TEXT NOT NULL,
              severity TEXT NOT NULL,
              eventType TEXT NOT NULL,
              payloadJson TEXT NOT NULL,
              contentHash TEXT NOT NULL,
              createdAt TEXT NOT NULL,
              FOREIGN KEY (demoReleaseId) REFERENCES DemoReleases(demoReleaseId)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS AuditEvents (
              auditEventId TEXT PRIMARY KEY,
              eventType TEXT NOT NULL,
              entityType TEXT NOT NULL,
              entityId TEXT,
              payloadJson TEXT NOT NULL,
              createdAt TEXT NOT NULL
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_audit_events_entity ON AuditEvents(entityType, entityId)",
            """
            CREATE TABLE IF NOT EXISTS LegacyEvidence (
              legacyEvidenceId TEXT PRIMARY KEY,
              sourcePath TEXT NOT NULL,
              sourceSha256 TEXT NOT NULL,
              evidenceType TEXT NOT NULL,
              strategyFamilyId TEXT,
              familyFingerprint TEXT,
              ruleFingerprint TEXT,
              classificationReasonsJson TEXT NOT NULL,
              payloadJson TEXT NOT NULL,
              contentHash TEXT NOT NULL,
              importedAt TEXT NOT NULL,
              FOREIGN KEY (strategyFamilyId) REFERENCES StrategyFamilies(strategyFamilyId)
            )
            """,
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_legacy_evidence_source ON LegacyEvidence(sourcePath, sourceSha256)",
            "CREATE INDEX IF NOT EXISTS idx_legacy_evidence_family ON LegacyEvidence(strategyFamilyId)",
            "CREATE INDEX IF NOT EXISTS idx_legacy_evidence_type ON LegacyEvidence(evidenceType)",
        ),
    ),
    Migration(
        version=2,
        name="create_outcome_ledger_v2",
        statements=(
            """
            CREATE TABLE IF NOT EXISTS OutcomeLedger (
              outcomeId TEXT PRIMARY KEY,
              evidenceClass TEXT NOT NULL,
              sourceEntityType TEXT NOT NULL,
              sourceEntityId TEXT NOT NULL,
              dataSnapshotId TEXT NOT NULL,
              strategyCandidateId TEXT,
              instrumentId TEXT NOT NULL,
              timeframe TEXT NOT NULL,
              direction TEXT NOT NULL,
              decisionAt TEXT NOT NULL,
              entryAt TEXT NOT NULL,
              exitAt TEXT NOT NULL,
              status TEXT NOT NULL,
              outcomeJson TEXT NOT NULL,
              contentHash TEXT NOT NULL,
              createdAt TEXT NOT NULL,
              FOREIGN KEY (dataSnapshotId) REFERENCES DataSnapshots(dataSnapshotId),
              FOREIGN KEY (strategyCandidateId) REFERENCES StrategyCandidates(strategyCandidateId)
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_outcome_ledger_source ON OutcomeLedger(sourceEntityType, sourceEntityId)",
            "CREATE INDEX IF NOT EXISTS idx_outcome_ledger_snapshot ON OutcomeLedger(dataSnapshotId)",
            "CREATE INDEX IF NOT EXISTS idx_outcome_ledger_candidate ON OutcomeLedger(strategyCandidateId)",
            "CREATE INDEX IF NOT EXISTS idx_outcome_ledger_instrument ON OutcomeLedger(instrumentId, timeframe)",
            "CREATE INDEX IF NOT EXISTS idx_outcome_ledger_exit ON OutcomeLedger(exitAt)",
        ),
    ),
    Migration(
        version=3,
        name="create_local_forward_registry_v3",
        statements=(
            """
            CREATE TABLE IF NOT EXISTS ForwardReleases (
              forwardReleaseId TEXT PRIMARY KEY,
              strategyCandidateId TEXT NOT NULL,
              status TEXT NOT NULL,
              riskEnvelopeJson TEXT NOT NULL,
              releaseJson TEXT NOT NULL,
              contentHash TEXT NOT NULL,
              createdAt TEXT NOT NULL,
              FOREIGN KEY (strategyCandidateId) REFERENCES StrategyCandidates(strategyCandidateId)
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_forward_releases_candidate ON ForwardReleases(strategyCandidateId)",
            """
            CREATE TABLE IF NOT EXISTS ForwardSessions (
              forwardSessionId TEXT PRIMARY KEY,
              forwardReleaseId TEXT NOT NULL,
              accountId TEXT NOT NULL,
              initialEquity REAL NOT NULL,
              sessionJson TEXT NOT NULL,
              contentHash TEXT NOT NULL,
              startedAt TEXT NOT NULL,
              createdAt TEXT NOT NULL,
              FOREIGN KEY (forwardReleaseId) REFERENCES ForwardReleases(forwardReleaseId)
            )
            """,
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_forward_sessions_release_account ON ForwardSessions(forwardReleaseId, accountId)",
            """
            CREATE TABLE IF NOT EXISTS ForwardEvents (
              forwardEventId TEXT PRIMARY KEY,
              forwardSessionId TEXT NOT NULL,
              forwardReleaseId TEXT NOT NULL,
              eventType TEXT NOT NULL,
              observedAt TEXT NOT NULL,
              instrumentId TEXT,
              payloadJson TEXT NOT NULL,
              contentHash TEXT NOT NULL,
              createdAt TEXT NOT NULL,
              FOREIGN KEY (forwardSessionId) REFERENCES ForwardSessions(forwardSessionId),
              FOREIGN KEY (forwardReleaseId) REFERENCES ForwardReleases(forwardReleaseId)
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_forward_events_session ON ForwardEvents(forwardSessionId, observedAt)",
            "CREATE INDEX IF NOT EXISTS idx_forward_events_release ON ForwardEvents(forwardReleaseId, observedAt)",
            "CREATE INDEX IF NOT EXISTS idx_forward_events_type ON ForwardEvents(eventType, observedAt)",
        ),
    ),
    Migration(
        version=4,
        name="create_versioned_risk_profiles_v4",
        statements=(
            """
            CREATE TABLE IF NOT EXISTS RiskProfiles (
              riskProfileId TEXT PRIMARY KEY,
              profileKey TEXT NOT NULL,
              version INTEGER NOT NULL,
              environment TEXT NOT NULL,
              name TEXT NOT NULL,
              status TEXT NOT NULL,
              profileJson TEXT NOT NULL,
              safetyEnvelopeJson TEXT NOT NULL,
              contentHash TEXT NOT NULL,
              createdAt TEXT NOT NULL
            )
            """,
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_risk_profiles_key_version ON RiskProfiles(profileKey, version)",
            "CREATE INDEX IF NOT EXISTS idx_risk_profiles_environment ON RiskProfiles(environment, createdAt)",
            """
            CREATE TABLE IF NOT EXISTS RiskProfileActivations (
              activationId TEXT PRIMARY KEY,
              environment TEXT NOT NULL,
              riskProfileId TEXT NOT NULL,
              previousRiskProfileId TEXT,
              action TEXT NOT NULL,
              actor TEXT NOT NULL,
              reason TEXT NOT NULL,
              contentHash TEXT NOT NULL,
              createdAt TEXT NOT NULL,
              FOREIGN KEY (riskProfileId) REFERENCES RiskProfiles(riskProfileId),
              FOREIGN KEY (previousRiskProfileId) REFERENCES RiskProfiles(riskProfileId)
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_risk_profile_activations_environment ON RiskProfileActivations(environment, createdAt)",
        ),
    ),
    Migration(
        version=5,
        name="create_live_releases_v5",
        statements=(
            """
            CREATE TABLE IF NOT EXISTS LiveReleases (
              liveReleaseId TEXT PRIMARY KEY,
              liveCandidatePackageId TEXT NOT NULL,
              strategyCandidateId TEXT NOT NULL,
              status TEXT NOT NULL,
              riskProfileId TEXT NOT NULL,
              releaseJson TEXT NOT NULL,
              contentHash TEXT NOT NULL,
              createdAt TEXT NOT NULL,
              FOREIGN KEY (liveCandidatePackageId) REFERENCES LiveCandidatePackages(liveCandidatePackageId),
              FOREIGN KEY (strategyCandidateId) REFERENCES StrategyCandidates(strategyCandidateId),
              FOREIGN KEY (riskProfileId) REFERENCES RiskProfiles(riskProfileId)
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_live_releases_candidate ON LiveReleases(strategyCandidateId, createdAt)",
            "CREATE INDEX IF NOT EXISTS idx_live_releases_profile ON LiveReleases(riskProfileId, createdAt)",
            "CREATE INDEX IF NOT EXISTS idx_live_releases_status ON LiveReleases(status, createdAt)",
        ),
    ),
    Migration(
        version=6,
        name="create_workflow_orchestrator_v6",
        statements=(
            """
            CREATE TABLE IF NOT EXISTS StrategyVersions (
              strategyVersionId TEXT PRIMARY KEY,
              strategyFamilyId TEXT NOT NULL,
              parentStrategyVersionId TEXT,
              strategyCandidateId TEXT,
              displayName TEXT NOT NULL,
              sourceType TEXT NOT NULL,
              status TEXT NOT NULL,
              definitionJson TEXT NOT NULL,
              parametersJson TEXT NOT NULL,
              modelArtifactId TEXT,
              contentHash TEXT NOT NULL,
              createdAt TEXT NOT NULL,
              FOREIGN KEY (strategyFamilyId) REFERENCES StrategyFamilies(strategyFamilyId),
              FOREIGN KEY (parentStrategyVersionId) REFERENCES StrategyVersions(strategyVersionId),
              FOREIGN KEY (strategyCandidateId) REFERENCES StrategyCandidates(strategyCandidateId)
            )
            """,
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_strategy_versions_family_content ON StrategyVersions(strategyFamilyId, contentHash)",
            "CREATE INDEX IF NOT EXISTS idx_strategy_versions_parent ON StrategyVersions(parentStrategyVersionId, createdAt)",
            """
            CREATE TABLE IF NOT EXISTS GateProfiles (
              gateProfileId TEXT PRIMARY KEY,
              profileKey TEXT NOT NULL,
              version INTEGER NOT NULL,
              stage TEXT NOT NULL,
              status TEXT NOT NULL,
              rulesJson TEXT NOT NULL,
              contentHash TEXT NOT NULL,
              createdAt TEXT NOT NULL
            )
            """,
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_gate_profiles_key_version ON GateProfiles(profileKey, version)",
            "CREATE INDEX IF NOT EXISTS idx_gate_profiles_stage ON GateProfiles(stage, status, createdAt)",
            """
            CREATE TABLE IF NOT EXISTS WorkflowRuns (
              workflowRunId TEXT PRIMARY KEY,
              strategyVersionId TEXT NOT NULL,
              stage TEXT NOT NULL,
              status TEXT NOT NULL,
              attemptNumber INTEGER NOT NULL,
              gateProfileId TEXT,
              riskProfileId TEXT,
              idempotencyKey TEXT NOT NULL,
              progressJson TEXT NOT NULL,
              resultJson TEXT NOT NULL,
              startedAt TEXT,
              checkpointAt TEXT,
              completedAt TEXT,
              contentHash TEXT NOT NULL,
              createdAt TEXT NOT NULL,
              updatedAt TEXT NOT NULL,
              FOREIGN KEY (strategyVersionId) REFERENCES StrategyVersions(strategyVersionId),
              FOREIGN KEY (gateProfileId) REFERENCES GateProfiles(gateProfileId),
              FOREIGN KEY (riskProfileId) REFERENCES RiskProfiles(riskProfileId)
            )
            """,
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_workflow_runs_idempotency ON WorkflowRuns(idempotencyKey)",
            "CREATE INDEX IF NOT EXISTS idx_workflow_runs_version ON WorkflowRuns(strategyVersionId, stage, attemptNumber)",
            "CREATE INDEX IF NOT EXISTS idx_workflow_runs_status ON WorkflowRuns(stage, status, updatedAt)",
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_workflow_runs_active_stage ON WorkflowRuns(strategyVersionId, stage) WHERE status IN ('awaiting', 'queued', 'running', 'paused', 'blocked')",
            """
            CREATE TABLE IF NOT EXISTS StageEvents (
              stageEventId TEXT PRIMARY KEY,
              workflowRunId TEXT NOT NULL,
              strategyVersionId TEXT NOT NULL,
              previousStage TEXT,
              nextStage TEXT NOT NULL,
              previousStatus TEXT,
              nextStatus TEXT NOT NULL,
              reasonCode TEXT NOT NULL,
              actor TEXT NOT NULL,
              evidenceJson TEXT NOT NULL,
              contentHash TEXT NOT NULL,
              createdAt TEXT NOT NULL,
              FOREIGN KEY (workflowRunId) REFERENCES WorkflowRuns(workflowRunId),
              FOREIGN KEY (strategyVersionId) REFERENCES StrategyVersions(strategyVersionId)
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_stage_events_run ON StageEvents(workflowRunId, createdAt)",
            "CREATE INDEX IF NOT EXISTS idx_stage_events_version ON StageEvents(strategyVersionId, createdAt)",
            """
            CREATE TABLE IF NOT EXISTS FailureDiagnoses (
              failureDiagnosisId TEXT PRIMARY KEY,
              workflowRunId TEXT NOT NULL,
              category TEXT NOT NULL,
              summary TEXT NOT NULL,
              retryDisposition TEXT NOT NULL,
              metricsJson TEXT NOT NULL,
              suggestionsJson TEXT NOT NULL,
              contentHash TEXT NOT NULL,
              createdAt TEXT NOT NULL,
              FOREIGN KEY (workflowRunId) REFERENCES WorkflowRuns(workflowRunId)
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_failure_diagnoses_run ON FailureDiagnoses(workflowRunId, createdAt)",
            "CREATE INDEX IF NOT EXISTS idx_failure_diagnoses_category ON FailureDiagnoses(category, retryDisposition, createdAt)",
        ),
    ),
)


def _ensure_migration_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS RegistryMigrations (
          version INTEGER PRIMARY KEY,
          name TEXT NOT NULL,
          appliedAt TEXT NOT NULL
        )
        """
    )
    connection.commit()


def apply_migrations(
    connection: sqlite3.Connection,
    migrations: Iterable[Migration] = MIGRATIONS,
) -> int:
    _ensure_migration_table(connection)
    applied = 0
    for migration in sorted(migrations, key=lambda item: item.version):
        exists = connection.execute(
            "SELECT 1 FROM RegistryMigrations WHERE version = ?",
            (migration.version,),
        ).fetchone()
        if exists:
            continue
        try:
            connection.execute("BEGIN")
            for statement in migration.statements:
                connection.execute(statement)
            connection.execute(
                "INSERT INTO RegistryMigrations(version, name, appliedAt) VALUES (?, ?, ?)",
                (migration.version, migration.name, datetime.now(UTC).isoformat()),
            )
            connection.commit()
            applied += 1
        except sqlite3.DatabaseError:
            connection.rollback()
            raise
    return applied
