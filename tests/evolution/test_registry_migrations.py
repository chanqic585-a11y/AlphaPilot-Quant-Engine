from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from alphapilot.evolution.registry.database import connect_registry
from alphapilot.evolution.registry.migrations import (
    MIGRATIONS,
    Migration,
    apply_migrations,
)


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
    "LiveReleases",
    "DriftEvents",
    "AuditEvents",
    "LegacyEvidence",
    "StrategyVersions",
    "GateProfiles",
    "WorkflowRuns",
    "StageEvents",
    "FailureDiagnoses",
    "StrategyDataContracts",
    "EvaluationBindings",
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
                foreign_key_violations = connection.execute(
                    "PRAGMA foreign_key_check"
                ).fetchall()
            finally:
                connection.close()

        self.assertGreater(first, 0)
        self.assertEqual(second, 0)
        self.assertTrue(EXPECTED_TABLES.issubset(tables))
        self.assertEqual(migration_count, first)
        self.assertEqual(foreign_key_violations, [])

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

    def test_v5_registry_upgrades_to_workflow_v6_without_rebuilding_old_tables(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "registry.sqlite"
            connection = connect_registry(path, initialize=False)
            try:
                initial_count = apply_migrations(
                    connection, migrations=MIGRATIONS[:5]
                )
                old_strategy_family_sql = connection.execute(
                    """
                    SELECT sql FROM sqlite_master
                    WHERE type = 'table' AND name = 'StrategyFamilies'
                    """
                ).fetchone()[0]

                upgraded_count = apply_migrations(connection)
                repeated_count = apply_migrations(connection)
                preserved_strategy_family_sql = connection.execute(
                    """
                    SELECT sql FROM sqlite_master
                    WHERE type = 'table' AND name = 'StrategyFamilies'
                    """
                ).fetchone()[0]
                workflow_table_count = connection.execute(
                    """
                    SELECT COUNT(*) FROM sqlite_master
                    WHERE type = 'table' AND name IN (
                      'StrategyVersions', 'GateProfiles', 'WorkflowRuns',
                      'StageEvents', 'FailureDiagnoses'
                    )
                    """
                ).fetchone()[0]
                foreign_key_violations = connection.execute(
                    "PRAGMA foreign_key_check"
                ).fetchall()
            finally:
                connection.close()

        self.assertEqual(initial_count, 5)
        self.assertEqual(upgraded_count, 2)
        self.assertEqual(repeated_count, 0)
        self.assertEqual(workflow_table_count, 5)
        self.assertEqual(
            preserved_strategy_family_sql,
            old_strategy_family_sql,
        )
        self.assertEqual(foreign_key_violations, [])

    def test_v6_registry_upgrades_to_evaluation_bindings_v7_without_rebuilding_workflow_tables(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "registry.sqlite"
            connection = connect_registry(path, initialize=False)
            try:
                initial_count = apply_migrations(
                    connection, migrations=MIGRATIONS[:6]
                )
                old_workflow_sql = connection.execute(
                    """
                    SELECT sql FROM sqlite_master
                    WHERE type = 'table' AND name = 'WorkflowRuns'
                    """
                ).fetchone()[0]

                upgraded_count = apply_migrations(connection)
                repeated_count = apply_migrations(connection)
                preserved_workflow_sql = connection.execute(
                    """
                    SELECT sql FROM sqlite_master
                    WHERE type = 'table' AND name = 'WorkflowRuns'
                    """
                ).fetchone()[0]
                new_table_count = connection.execute(
                    """
                    SELECT COUNT(*) FROM sqlite_master
                    WHERE type = 'table' AND name IN (
                      'StrategyDataContracts', 'EvaluationBindings'
                    )
                    """
                ).fetchone()[0]
                foreign_key_violations = connection.execute(
                    "PRAGMA foreign_key_check"
                ).fetchall()
            finally:
                connection.close()

        self.assertEqual(initial_count, 6)
        self.assertEqual(upgraded_count, 1)
        self.assertEqual(repeated_count, 0)
        self.assertEqual(new_table_count, 2)
        self.assertEqual(preserved_workflow_sql, old_workflow_sql)
        self.assertEqual(foreign_key_violations, [])


if __name__ == "__main__":
    unittest.main()
