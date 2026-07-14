"""One-time, auditable migration from downloader progress to local formal data."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from alphapilot.evolution.registry.repositories import RegistryRepository

from .repository import WorkflowRepository
from .service import checkpoint_workflow_run, pause_workflow_run, queue_workflow_run


_PRESERVED_PHASES = ("checking_local_data", "research_smoke_running")
_PRESERVED_ARTIFACTS = ("strategyDataContractId", "researchSmokePath")
_OBSOLETE_ARTIFACTS = {
    "officialCollectionPath",
    "downloadedPartitions",
    "requiredPartitions",
    "downloadedFundingFiles",
    "dataSnapshotId",
    "validationPackPath",
    "evaluationBindingId",
    "formalAdapterResultPath",
}


@dataclass(frozen=True)
class LocalFormalMigrationResult:
    migratedCount: int
    skippedCount: int
    backupPath: str | None
    workflowRunIds: tuple[str, ...]


def _backup_registry(connection: sqlite3.Connection, registry_path: Path) -> str:
    backup_root = registry_path.parent / "backups"
    backup_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    backup_path = backup_root / (
        f"{registry_path.stem}.before-local-formal-migration-{stamp}.sqlite"
    )
    destination = sqlite3.connect(backup_path)
    try:
        connection.backup(destination)
    finally:
        destination.close()
    return str(backup_path)


def _requires_reset(progress: dict[str, object]) -> bool:
    artifacts = progress.get("artifacts") or {}
    if isinstance(artifacts, dict) and _OBSOLETE_ARTIFACTS.intersection(artifacts):
        return True
    phase = str(progress.get("phase") or "")
    completed = {str(item) for item in progress.get("completedPhases") or []}
    return phase in {"preparing_official_data", "validating_official_data"} or bool(
        completed - set(_PRESERVED_PHASES)
    )


def _reset_progress(progress: dict[str, object]) -> dict[str, object]:
    completed = [
        phase
        for phase in _PRESERVED_PHASES
        if phase in {str(item) for item in progress.get("completedPhases") or []}
    ]
    artifacts = progress.get("artifacts") or {}
    preserved_artifacts = (
        {
            key: artifacts[key]
            for key in _PRESERVED_ARTIFACTS
            if isinstance(artifacts, dict) and key in artifacts
        }
        if isinstance(artifacts, dict)
        else {}
    )
    return {
        "phase": completed[-1] if completed else None,
        "phaseHistory": completed,
        "completedPhases": completed,
        "artifacts": preserved_artifacts,
    }


def migrate_active_backtests_to_local_formal(
    repository: WorkflowRepository,
    registry: RegistryRepository,
    *,
    registry_path: Path | str,
    strategy_version_ids: list[str] | None = None,
    resume: bool = True,
) -> LocalFormalMigrationResult:
    """Reset only active non-terminal runs that still reference downloader state."""

    allowed_ids = set(strategy_version_ids or [])
    candidates = []
    skipped_count = 0
    for version in repository.list_strategy_versions():
        if version.status != "active":
            continue
        if allowed_ids and version.strategyVersionId not in allowed_ids:
            continue
        run = repository.get_latest_workflow_run(
            version.strategyVersionId,
            stage="backtest",
        )
        if run is None or run.status not in {"queued", "running", "paused"}:
            skipped_count += 1
            continue
        if not _requires_reset(run.progress):
            skipped_count += 1
            continue
        candidates.append(run)

    if not candidates:
        return LocalFormalMigrationResult(0, skipped_count, None, ())
    backup_path = _backup_registry(repository.connection, Path(registry_path))
    migrated_ids: list[str] = []
    for run in candidates:
        current = run
        if current.status in {"queued", "running"}:
            current = pause_workflow_run(
                repository,
                current.workflowRunId,
                actor="system",
            )
        current = checkpoint_workflow_run(
            repository,
            current.workflowRunId,
            progress=_reset_progress(current.progress),
            actor="worker",
        )
        if resume:
            current = queue_workflow_run(
                repository,
                current.workflowRunId,
                actor="system",
            )
        registry.append_audit_event(
            eventType="local_formal_backtest_migration",
            entityType="StrategyVersion",
            entityId=current.strategyVersionId,
            payload={
                "workflowRunId": current.workflowRunId,
                "source": "user_approved_local_market_data",
                "resumed": resume,
                "backupPath": backup_path,
            },
        )
        migrated_ids.append(current.workflowRunId)
    return LocalFormalMigrationResult(
        migratedCount=len(migrated_ids),
        skippedCount=skipped_count,
        backupPath=backup_path,
        workflowRunIds=tuple(migrated_ids),
    )
