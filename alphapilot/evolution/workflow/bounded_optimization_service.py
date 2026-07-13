"""Persist and schedule bounded, split-safe optimization decisions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from alphapilot.evolution.registry.hashing import stable_hash
from alphapilot.evolution.registry.repositories import RegistryRepository

from .bounded_optimizer import (
    OptimizationDecision,
    OptimizationInput,
    decide_bounded_optimization,
)
from .repository import WorkflowRepository
from .service import create_challenger_version, queue_workflow_run
from .types import StrategyVersionRecord, WorkflowRunRecord


@dataclass(frozen=True)
class OptimizationProcessingResult:
    decision: OptimizationDecision
    challengerStrategyVersionId: str | None
    challengerWorkflowRunId: str | None


def _lineage(version: StrategyVersionRecord) -> dict[str, Any]:
    value = version.definition.get("optimizationLineage")
    return value if isinstance(value, dict) else {}


def _root_id(version: StrategyVersionRecord) -> str:
    return str(_lineage(version).get("rootStrategyVersionId") or version.strategyVersionId)


def _campaign_versions(
    repository: WorkflowRepository,
    root_strategy_version_id: str,
) -> list[StrategyVersionRecord]:
    return [
        version
        for version in repository.list_strategy_versions()
        if _root_id(version) == root_strategy_version_id
    ]


def _completed_attempts(versions: list[StrategyVersionRecord]) -> int:
    attempts = [
        int(_lineage(version).get("attemptNumber") or 0)
        for version in versions
        if str(_lineage(version).get("phase") or "") == "selection"
    ]
    return max(attempts, default=0)


def _direct_active_child(
    repository: WorkflowRepository,
    versions: list[StrategyVersionRecord],
    parent_strategy_version_id: str,
) -> tuple[StrategyVersionRecord, WorkflowRunRecord] | None:
    for version in versions:
        if version.parentStrategyVersionId != parent_strategy_version_id:
            continue
        run = repository.get_latest_workflow_run(
            version.strategyVersionId,
            stage="backtest",
        )
        if run is not None and run.status in {"awaiting", "queued", "running", "paused"}:
            return version, run
    return None


def _audit_payload(
    decision: OptimizationDecision,
    *,
    workflow_run_id: str,
    challenger_strategy_version_id: str | None,
) -> dict[str, Any]:
    selection_metrics_hash = stable_hash(decision.selectionMetrics)
    decision_key = stable_hash(
        {
            "workflowRunId": workflow_run_id,
            "campaignId": decision.campaignId,
            "action": decision.action,
            "reasonCode": decision.reasonCode,
            "attemptNumber": decision.attemptNumber,
            "terminalStatus": decision.terminalStatus,
            "selectionMetricsHash": selection_metrics_hash,
        },
        prefix="bounded_optimization_decision",
    )
    return {
        "schemaVersion": "bounded_optimization_audit_v1",
        "decisionKey": decision_key,
        "campaignId": decision.campaignId,
        "rootStrategyVersionId": decision.rootStrategyVersionId,
        "currentStrategyVersionId": decision.currentStrategyVersionId,
        "workflowRunId": workflow_run_id,
        "action": decision.action,
        "reasonCode": decision.reasonCode,
        "terminalStatus": decision.terminalStatus,
        "attemptNumber": decision.attemptNumber,
        "maxAttempts": decision.maxAttempts,
        "changedParameter": decision.changedParameter,
        "selectionMetricsHash": selection_metrics_hash,
        "challengerStrategyVersionId": challenger_strategy_version_id,
    }


def _append_audit_once(
    registry: RegistryRepository,
    *,
    root_strategy_version_id: str,
    payload: dict[str, Any],
) -> None:
    existing = registry.list_audit_events(
        event_type="bounded_auto_optimization",
        entity_type="StrategyVersion",
        entity_id=root_strategy_version_id,
    )
    if any(event.payload.get("decisionKey") == payload["decisionKey"] for event in existing):
        return
    registry.append_audit_event(
        eventType="bounded_auto_optimization",
        entityType="StrategyVersion",
        entityId=root_strategy_version_id,
        payload=payload,
    )


def process_bounded_optimization_result(
    repository: WorkflowRepository,
    registry: RegistryRepository,
    run: WorkflowRunRecord,
) -> OptimizationProcessingResult:
    """Create at most one immutable challenger after a terminal backtest result."""

    version = repository.get_strategy_version(run.strategyVersionId)
    if version is None:
        raise ValueError(f"strategy_version_missing:{run.strategyVersionId}")
    root_strategy_version_id = _root_id(version)
    versions = _campaign_versions(repository, root_strategy_version_id)
    existing_child = _direct_active_child(
        repository,
        versions,
        version.strategyVersionId,
    )
    diagnosis = repository.get_latest_failure_diagnosis(run.workflowRunId)
    gate = repository.get_gate_profile(run.gateProfileId) if run.gateProfileId else None
    metrics = run.result.get("metrics") if isinstance(run.result, dict) else None
    decision = decide_bounded_optimization(
        OptimizationInput(
            rootStrategyVersionId=root_strategy_version_id,
            currentStrategyVersionId=version.strategyVersionId,
            displayName=version.displayName,
            definition=version.definition,
            parameters=version.parameters,
            metrics=metrics if isinstance(metrics, dict) else {},
            gateRules=gate.rules if gate is not None else {},
            failureCategory=diagnosis.category if diagnosis is not None else None,
            runStatus=run.status,
            completedAttempts=_completed_attempts(versions),
            activeChallengerExists=existing_child is not None,
        )
    )
    if existing_child is not None:
        child, child_run = existing_child
        return OptimizationProcessingResult(
            decision=decision,
            challengerStrategyVersionId=child.strategyVersionId,
            challengerWorkflowRunId=child_run.workflowRunId,
        )

    challenger: StrategyVersionRecord | None = None
    challenger_run: WorkflowRunRecord | None = None
    if decision.action in {"create_challenger", "create_formal_validation"}:
        if decision.proposedDefinition is None or decision.proposedParameters is None:
            raise ValueError("bounded_optimization_proposal_missing")
        suffix = (
            f"自动优化 {decision.attemptNumber}/{decision.maxAttempts}"
            if decision.action == "create_challenger"
            else "正式锁定验证"
        )
        challenger = create_challenger_version(
            repository,
            parent_strategy_version_id=version.strategyVersionId,
            display_name=f"{version.displayName} · {suffix}",
            source_type="bounded_auto_optimization_v1",
            definition=decision.proposedDefinition,
            parameters=decision.proposedParameters,
            model_artifact_id=version.modelArtifactId,
        )
        initial = repository.get_latest_workflow_run(
            challenger.strategyVersionId,
            stage="backtest",
        )
        if initial is None:
            raise ValueError("bounded_optimization_backtest_run_missing")
        challenger_run = queue_workflow_run(repository, initial.workflowRunId, actor="system")

    payload = _audit_payload(
        decision,
        workflow_run_id=run.workflowRunId,
        challenger_strategy_version_id=(
            challenger.strategyVersionId if challenger is not None else None
        ),
    )
    _append_audit_once(
        registry,
        root_strategy_version_id=root_strategy_version_id,
        payload=payload,
    )
    return OptimizationProcessingResult(
        decision=decision,
        challengerStrategyVersionId=(
            challenger.strategyVersionId if challenger is not None else None
        ),
        challengerWorkflowRunId=(
            challenger_run.workflowRunId if challenger_run is not None else None
        ),
    )
