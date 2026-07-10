from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from alphapilot.evolution.registry.database import connect_registry
from alphapilot.evolution.registry.migrations import Migration, apply_migrations


EXPECTED_TABLES = {
    "RegistryMigrations",
    "DataSnapshots",
    "FactorDefinitions",
    "FactorRuns",
    "Experiments",
    "Models",
    "OutcomeLedger",
    "RiskProfiles",
    "RiskProfileActivations",
    "ForwardReleases",
    "ForwardSessions",
    "ForwardEvents",
    "StrategyFamilies",
    "StrategyCandidates",
    "PromotionDecisions",
    "DemoReleases",
    "LiveCandidatePackages",
    "DriftEvents",
    "AuditEvents",
    "LegacyEvidence",
}


class RegistryMigrationTests(unittest.TestCase):
    def test_default_migrations_are_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "registry.sqlite"
            connection = connect_registry(path, initialize=False)
            try:
                first = apply_migrations(connection)
                second = apply_migrations(connection)
                tables = {
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    ).fetchall()
                }
                migration_count = connection.execute(
                    "SELECT COUNT(*) FROM RegistryMigrations"
                ).fetchone()[0]
            finally:
                connection.close()

        self.assertGreater(first, 0)
        self.assertEqual(second, 0)
        self.assertTrue(EXPECTED_TABLES.issubset(tables))
        self.assertEqual(migration_count, first)

    def test_failed_migration_rolls_back_all_statements(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "registry.sqlite"
            connection = connect_registry(path, initialize=True)
            broken = Migration(
                version=999,
                name="broken_test_migration",
                statements=(
                    "CREATE TABLE ShouldRollback (id INTEGER PRIMARY KEY)",
                    "THIS IS NOT SQL",
                ),
            )
            try:
                with self.assertRaises(sqlite3.DatabaseError):
                    apply_migrations(connection, migrations=(broken,))
                table_count = connection.execute(
                    "SELECT COUNT(*) FROM sqlite_master WHERE type = 'table' AND name = 'ShouldRollback'"
                ).fetchone()[0]
                migration_count = connection.execute(
                    "SELECT COUNT(*) FROM RegistryMigrations WHERE version = 999"
                ).fetchone()[0]
            finally:
                connection.close()

        self.assertEqual(table_count, 0)
        self.assertEqual(migration_count, 0)


if __name__ == "__main__":
    unittest.main()
