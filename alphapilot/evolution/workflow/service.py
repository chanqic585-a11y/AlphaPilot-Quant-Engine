"""Idempotent commands for the strategy workflow orchestrator."""

from __future__ import annotations

import uuid
from dataclasses import replace
from typing import Any

from alphapilot.evolution.registry.hashing import stable_hash
from alphapilot.evolution.registry.types import utc_now

from .repository import WorkflowRepository
from .states import (
    FAILURE_CATEGORIES,
    RETRY_DISPOSITIONS,
    STAGE_ORDER,
    TERMINAL_STATUSES,
    WORKER_RESULT_ACTORS,
    WorkflowConflict,
    WorkflowTransitionError,
    validate_actor,
    validate_transition,
)
from .types import (
    FailureDiagnosisRecord,
    StageEventRecord,
    StrategyVersionRecord,
    WorkflowRunRecord,
)


NEXT_STAGE = {
    "backtest": "local_forward",
    "local_forward": "demo",
    "demo": "live",
}


def _strategy_content(
    *,
    strategy_family_id: str,
    definition: dict[str, Any],
    parameters: dict[str, Any],
    model_artifact_id: str | None,
) -> dict[str, Any]:
    return {
        "strategyFamilyId": strategy_family_id,
        "definition": definition,
        "parameters": parameters,
        "modelArtifactId": model_artifact_id,
    }


def _make_stage_event(
    run: WorkflowRunRecord,
    *,
    previous_stage: str | None,
    previous_status: str | None,
    next_stage: str,
    next_status: str,
    reason_code: str,
    actor: str,
    evidence: dict[str, Any] | None = None,
) -> StageEventRecord:
    created_at = utc_now()
    payload = {
        "workflowRunId": run.workflowRunId,
        "strategyVersionId": run.strategyVersionId,
        "previousStage": previous_stage,
        "nextStage": next_stage,
        "previousStatus": previous_status,
        "nextStatus": next_status,
        "reasonCode": reason_code,
        "actor": actor,
        "evidence": evidence or {},
        "createdAt": created_at,
        "nonce": uuid.uuid4().hex,
    }
    return StageEventRecord(
        stageEventId=stable_hash(payload, prefix="stage_event"),
        workflowRunId=run.workflowRunId,
        strategyVersionId=run.strategyVersionId,
        previousStage=previous_stage,
        nextStage=next_stage,
        previousStatus=previous_status,
        nextStatus=next_status,
        reasonCode=reason_code,
        actor=actor,
        evidence=evidence or {},
        contentHash=stable_hash(payload),
        createdAt=created_at,
    )


def _current_run(
    repository: WorkflowRepository, strategy_version_id: str
) -> WorkflowRunRecord | None:
    runs = repository.list_workflow_runs(strategy_version_id=strategy_version_id)
    if not runs:
        return None
    return max(
        runs,
        key=lambda run: (
            STAGE_ORDER[run.stage],
            run.attemptNumber,
            run.createdAt,
            run.workflowRunId,
        ),
    )


def _record_initial_event(
    repository: WorkflowRepository,
    run: WorkflowRunRecord,
    *,
    previous_stage: str | None,
    previous_status: str | None,
    reason_code: str,
    actor: str,
) -> None:
    if repository.list_stage_events(workflow_run_id=run.workflowRunId):
        return
    repository.create_stage_event(
        _make_stage_event(
            run,
            previous_stage=previous_stage,
            previous_status=previous_status,
            next_stage=run.stage,
            next_status=run.status,
            reason_code=reason_code,
            actor=actor,
        )
    )


def register_strategy_version(
    repository: WorkflowRepository,
    *,
    strategy_family_id: str,
    display_name: str,
    source_type: str,
    definition: dict[str, Any],
    parameters: dict[str, Any],
    parent_strategy_version_id: str | None = None,
    strategy_candidate_id: str | None = None,
    model_artifact_id: str | None = None,
    initial_gate_profile_id: str | None = None,
) -> StrategyVersionRecord:
    if not repository.strategy_family_exists(strategy_family_id):
        raise WorkflowConflict(f"strategy_family_missing:{strategy_family_id}")
    if (
        initial_gate_profile_id is not None
        and repository.get_gate_profile(initial_gate_profile_id) is None
    ):
        raise WorkflowConflict(
            f"initial_gate_profile_missing:{initial_gate_profile_id}"
        )
    content = _strategy_content(
        strategy_family_id=strategy_family_id,
        definition=definition,
        parameters=parameters,
        model_artifact_id=model_artifact_id,
    )
    content_hash = stable_hash(content)
    strategy_version_id = stable_hash(content, prefix="strategy_version")
    record = StrategyVersionRecord(
        strategyVersionId=strategy_version_id,
        strategyFamilyId=strategy_family_id,
        parentStrategyVersionId=parent_strategy_version_id,
        strategyCandidateId=strategy_candidate_id,
        displayName=display_name,
        sourceType=source_type,
        status="active",
        definition=definition,
        parameters=parameters,
        modelArtifactId=model_artifact_id,
        contentHash=content_hash,
    )
    stored = repository.create_strategy_version(record)
    initial = repository.create_workflow_run(
        strategy_version_id=stored.strategyVersionId,
        stage="backtest",
        status="awaiting",
        attempt_number=1,
        gate_profile_id=initial_gate_profile_id,
        risk_profile_id=None,
        idempotency_key=f"initial::{stored.strategyVersionId}::backtest",
        progress={},
        result={},
    )
    _record_initial_event(
        repository,
        initial,
        previous_stage=None,
        previous_status=None,
        reason_code="strategy_version_registered",
        actor="system",
    )
    return stored


def create_challenger_version(
    repository: WorkflowRepository,
    *,
    parent_strategy_version_id: str,
    display_name: str,
    source_type: str,
    definition: dict[str, Any],
    parameters: dict[str, Any],
    model_artifact_id: str | None = None,
) -> StrategyVersionRecord:
    parent = repository.get_strategy_version(parent_strategy_version_id)
    if parent is None:
        raise WorkflowConflict(
            f"parent_strategy_version_missing:{parent_strategy_version_id}"
        )
    challenger_content = _strategy_content(
        strategy_family_id=parent.strategyFamilyId,
        definition=definition,
        parameters=parameters,
        model_artifact_id=model_artifact_id,
    )
    if stable_hash(challenger_content) == parent.contentHash:
        raise WorkflowConflict("challenger_content_unchanged")
    return register_strategy_version(
        repository,
        strategy_family_id=parent.strategyFamilyId,
        display_name=display_name,
        source_type=source_type,
        definition=definition,
        parameters=parameters,
        parent_strategy_version_id=parent.strategyVersionId,
        model_artifact_id=model_artifact_id,
    )


def _transition_run(
    repository: WorkflowRepository,
    run: WorkflowRunRecord,
    *,
    next_status: str,
    actor: str,
    reason_code: str,
    progress: dict[str, Any] | None = None,
    result: dict[str, Any] | None = None,
    evidence: dict[str, Any] | None = None,
    diagnosis: FailureDiagnosisRecord | None = None,
) -> WorkflowRunRecord:
    validate_transition(run.status, next_status, actor)
    now = utc_now()
    updated = replace(
        run,
        status=next_status,
        progress=run.progress if progress is None else progress,
        result=run.result if result is None else result,
        startedAt=run.startedAt or (now if next_status == "running" else None),
        checkpointAt=run.checkpointAt,
        completedAt=now if next_status in TERMINAL_STATUSES else None,
        updatedAt=now,
    )
    event = _make_stage_event(
        run,
        previous_stage=run.stage,
        previous_status=run.status,
        next_stage=run.stage,
        next_status=next_status,
        reason_code=reason_code,
        actor=actor,
        evidence=evidence,
    )
    return repository.apply_workflow_update(
        updated=updated,
        expected_status=run.status,
        event=event,
        diagnosis=diagnosis,
    )


def queue_workflow_run(
    repository: WorkflowRepository, workflow_run_id: str, *, actor: str
) -> WorkflowRunRecord:
    run = repository.get_workflow_run(workflow_run_id)
    if run is None:
        raise WorkflowConflict(f"workflow_run_missing:{workflow_run_id}")
    if run.status == "queued":
        return run
    if run.status not in {"awaiting", "paused"}:
        raise WorkflowTransitionError(f"workflow_run_not_queueable:{run.status}")
    return _transition_run(
        repository,
        run,
        next_status="queued",
        actor=actor,
        reason_code="workflow_run_queued",
    )


def start_workflow_run(
    repository: WorkflowRepository, workflow_run_id: str, *, actor: str
) -> WorkflowRunRecord:
    validate_actor(actor)
    if actor not in WORKER_RESULT_ACTORS:
        raise WorkflowTransitionError("workflow_start_requires_worker_actor")
    run = repository.get_workflow_run(workflow_run_id)
    if run is None:
        raise WorkflowConflict(f"workflow_run_missing:{workflow_run_id}")
    return _transition_run(
        repository,
        run,
        next_status="running",
        actor=actor,
        reason_code="workflow_run_started",
    )


def pause_workflow_run(
    repository: WorkflowRepository, workflow_run_id: str, *, actor: str
) -> WorkflowRunRecord:
    run = repository.get_workflow_run(workflow_run_id)
    if run is None:
        raise WorkflowConflict(f"workflow_run_missing:{workflow_run_id}")
    if run.status == "paused":
        return run
    if run.status != "running":
        raise WorkflowTransitionError(f"workflow_run_not_pauseable:{run.status}")
    return _transition_run(
        repository,
        run,
        next_status="paused",
        actor=actor,
        reason_code="workflow_run_paused",
    )


def cancel_workflow_run(
    repository: WorkflowRepository, workflow_run_id: str, *, actor: str
) -> WorkflowRunRecord:
    run = repository.get_workflow_run(workflow_run_id)
    if run is None:
        raise WorkflowConflict(f"workflow_run_missing:{workflow_run_id}")
    if run.status == "cancelled":
        return run
    if run.status not in {"awaiting", "queued", "running", "paused", "blocked"}:
        raise WorkflowTransitionError(f"workflow_run_not_cancellable:{run.status}")
    return _transition_run(
        repository,
        run,
        next_status="cancelled",
        actor=actor,
        reason_code="workflow_run_cancelled",
    )


def archive_strategy_version(
    repository: WorkflowRepository, strategy_version_id: str, *, actor: str
) -> StrategyVersionRecord:
    validate_actor(actor)
    version = repository.get_strategy_version(strategy_version_id)
    if version is None:
        raise WorkflowConflict(f"strategy_version_missing:{strategy_version_id}")
    if version.status == "archived":
        return version
    if version.status != "active":
        raise WorkflowTransitionError(
            f"strategy_version_not_archivable:{version.status}"
        )
    current = _current_run(repository, strategy_version_id)
    if current is None:
        raise WorkflowConflict(f"strategy_workflow_missing:{strategy_version_id}")
    if current.status in {"awaiting", "queued", "running", "paused", "blocked"}:
        current = cancel_workflow_run(
            repository, current.workflowRunId, actor=actor
        )
    event = _make_stage_event(
        current,
        previous_stage=current.stage,
        previous_status=current.status,
        next_stage=current.stage,
        next_status=current.status,
        reason_code="strategy_version_archived",
        actor=actor,
        evidence={"strategyContentHash": version.contentHash},
    )
    return repository.update_strategy_version_status(
        strategy_version_id=strategy_version_id,
        expected_status=version.status,
        next_status="archived",
        event=event,
    )


def checkpoint_workflow_run(
    repository: WorkflowRepository,
    workflow_run_id: str,
    *,
    progress: dict[str, Any],
    actor: str,
    result: dict[str, Any] | None = None,
) -> WorkflowRunRecord:
    validate_actor(actor)
    if actor not in WORKER_RESULT_ACTORS:
        raise WorkflowTransitionError("checkpoint_requires_worker_actor")
    run = repository.get_workflow_run(workflow_run_id)
    if run is None:
        raise WorkflowConflict(f"workflow_run_missing:{workflow_run_id}")
    if run.status not in {"running", "paused"}:
        raise WorkflowTransitionError(f"workflow_run_not_checkpointable:{run.status}")
    now = utc_now()
    updated = replace(
        run,
        progress=progress,
        result=run.result if result is None else result,
        checkpointAt=now,
        updatedAt=now,
    )
    event = _make_stage_event(
        run,
        previous_stage=run.stage,
        previous_status=run.status,
        next_stage=run.stage,
        next_status=run.status,
        reason_code="checkpoint_saved",
        actor=actor,
        evidence={"progressHash": stable_hash(progress)},
    )
    return repository.apply_workflow_update(
        updated=updated,
        expected_status=run.status,
        event=event,
    )


def complete_workflow_run(
    repository: WorkflowRepository,
    workflow_run_id: str,
    *,
    status: str,
    actor: str,
    result: dict[str, Any],
    evidence: dict[str, Any],
    failure: dict[str, Any] | None = None,
) -> WorkflowRunRecord:
    if status not in {"passed", "failed", "blocked"}:
        raise WorkflowTransitionError(f"unsupported_completion_status:{status}")
    if actor not in WORKER_RESULT_ACTORS:
        raise WorkflowTransitionError(f"workflow_result_requires_worker_actor:{status}")
    if status == "passed" and not evidence:
        raise WorkflowTransitionError("passed_workflow_requires_evidence")
    run = repository.get_workflow_run(workflow_run_id)
    if run is None:
        raise WorkflowConflict(f"workflow_run_missing:{workflow_run_id}")
    diagnosis: FailureDiagnosisRecord | None = None
    if status in {"failed", "blocked"}:
        failure_payload = failure if isinstance(failure, dict) else {}
        category = str(failure_payload.get("category") or "").strip()
        retry_disposition = str(
            failure_payload.get("retryDisposition") or ""
        ).strip()
        if category not in FAILURE_CATEGORIES:
            raise WorkflowTransitionError(f"unsupported_failure_category:{category}")
        if retry_disposition not in RETRY_DISPOSITIONS:
            raise WorkflowTransitionError(
                f"unsupported_retry_disposition:{retry_disposition}"
            )
        diagnosis_core = {
            "workflowRunId": run.workflowRunId,
            "category": category,
            "summary": str(failure_payload.get("summary") or "Workflow failed."),
            "retryDisposition": retry_disposition,
            "metrics": failure_payload.get("metrics") or {},
            "suggestions": list(failure_payload.get("suggestions") or []),
        }
        diagnosis = FailureDiagnosisRecord(
            failureDiagnosisId=stable_hash(
                {**diagnosis_core, "attemptNumber": run.attemptNumber},
                prefix="failure_diagnosis",
            ),
            workflowRunId=run.workflowRunId,
            category=category,
            summary=diagnosis_core["summary"],
            retryDisposition=retry_disposition,
            metrics=diagnosis_core["metrics"],
            suggestions=diagnosis_core["suggestions"],
            contentHash=stable_hash(diagnosis_core),
        )
    persisted_result = {**result, "evidence": evidence}
    return _transition_run(
        repository,
        run,
        next_status=status,
        actor=actor,
        reason_code=f"workflow_run_{status}",
        result=persisted_result,
        evidence=evidence,
        diagnosis=diagnosis,
    )


def retry_workflow_run(
    repository: WorkflowRepository, workflow_run_id: str, *, actor: str
) -> WorkflowRunRecord:
    validate_actor(actor)
    source = repository.get_workflow_run(workflow_run_id)
    if source is None:
        raise WorkflowConflict(f"workflow_run_missing:{workflow_run_id}")
    diagnosis = repository.get_latest_failure_diagnosis(source.workflowRunId)
    if diagnosis is None:
        raise WorkflowTransitionError("workflow_retry_requires_failure_diagnosis")
    if diagnosis.retryDisposition != "same_version_retry":
        raise WorkflowTransitionError(
            f"workflow_retry_requires_new_version:{diagnosis.retryDisposition}"
        )
    attempt_number = source.attemptNumber + 1
    retry_key = f"retry::{source.workflowRunId}::{attempt_number}"
    existing_retry = repository.get_workflow_run_by_idempotency_key(retry_key)
    if existing_retry is not None:
        return existing_retry
    if source.status not in {"failed", "blocked"}:
        raise WorkflowTransitionError(f"workflow_run_not_retryable:{source.status}")
    if source.status == "blocked":
        source = _transition_run(
            repository,
            source,
            next_status="cancelled",
            actor="system",
            reason_code="blocked_attempt_closed_for_retry",
        )
    retry = repository.create_workflow_run(
        strategy_version_id=source.strategyVersionId,
        stage=source.stage,
        status="queued",
        attempt_number=attempt_number,
        gate_profile_id=source.gateProfileId,
        risk_profile_id=source.riskProfileId,
        idempotency_key=retry_key,
        progress=source.progress,
        result={},
    )
    _record_initial_event(
        repository,
        retry,
        previous_stage=source.stage,
        previous_status=source.status,
        reason_code="same_version_operational_retry",
        actor=actor,
    )
    return retry


def retry_backtest_for_data_preparation(
    repository: WorkflowRepository,
    blocked_run_id: str,
    *,
    actor: str,
) -> WorkflowRunRecord:
    """Retry a blocked data-preparation attempt without changing strategy logic."""

    validate_actor(actor)
    source = repository.get_workflow_run(blocked_run_id)
    if source is None:
        raise WorkflowConflict(f"workflow_run_missing:{blocked_run_id}")
    retry_key = f"data-preparation-retry::{source.workflowRunId}::{source.attemptNumber + 1}"
    existing = repository.get_workflow_run_by_idempotency_key(retry_key)
    if existing is not None:
        return existing
    if source.stage != "backtest" or source.status != "blocked":
        raise WorkflowTransitionError(
            f"data_preparation_retry_not_allowed:{source.stage}:{source.status}"
        )
    diagnosis = repository.get_latest_failure_diagnosis(source.workflowRunId)
    if diagnosis is None or diagnosis.category not in {
        "data_integrity",
        "worker_operational",
        "exchange_operational",
    }:
        raise WorkflowTransitionError("data_preparation_retry_requires_data_blocker")
    source = _transition_run(
        repository,
        source,
        next_status="cancelled",
        actor="system",
        reason_code="blocked_data_attempt_closed_for_retry",
        evidence={"preservedStrategyVersionId": source.strategyVersionId},
    )
    completed = [
        phase
        for phase in source.progress.get("completedPhases", [])
        if phase in {"checking_local_data", "research_smoke_running"}
    ]
    artifacts = dict(source.progress.get("artifacts") or {})
    artifacts = {
        key: value
        for key, value in artifacts.items()
        if key in {"strategyDataContractId", "researchSmokePath"}
    }
    retry_progress = {
        "phase": completed[-1] if completed else None,
        "phaseHistory": completed,
        "completedPhases": completed,
        "artifacts": artifacts,
    }
    retry = repository.create_workflow_run(
        strategy_version_id=source.strategyVersionId,
        stage="backtest",
        status="queued",
        attempt_number=source.attemptNumber + 1,
        gate_profile_id=source.gateProfileId,
        risk_profile_id=source.riskProfileId,
        idempotency_key=retry_key,
        progress=retry_progress,
        result={},
    )
    _record_initial_event(
        repository,
        retry,
        previous_stage=source.stage,
        previous_status=source.status,
        reason_code="data_preparation_retry_created",
        actor=actor,
    )
    return retry


def create_next_stage_run(
    repository: WorkflowRepository, strategy_version_id: str, *, actor: str
) -> WorkflowRunRecord:
    validate_actor(actor)
    current = _current_run(repository, strategy_version_id)
    if current is None:
        raise WorkflowConflict(f"strategy_workflow_missing:{strategy_version_id}")
    if current.idempotencyKey == f"advance::{strategy_version_id}::{current.stage}":
        return current
    if current.status != "passed":
        raise WorkflowTransitionError(
            f"current_workflow_stage_not_passed:{current.stage}:{current.status}"
        )
    next_stage = NEXT_STAGE.get(current.stage)
    if next_stage is None:
        raise WorkflowTransitionError(f"workflow_has_no_next_stage:{current.stage}")
    next_run = repository.create_workflow_run(
        strategy_version_id=strategy_version_id,
        stage=next_stage,
        status="awaiting",
        attempt_number=1,
        gate_profile_id=None,
        risk_profile_id=None,
        idempotency_key=f"advance::{strategy_version_id}::{next_stage}",
        progress={},
        result={},
    )
    _record_initial_event(
        repository,
        next_run,
        previous_stage=current.stage,
        previous_status=current.status,
        reason_code="workflow_stage_advanced",
        actor=actor,
    )
    return next_run
