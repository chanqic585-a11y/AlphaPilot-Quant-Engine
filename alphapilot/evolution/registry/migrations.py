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
