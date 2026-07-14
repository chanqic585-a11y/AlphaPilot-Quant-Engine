import tempfile
import unittest
from pathlib import Path

from alphapilot.evolution.registry.database import connect_registry
from alphapilot.evolution.registry.repositories import RegistryRepository
from alphapilot.evolution.workflow.bootstrap import register_alpha191_observer
from alphapilot.evolution.workflow.local_formal_migration import (
    migrate_active_backtests_to_local_formal,
)
from alphapilot.evolution.workflow.repository import WorkflowRepository
from alphapilot.evolution.workflow.service import (
    checkpoint_workflow_run,
    queue_workflow_run,
    start_workflow_run,
)


class LocalFormalMigrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.registry_path = self.root / "registry.sqlite"
        self.connection = connect_registry(self.registry_path)
        self.registry = RegistryRepository(self.connection)
        self.workflow = WorkflowRepository(self.connection)

    def tearDown(self) -> None:
        self.connection.close()
        self.temp.cleanup()

    def test_resets_active_official_progress_and_is_idempotent(self) -> None:
        version = register_alpha191_observer(self.registry, self.workflow)
        initial = self.workflow.get_latest_workflow_run(version.strategyVersionId)
        assert initial is not None
        queued = queue_workflow_run(self.workflow, initial.workflowRunId, actor="user")
        running = start_workflow_run(self.workflow, queued.workflowRunId, actor="worker")
        checkpoint_workflow_run(
            self.workflow,
            running.workflowRunId,
            actor="worker",
            progress={
                "phase": "preparing_official_data",
                "phaseHistory": [
                    "checking_local_data",
                    "research_smoke_running",
                    "preparing_official_data",
                ],
                "completedPhases": [
                    "checking_local_data",
                    "research_smoke_running",
                ],
                "artifacts": {
                    "strategyDataContractId": "contract",
                    "researchSmokePath": "smoke.json",
                    "officialCollectionPath": "official.json",
                    "downloadedPartitions": 17,
                },
            },
        )

        first = migrate_active_backtests_to_local_formal(
            self.workflow,
            self.registry,
            registry_path=self.registry_path,
            resume=True,
        )
        second = migrate_active_backtests_to_local_formal(
            self.workflow,
            self.registry,
            registry_path=self.registry_path,
            resume=True,
        )

        migrated = self.workflow.get_workflow_run(running.workflowRunId)
        assert migrated is not None
        self.assertEqual(first.migratedCount, 1)
        self.assertTrue(first.backupPath)
        self.assertEqual(migrated.status, "queued")
        self.assertEqual(
            migrated.progress["completedPhases"],
            ["checking_local_data", "research_smoke_running"],
        )
        self.assertEqual(
            migrated.progress["artifacts"],
            {
                "strategyDataContractId": "contract",
                "researchSmokePath": "smoke.json",
            },
        )
        self.assertEqual(second.migratedCount, 0)
        self.assertIsNone(second.backupPath)


if __name__ == "__main__":
    unittest.main()
