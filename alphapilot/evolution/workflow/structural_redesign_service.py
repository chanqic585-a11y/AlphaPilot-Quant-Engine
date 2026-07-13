"""Atomically persist bounded structural redesign decisions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from typing import Any

from alphapilot.evolution.registry.hashing import stable_hash
from alphapilot.evolution.registry.repositories import RegistryRepository
from alphapilot.evolution.registry.types import AuditEventRecord, utc_now

from .repository import WorkflowRepository
from .structural_redesign import (
    StructuralRedesignDecision,
    StructuralRedesignInput,
    decide_structural_redesign,
)
from .types import StageEventRecord, StrategyVersionRecord, WorkflowRunRecord


_ACTIVE_RUN_STATUSES = {"awaiting", "queued", "running", "paused"}
_ARCHIVABLE_STOP_REASONS = {
    "structural_generation_budget_exhausted",
    "no_novel_structural_recipe",
}


@dataclass(frozen=True)
class StructuralRedesignProcessingResult:
    action: str
    reasonCode: str
    decisionKey: str
    generation: int
    recipeId: str | None
    parentStrategyVersionId: str
    childStrategyVersionId: str | None
    childWorkflowRunId: str | None


@dataclass(frozen=True)
class StructuralRedesignRecoveryResult:
    backupPath: str | None
    reviewedCount: int
    alreadyReviewedCount: int
    createdChildCount: int
    stoppedCount: int
    childWorkflowRunIds: list[str]
    decisions: list[dict[str, Any]]


def _structural_lineage(version: StrategyVersionRecord) -> dict[str, Any]:
    value = version.definition.get("structuralRedesignLineage")
    return value if isinstance(value, dict) else {}


def _optimization_lineage(version: StrategyVersionRecord) -> dict[str, Any]:
    value = version.definition.get("optimizationLineage")
    return value if isinstance(value, dict) else {}


def _root_id(version: StrategyVersionRecord) -> str:
    return str(
        _structural_lineage(version).get("rootStrategyVersionId")
        or _optimization_lineage(version).get("rootStrategyVersionId")
        or version.strategyVersionId
    )


def _campaign_versions(
    repository: WorkflowRepository,
    root_strategy_version_id: str,
) -> list[StrategyVersionRecord]:
    return [
        version
        for version in repository.list_strategy_versions()
        if _root_id(version) == root_strategy_version_id
    ]


def _direct_structural_child(
    repository: WorkflowRepository,
    versions: list[StrategyVersionRecord],
    parent_strategy_version_id: str,
) -> tuple[StrategyVersionRecord, WorkflowRunRecord] | None:
    for version in versions:
        lineage = _structural_lineage(version)
        if version.parentStrategyVersionId != parent_strategy_version_id or not lineage:
            continue
        run = repository.get_latest_workflow_run(
            version.strategyVersionId,
            stage="backtest",
        )
        if run is not None:
            return version, run
    return None


def _used_recipe_ids(versions: list[StrategyVersionRecord]) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                str(_structural_lineage(version).get("recipeId"))
                for version in versions
                if _structural_lineage(version).get("recipeId")
            }
        )
    )


def _result(
    decision: StructuralRedesignDecision,
    *,
    action: str | None = None,
    reason_code: str | None = None,
    child: StrategyVersionRecord | None = None,
    child_run: WorkflowRunRecord | None = None,
) -> StructuralRedesignProcessingResult:
    return StructuralRedesignProcessingResult(
        action=action or decision.action,
        reasonCode=reason_code or decision.reasonCode,
        decisionKey=decision.decisionKey,
        generation=decision.generation,
        recipeId=decision.recipeId,
        parentStrategyVersionId=decision.currentStrategyVersionId,
        childStrategyVersionId=(child.strategyVersionId if child is not None else None),
        childWorkflowRunId=(child_run.workflowRunId if child_run is not None else None),
    )


def _strategy_content(
    parent: StrategyVersionRecord,
    *,
    definition: dict[str, Any],
    parameters: dict[str, Any],
) -> dict[str, Any]:
    return {
        "strategyFamilyId": parent.strategyFamilyId,
        "definition": definition,
        "parameters": parameters,
        "modelArtifactId": parent.modelArtifactId,
    }


def _build_child_records(
    parent: StrategyVersionRecord,
    failed_run: WorkflowRunRecord,
    decision: StructuralRedesignDecision,
    *,
    created_at: str,
) -> tuple[StrategyVersionRecord, WorkflowRunRecord, StageEventRecord]:
    if decision.proposedDefinition is None or decision.proposedParameters is None:
        raise ValueError("structural_redesign_proposal_missing")
    content = _strategy_content(
        parent,
        definition=decision.proposedDefinition,
        parameters=decision.proposedParameters,
    )
    content_hash = stable_hash(content)
    strategy_version_id = stable_hash(content, prefix="strategy_version")
    child = StrategyVersionRecord(
        strategyVersionId=strategy_version_id,
        strategyFamilyId=parent.strategyFamilyId,
        parentStrategyVersionId=parent.strategyVersionId,
        strategyCandidateId=parent.strategyCandidateId,
        displayName=(
            f"{parent.displayName} / structural redesign G{decision.generation}"
        ),
        sourceType="bounded_structural_redesign_v1",
        status="active",
        definition=decision.proposedDefinition,
        parameters=decision.proposedParameters,
        modelArtifactId=parent.modelArtifactId,
        contentHash=content_hash,
        createdAt=created_at,
    )
    idempotency_key = f"initial::{child.strategyVersionId}::backtest"
    run_core = {
        "strategyVersionId": child.strategyVersionId,
        "stage": "backtest",
        "attemptNumber": 1,
        "gateProfileId": failed_run.gateProfileId,
        "riskProfileId": None,
        "idempotencyKey": idempotency_key,
    }
    run_hash = stable_hash(run_core)
    child_run = WorkflowRunRecord(
        workflowRunId=stable_hash(
            {"idempotencyKey": idempotency_key, "contentHash": run_hash},
            prefix="workflow_run",
        ),
        strategyVersionId=child.strategyVersionId,
        stage="backtest",
        status="queued",
        attemptNumber=1,
        gateProfileId=failed_run.gateProfileId,
        riskProfileId=None,
        idempotencyKey=idempotency_key,
        progress={},
        result={},
        startedAt=None,
        checkpointAt=None,
        completedAt=None,
        contentHash=run_hash,
        createdAt=created_at,
        updatedAt=created_at,
    )
    child_event = _stage_event(
        run=child_run,
        decision_key=decision.decisionKey,
        previous_stage=None,
        previous_status=None,
        next_status="queued",
        reason_code="structural_redesign_queued",
        evidence={
            "campaignId": decision.campaignId,
            "generation": decision.generation,
            "recipeId": decision.recipeId,
            "parentStrategyVersionId": parent.strategyVersionId,
        },
        created_at=created_at,
    )
    return child, child_run, child_event


def _stage_event(
    *,
    run: WorkflowRunRecord,
    decision_key: str,
    previous_stage: str | None,
    previous_status: str | None,
    next_status: str,
    reason_code: str,
    evidence: dict[str, Any],
    created_at: str,
) -> StageEventRecord:
    payload = {
        "workflowRunId": run.workflowRunId,
        "strategyVersionId": run.strategyVersionId,
        "previousStage": previous_stage,
        "nextStage": run.stage,
        "previousStatus": previous_status,
        "nextStatus": next_status,
        "reasonCode": reason_code,
        "actor": "system",
        "evidence": evidence,
        "decisionKey": decision_key,
    }
    return StageEventRecord(
        stageEventId=stable_hash(
            {"decisionKey": decision_key, "reasonCode": reason_code},
            prefix="stage_event",
        ),
        workflowRunId=run.workflowRunId,
        strategyVersionId=run.strategyVersionId,
        previousStage=previous_stage,
        nextStage=run.stage,
        previousStatus=previous_status,
        nextStatus=next_status,
        reasonCode=reason_code,
        actor="system",
        evidence=evidence,
        contentHash=stable_hash(payload),
        createdAt=created_at,
    )


def _profile_summary(decision: StructuralRedesignDecision) -> dict[str, Any]:
    profile = decision.failureProfile
    if profile is None:
        return {}
    return {
        "failureEvidenceHash": profile.evidenceHash,
        "failedGateNames": list(profile.failedGateNames),
        "overtrading": profile.overtrading,
        "weakExpectancy": profile.weakExpectancy,
        "drawdownConcentration": profile.drawdownConcentration,
        "sparseSample": profile.sparseSample,
        "transactionCostSensitive": profile.transactionCostSensitive,
    }


def _audit_event(
    *,
    event_type: str,
    parent: StrategyVersionRecord,
    failed_run: WorkflowRunRecord,
    decision: StructuralRedesignDecision,
    child: StrategyVersionRecord | None,
    created_at: str,
) -> AuditEventRecord:
    payload = {
        "schemaVersion": "structural_redesign_audit_v1",
        "eventType": event_type,
        "decisionKey": decision.decisionKey,
        "campaignId": decision.campaignId,
        "rootStrategyVersionId": decision.rootStrategyVersionId,
        "parentStrategyVersionId": parent.strategyVersionId,
        "childStrategyVersionId": (
            child.strategyVersionId if child is not None else None
        ),
        "workflowRunId": failed_run.workflowRunId,
        "action": decision.action,
        "reasonCode": decision.reasonCode,
        "generation": decision.generation,
        "maxGenerations": decision.maxGenerations,
        "recipeId": decision.recipeId,
        "recipeSummary": decision.recipeSummary,
        "grammarVersion": "structural_strategy_grammar_v1",
        "profile": _profile_summary(decision),
    }
    return AuditEventRecord(
        auditEventId=stable_hash(
            {"decisionKey": decision.decisionKey, "eventType": event_type},
            prefix="audit",
        ),
        eventType=event_type,
        entityType="StrategyVersion",
        entityId=parent.strategyVersionId,
        payload=payload,
        createdAt=created_at,
    )


def _decision_for_run(
    repository: WorkflowRepository,
    version: StrategyVersionRecord,
    stored_run: WorkflowRunRecord,
) -> tuple[
    StructuralRedesignDecision,
    tuple[StrategyVersionRecord, WorkflowRunRecord] | None,
]:
    root_strategy_version_id = _root_id(version)
    versions = _campaign_versions(repository, root_strategy_version_id)
    existing_child = _direct_structural_child(
        repository,
        versions,
        version.strategyVersionId,
    )
    diagnosis = repository.get_latest_failure_diagnosis(stored_run.workflowRunId)
    gate = (
        repository.get_gate_profile(stored_run.gateProfileId)
        if stored_run.gateProfileId
        else None
    )
    metrics = (
        stored_run.result.get("metrics")
        if isinstance(stored_run.result, dict)
        else None
    )
    return (
        decide_structural_redesign(
            StructuralRedesignInput(
                rootStrategyVersionId=root_strategy_version_id,
                currentStrategyVersionId=version.strategyVersionId,
                displayName=version.displayName,
                definition=version.definition,
                parameters=version.parameters,
                metrics=metrics if isinstance(metrics, dict) else {},
                gateRules=gate.rules if gate is not None else {},
                failureCategory=(
                    diagnosis.category if diagnosis is not None else None
                ),
                runStatus=stored_run.status,
                usedRecipeIds=_used_recipe_ids(versions),
                activeStructuralChildExists=(
                    existing_child is not None
                    and existing_child[1].status in _ACTIVE_RUN_STATUSES
                ),
            )
        ),
        existing_child,
    )


def process_structural_redesign_result(
    repository: WorkflowRepository,
    registry: RegistryRepository,
    run: WorkflowRunRecord,
) -> StructuralRedesignProcessingResult:
    """Create at most one structural child after a terminal weak backtest."""

    del registry  # The atomic repository transaction owns cross-table persistence.
    stored_run = repository.get_workflow_run(run.workflowRunId)
    if stored_run is None:
        raise ValueError(f"workflow_run_missing:{run.workflowRunId}")
    version = repository.get_strategy_version(stored_run.strategyVersionId)
    if version is None:
        raise ValueError(f"strategy_version_missing:{stored_run.strategyVersionId}")
    decision, existing_child = _decision_for_run(repository, version, stored_run)
    if existing_child is not None:
        child, child_run = existing_child
        return _result(
            decision,
            action="existing_child",
            reason_code="structural_child_already_registered",
            child=child,
            child_run=child_run,
        )

    if decision.action == "create_child":
        created_at = utc_now()
        child, child_run, child_event = _build_child_records(
            version,
            stored_run,
            decision,
            created_at=created_at,
        )
        parent_evidence = {
            "campaignId": decision.campaignId,
            "decisionKey": decision.decisionKey,
            "childStrategyVersionId": child.strategyVersionId,
            "reasonCode": decision.reasonCode,
        }
        parent_event = _stage_event(
            run=stored_run,
            decision_key=decision.decisionKey,
            previous_stage=stored_run.stage,
            previous_status=stored_run.status,
            next_status=stored_run.status,
            reason_code="structural_redesign_parent_archived",
            evidence=parent_evidence,
            created_at=created_at,
        )
        audits = (
            _audit_event(
                event_type="structural_redesign_candidate_created",
                parent=version,
                failed_run=stored_run,
                decision=decision,
                child=child,
                created_at=created_at,
            ),
            _audit_event(
                event_type="structural_redesign_parent_archived",
                parent=version,
                failed_run=stored_run,
                decision=decision,
                child=child,
                created_at=created_at,
            ),
        )
        repository.commit_structural_redesign(
            parent_strategy_version_id=version.strategyVersionId,
            expected_parent_status="active",
            child=child,
            child_run=child_run,
            child_event=child_event,
            parent_event=parent_event,
            audit_events=audits,
        )
        return _result(decision, child=child, child_run=child_run)

    if (
        decision.action == "stop"
        and decision.reasonCode in _ARCHIVABLE_STOP_REASONS
        and version.status == "active"
    ):
        created_at = utc_now()
        parent_event = _stage_event(
            run=stored_run,
            decision_key=decision.decisionKey,
            previous_stage=stored_run.stage,
            previous_status=stored_run.status,
            next_status=stored_run.status,
            reason_code="structural_redesign_stopped",
            evidence={
                "campaignId": decision.campaignId,
                "reasonCode": decision.reasonCode,
                "generation": decision.generation,
            },
            created_at=created_at,
        )
        repository.commit_structural_redesign_stop(
            parent_strategy_version_id=version.strategyVersionId,
            expected_parent_status="active",
            parent_event=parent_event,
            audit_event=_audit_event(
                event_type="structural_redesign_stopped",
                parent=version,
                failed_run=stored_run,
                decision=decision,
                child=None,
                created_at=created_at,
            ),
        )
    return _result(decision)


def _reviewed_workflow_run_ids(registry: RegistryRepository) -> set[str]:
    reviewed: set[str] = set()
    for event_type in (
        "structural_redesign_candidate_created",
        "structural_redesign_parent_archived",
        "structural_redesign_stopped",
    ):
        reviewed.update(
            str(event.payload.get("workflowRunId"))
            for event in registry.list_audit_events(event_type=event_type)
            if event.payload.get("workflowRunId")
        )
    return reviewed


def _backup_registry(
    connection: sqlite3.Connection,
    registry_path: Path,
) -> str:
    backup_root = registry_path.parent / "backups"
    backup_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    backup_path = backup_root / (
        f"{registry_path.stem}.before-structural-redesign-{stamp}.sqlite"
    )
    destination = sqlite3.connect(backup_path)
    try:
        connection.backup(destination)
    finally:
        destination.close()
    return str(backup_path)


def recover_terminal_structural_redesigns(
    repository: WorkflowRepository,
    registry: RegistryRepository,
    *,
    registry_path: Path | str,
    strategy_version_ids: list[str] | None = None,
) -> StructuralRedesignRecoveryResult:
    """Recover eligible old structural failures after an online SQLite backup."""

    all_versions = repository.list_strategy_versions()
    versions_by_id = {
        version.strategyVersionId: version for version in all_versions
    }
    if strategy_version_ids is None:
        requested = all_versions
    else:
        requested = []
        for strategy_version_id in dict.fromkeys(strategy_version_ids):
            version = versions_by_id.get(strategy_version_id)
            if version is None:
                raise ValueError(f"strategy_version_missing:{strategy_version_id}")
            requested.append(version)

    reviewed_ids = _reviewed_workflow_run_ids(registry)
    already_reviewed_count = 0
    eligible: list[
        tuple[StrategyVersionRecord, WorkflowRunRecord, StructuralRedesignDecision]
    ] = []
    for version in requested:
        run = repository.get_latest_workflow_run(
            version.strategyVersionId,
            stage="backtest",
        )
        if run is None or run.status != "failed":
            continue
        diagnosis = repository.get_latest_failure_diagnosis(run.workflowRunId)
        if diagnosis is None or diagnosis.category != "strategy_performance":
            continue
        if run.workflowRunId in reviewed_ids:
            already_reviewed_count += 1
            continue
        if version.status != "active":
            continue
        decision, existing_child = _decision_for_run(repository, version, run)
        if existing_child is not None:
            already_reviewed_count += 1
            continue
        if decision.action == "create_child" or (
            decision.action == "stop"
            and decision.reasonCode in _ARCHIVABLE_STOP_REASONS
        ):
            eligible.append((version, run, decision))

    backup_path = (
        _backup_registry(repository.connection, Path(registry_path))
        if eligible
        else None
    )
    reviewed_count = 0
    created_child_count = 0
    stopped_count = 0
    child_workflow_run_ids: list[str] = []
    decisions: list[dict[str, Any]] = []
    for version, run, _preview in eligible:
        processed = process_structural_redesign_result(repository, registry, run)
        reviewed_count += 1
        if processed.childWorkflowRunId is not None:
            created_child_count += 1
            child_workflow_run_ids.append(processed.childWorkflowRunId)
        if processed.action == "stop":
            stopped_count += 1
        decisions.append(
            {
                "strategyVersionId": version.strategyVersionId,
                "workflowRunId": run.workflowRunId,
                "action": processed.action,
                "reasonCode": processed.reasonCode,
                "decisionKey": processed.decisionKey,
                "generation": processed.generation,
                "recipeId": processed.recipeId,
                "childStrategyVersionId": processed.childStrategyVersionId,
                "childWorkflowRunId": processed.childWorkflowRunId,
            }
        )

    return StructuralRedesignRecoveryResult(
        backupPath=backup_path,
        reviewedCount=reviewed_count,
        alreadyReviewedCount=already_reviewed_count,
        createdChildCount=created_child_count,
        stoppedCount=stopped_count,
        childWorkflowRunIds=child_workflow_run_ids,
        decisions=decisions,
    )
