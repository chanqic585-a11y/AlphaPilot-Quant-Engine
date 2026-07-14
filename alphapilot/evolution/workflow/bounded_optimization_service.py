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
from .service import (
    archive_strategy_version,
    create_challenger_version,
    queue_workflow_run,
)
from .types import StrategyVersionRecord, WorkflowRunRecord


@dataclass(frozen=True)
class OptimizationProcessingResult:
    decision: OptimizationDecision
    challengerStrategyVersionId: str | None
    challengerWorkflowRunId: str | None


@dataclass(frozen=True)
class OptimizationRecoveryResult:
    reviewedCount: int
    alreadyReviewedCount: int
    createdChallengerCount: int
    stoppedCount: int
    challengerWorkflowRunIds: list[str]
    decisions: list[dict[str, Any]]


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


def _is_exhausted_terminal(payload: dict[str, Any]) -> bool:
    return (
        payload.get("reasonCode") == "automatic_attempt_budget_exhausted"
        and payload.get("terminalStatus") == "budget_exhausted"
    )


def _archive_exhausted_campaign(
    repository: WorkflowRepository,
    root_strategy_version_id: str,
) -> list[str]:
    """Retire every active version after bounded optimization is exhausted."""

    archived_ids: list[str] = []
    versions = sorted(
        _campaign_versions(repository, root_strategy_version_id),
        key=lambda version: (
            int(_lineage(version).get("attemptNumber") or 0),
            version.createdAt,
            version.strategyVersionId,
        ),
        reverse=True,
    )
    for version in versions:
        if version.status != "active":
            continue
        archive_strategy_version(
            repository,
            version.strategyVersionId,
            actor="system",
        )
        archived_ids.append(version.strategyVersionId)
    return archived_ids


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
    if _is_exhausted_terminal(payload):
        _archive_exhausted_campaign(repository, root_strategy_version_id)
    return OptimizationProcessingResult(
        decision=decision,
        challengerStrategyVersionId=(
            challenger.strategyVersionId if challenger is not None else None
        ),
        challengerWorkflowRunId=(
            challenger_run.workflowRunId if challenger_run is not None else None
        ),
    )


def _latest_campaign_leaf(
    versions: list[StrategyVersionRecord],
) -> StrategyVersionRecord | None:
    parent_ids = {
        version.parentStrategyVersionId
        for version in versions
        if version.parentStrategyVersionId is not None
    }
    leaves = [
        version
        for version in versions
        if version.strategyVersionId not in parent_ids
    ]
    if not leaves:
        return None
    return max(
        leaves,
        key=lambda version: (
            int(_lineage(version).get("attemptNumber") or 0),
            version.createdAt,
            version.strategyVersionId,
        ),
    )


def _reviewed_audit_payloads_by_run(
    registry: RegistryRepository,
    root_strategy_version_id: str,
) -> dict[str, dict[str, Any]]:
    return {
        str(event.payload.get("workflowRunId")): event.payload
        for event in registry.list_audit_events(
            event_type="bounded_auto_optimization",
            entity_type="StrategyVersion",
            entity_id=root_strategy_version_id,
        )
        if event.payload.get("workflowRunId")
        and not (
            event.payload.get("reasonCode") == "parameter_allowlist_missing"
            and event.payload.get("terminalStatus") == "data_evidence_blocked"
        )
    }


def recover_terminal_optimization_results(
    repository: WorkflowRepository,
    registry: RegistryRepository,
    *,
    strategy_version_ids: list[str] | None = None,
) -> OptimizationRecoveryResult:
    """Review terminal backtests that predate the bounded optimizer hook.

    The recovery is idempotent by workflow run ID. It only reviews the latest
    leaf in each immutable optimization campaign, so historical ancestors are
    never optimized again after a challenger exists.
    """

    all_versions = repository.list_strategy_versions()
    versions_by_id = {
        version.strategyVersionId: version for version in all_versions
    }
    if strategy_version_ids is None:
        requested_roots = [_root_id(version) for version in all_versions]
    else:
        requested_roots = []
        for strategy_version_id in strategy_version_ids:
            version = versions_by_id.get(strategy_version_id)
            if version is None:
                raise ValueError(
                    f"strategy_version_missing:{strategy_version_id}"
                )
            requested_roots.append(_root_id(version))

    roots = list(dict.fromkeys(requested_roots))
    reviewed_count = 0
    already_reviewed_count = 0
    created_challenger_count = 0
    stopped_count = 0
    challenger_workflow_run_ids: list[str] = []
    decisions: list[dict[str, Any]] = []

    for root_strategy_version_id in roots:
        campaign = [
            version
            for version in all_versions
            if _root_id(version) == root_strategy_version_id
        ]
        leaf = _latest_campaign_leaf(campaign)
        if leaf is None:
            continue
        run = repository.get_latest_workflow_run(
            leaf.strategyVersionId,
            stage="backtest",
        )
        if run is None or run.status not in {"passed", "failed", "blocked"}:
            continue
        reviewed_payloads = _reviewed_audit_payloads_by_run(
            registry,
            root_strategy_version_id,
        )
        if run.workflowRunId in reviewed_payloads:
            if _is_exhausted_terminal(reviewed_payloads[run.workflowRunId]):
                _archive_exhausted_campaign(
                    repository,
                    root_strategy_version_id,
                )
            already_reviewed_count += 1
            continue

        processed = process_bounded_optimization_result(
            repository,
            registry,
            run,
        )
        reviewed_count += 1
        if processed.challengerWorkflowRunId is not None:
            created_challenger_count += 1
            challenger_workflow_run_ids.append(
                processed.challengerWorkflowRunId
            )
        if processed.decision.action == "stop":
            stopped_count += 1
        decisions.append(
            {
                "rootStrategyVersionId": root_strategy_version_id,
                "strategyVersionId": leaf.strategyVersionId,
                "workflowRunId": run.workflowRunId,
                "action": processed.decision.action,
                "reasonCode": processed.decision.reasonCode,
                "terminalStatus": processed.decision.terminalStatus,
                "challengerStrategyVersionId": (
                    processed.challengerStrategyVersionId
                ),
                "challengerWorkflowRunId": (
                    processed.challengerWorkflowRunId
                ),
            }
        )

    return OptimizationRecoveryResult(
        reviewedCount=reviewed_count,
        alreadyReviewedCount=already_reviewed_count,
        createdChallengerCount=created_challenger_count,
        stoppedCount=stopped_count,
        challengerWorkflowRunIds=challenger_workflow_run_ids,
        decisions=decisions,
    )
