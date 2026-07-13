"""Build one current, page-specific workflow projection per strategy version."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from alphapilot.data_foundation.checkpoint import load_json
from alphapilot.data_foundation.warehouse import WarehouseLayout
from alphapilot.evolution.registry.types import utc_now
from alphapilot.evolution.registry.repositories import RegistryRepository

from .repository import WorkflowRepository
from .states import STAGE_LABELS, STAGE_ORDER, STAGE_PAGES, STATUS_LABELS
from .types import StrategyDataContractRecord, StrategyVersionRecord, WorkflowRunRecord


PHASE_LABELS = {
    "checking_local_data": "检查本地数据",
    "research_smoke_running": "本地研究烟测",
    "preparing_official_data": "准备官方数据",
    "validating_official_data": "校验正式数据",
    "freezing_data_snapshot": "冻结正式快照",
    "building_validation_manifests": "构建正式验证集",
    "formal_backtest_running": "正式回测中",
    "evaluating_gate": "评估回测门槛",
    "public_forward_observation": "本地前向运行中",
}


def _optimization_campaign_audit(
    repository: WorkflowRepository,
    root_strategy_version_id: str,
) -> tuple[dict[str, Any], str] | None:
    registry = RegistryRepository(repository.connection)
    events = registry.list_audit_events(
        event_type="bounded_auto_optimization",
        entity_type="StrategyVersion",
        entity_id=root_strategy_version_id,
    )
    if not events:
        return None
    latest = events[-1]
    return dict(latest.payload), latest.createdAt


def _structural_redesign_campaign(
    repository: WorkflowRepository,
    *,
    version: StrategyVersionRecord,
    current: WorkflowRunRecord,
) -> dict[str, Any]:
    lineage_value = version.definition.get("structuralRedesignLineage")
    lineage = lineage_value if isinstance(lineage_value, dict) else {}
    parent_strategy_version_id = str(
        lineage.get("parentStrategyVersionId")
        or version.strategyVersionId
    )
    registry = RegistryRepository(repository.connection)
    audit_records = []
    for event_type in (
        "structural_redesign_candidate_created",
        "structural_redesign_parent_archived",
        "structural_redesign_stopped",
    ):
        audit_records.extend(
            registry.list_audit_events(
                event_type=event_type,
                entity_type="StrategyVersion",
                entity_id=parent_strategy_version_id,
            )
        )
    audit_records.sort(key=lambda event: (event.createdAt, event.auditEventId))
    if not lineage and not audit_records:
        return {
            "supported": False,
            "campaignId": None,
            "generation": 0,
            "maxGenerations": 3,
            "recipeId": None,
            "recipeSummary": None,
            "parentStrategyVersionId": None,
            "parentStatus": None,
            "childStrategyVersionId": None,
            "childWorkflowRunId": None,
            "childStatus": None,
            "stopReason": None,
            "lastDecisionAt": None,
        }
    matching = [
        event
        for event in audit_records
        if event.payload.get("childStrategyVersionId")
        == version.strategyVersionId
    ]
    selected = matching[-1] if matching else (audit_records[-1] if audit_records else None)
    payload = dict(selected.payload) if selected is not None else {}
    parent = repository.get_strategy_version(parent_strategy_version_id)
    child_strategy_version_id = str(
        version.strategyVersionId
        if lineage.get("parentStrategyVersionId")
        else payload.get("childStrategyVersionId") or ""
    )
    child = (
        repository.get_strategy_version(child_strategy_version_id)
        if child_strategy_version_id
        else None
    )
    child_run = (
        current
        if child is not None and child.strategyVersionId == version.strategyVersionId
        else (
            repository.get_latest_workflow_run(
                child.strategyVersionId,
                stage="backtest",
            )
            if child is not None
            else None
        )
    )
    return {
        "supported": True,
        "campaignId": lineage.get("campaignId") or payload.get("campaignId"),
        "generation": int(
            lineage.get("generation") or payload.get("generation") or 0
        ),
        "maxGenerations": int(
            lineage.get("maxGenerations")
            or payload.get("maxGenerations")
            or 3
        ),
        "recipeId": lineage.get("recipeId") or payload.get("recipeId"),
        "recipeSummary": payload.get("recipeSummary"),
        "parentStrategyVersionId": parent_strategy_version_id,
        "parentStatus": parent.status if parent is not None else None,
        "childStrategyVersionId": (
            child.strategyVersionId if child is not None else None
        ),
        "childWorkflowRunId": (
            child_run.workflowRunId if child_run is not None else None
        ),
        "childStatus": child_run.status if child_run is not None else None,
        "stopReason": (
            payload.get("reasonCode")
            if selected is not None
            and selected.eventType == "structural_redesign_stopped"
            else None
        ),
        "lastDecisionAt": selected.createdAt if selected is not None else None,
    }


def _current_run(runs: list[WorkflowRunRecord]) -> WorkflowRunRecord:
    return max(
        runs,
        key=lambda run: (
            STAGE_ORDER[run.stage],
            run.attemptNumber,
            run.createdAt,
            run.workflowRunId,
        ),
    )


def _checkpoint_download_progress(
    contract: StrategyDataContractRecord | None,
    warehouse_root: Path | str | None,
    *,
    funding_files: int,
) -> dict[str, Any] | None:
    if contract is None or warehouse_root is None:
        return None
    checkpoint_path = (
        WarehouseLayout.from_root(warehouse_root).checkpointRoot
        / f"official-{contract.strategyDataContractId}.json"
    )
    if not checkpoint_path.is_file():
        return None
    checkpoint = load_json(checkpoint_path)
    completed = checkpoint.get("completed")
    if not isinstance(completed, dict):
        return None
    timeframes = {
        str(value)
        for value in (
            contract.contract.get("signalTimeframe"),
            contract.contract.get("executionTimeframe"),
            contract.contract.get("executionFallbackTimeframe"),
        )
        if value
    }
    target_members = int(
        (contract.contract.get("universePolicy") or {}).get("targetMembers", 0)
    )
    required = target_members * len(timeframes)
    progress: dict[str, Any] = {
        "completed": len(completed),
        "required": max(len(completed), required),
        "fundingFiles": funding_files,
    }
    preparation_mode = str(checkpoint.get("preparationMode") or "").strip()
    if preparation_mode:
        progress["mode"] = preparation_mode
    active = checkpoint.get("inProgress")
    if isinstance(active, dict):
        instrument_id = str(active.get("instrumentId") or "")
        timeframe = str(active.get("timeframe") or "")
        request_count = max(0, int(active.get("requestCount") or 0))
        row_count = max(0, int(active.get("rowCount") or 0))
        max_pages = max(0, int(active.get("maxPages") or 0))
        if instrument_id and timeframe and max_pages > 0:
            active_mode = str(active.get("mode") or preparation_mode).strip()
            progress["active"] = {
                "instrumentId": instrument_id,
                "timeframe": timeframe,
                "requestCount": request_count,
                "rowCount": row_count,
                "oldestTimestampMs": active.get("oldestTimestampMs"),
                "maxPages": max_pages,
                "percent": round(min(100.0, request_count / max_pages * 100), 1),
                "updatedAt": active.get("updatedAt"),
            }
            if active_mode:
                progress["active"]["mode"] = active_mode
                progress["mode"] = active_mode
            if "baseRows" in active:
                progress["active"]["baseRows"] = max(
                    0, int(active.get("baseRows") or 0)
                )
            if "baseEndTime" in active:
                progress["active"]["baseEndTime"] = active.get("baseEndTime")
    return progress


def build_workflow_projection(
    repository: WorkflowRepository,
    *,
    warehouse_root: Path | str | None = None,
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    archived_items: list[dict[str, Any]] = []
    for version in repository.list_strategy_versions():
        runs = repository.list_workflow_runs(
            strategy_version_id=version.strategyVersionId
        )
        if not runs:
            continue
        current = _current_run(runs)
        contracts = repository.list_strategy_data_contracts(
            strategy_version_id=version.strategyVersionId
        )
        latest_contract = contracts[-1] if contracts else None
        binding = repository.get_evaluation_binding_for_run(current.workflowRunId)
        phase = str(current.progress.get("phase") or "")
        artifacts = current.progress.get("artifacts") or {}
        diagnosis = repository.get_latest_failure_diagnosis(current.workflowRunId)
        events = repository.list_stage_events(
            strategy_version_id=version.strategyVersionId
        )
        funding_files = int(artifacts.get("downloadedFundingFiles") or 0)
        checkpoint_progress = _checkpoint_download_progress(
            latest_contract,
            warehouse_root,
            funding_files=funding_files,
        )
        download_progress = checkpoint_progress or {
            "completed": int(artifacts.get("downloadedPartitions") or 0),
            "required": int(artifacts.get("requiredPartitions") or 0),
            "fundingFiles": funding_files,
        }
        optimization_lineage = version.definition.get("optimizationLineage")
        optimization_lineage = (
            optimization_lineage if isinstance(optimization_lineage, dict) else {}
        )
        root_strategy_version_id = str(
            optimization_lineage.get("rootStrategyVersionId")
            or version.strategyVersionId
        )
        optimization_audit_record = _optimization_campaign_audit(
            repository,
            root_strategy_version_id,
        )
        optimization_audit = (
            optimization_audit_record[0]
            if optimization_audit_record is not None
            else None
        )
        optimization_campaign = {
            "rootStrategyVersionId": root_strategy_version_id,
            "campaignId": optimization_lineage.get("campaignId"),
            "phase": optimization_lineage.get("phase") or "root",
            "attemptNumber": int(optimization_lineage.get("attemptNumber") or 0),
            "maxAttempts": int(optimization_lineage.get("maxAttempts") or 3),
            "changedParameter": optimization_lineage.get("changedParameter"),
            "formalValidationConsumed": bool(
                optimization_lineage.get("formalValidationConsumed")
            ),
            "reviewed": optimization_audit is not None,
            "status": (
                optimization_audit.get("terminalStatus")
                or (
                    "challenger_queued"
                    if optimization_audit.get("challengerStrategyVersionId")
                    else "reviewed"
                )
                if optimization_audit is not None
                else "pending_review"
            ),
            "reasonCode": (
                optimization_audit.get("reasonCode")
                if optimization_audit is not None
                else None
            ),
            "lastAction": (
                optimization_audit.get("action")
                if optimization_audit is not None
                else None
            ),
            "lastDecisionAt": (
                optimization_audit_record[1]
                if optimization_audit_record is not None
                else None
            ),
        }
        structural_redesign_campaign = _structural_redesign_campaign(
            repository,
            version=version,
            current=current,
        )
        item = {
            "strategyVersionId": version.strategyVersionId,
            "strategyFamilyId": version.strategyFamilyId,
            "parentStrategyVersionId": version.parentStrategyVersionId,
            "displayName": version.displayName,
            "sourceType": version.sourceType,
            "contentHash": version.contentHash,
            "strategyDataContractId": (
                contracts[-1].strategyDataContractId if contracts else None
            ),
            "evaluationBindingId": (
                binding.evaluationBindingId if binding else None
            ),
            "workflowMode": "dual_layer_backtest",
            "evidenceClass": (
                "formal_backtest"
                if binding is not None
                else (
                    "research_smoke"
                    if "research_smoke_running"
                    in set(current.progress.get("completedPhases") or [])
                    else "pending"
                )
            ),
            "phase": phase or None,
            "phaseLabel": PHASE_LABELS.get(phase, STATUS_LABELS[current.status]),
            "dataCoverage": {
                "strategyDataContractId": (
                    contracts[-1].strategyDataContractId if contracts else None
                ),
                "dataSnapshotId": (
                    binding.dataSnapshotId
                    if binding
                    else artifacts.get("dataSnapshotId")
                ),
            },
            "downloadProgress": download_progress,
            "automaticNextStage": "local_forward",
            "stage": current.stage,
            "stageLabel": STAGE_LABELS[current.stage],
            "status": current.status,
            "statusLabel": STATUS_LABELS[current.status],
            "page": STAGE_PAGES[current.stage],
            "workflowRunId": current.workflowRunId,
            "attemptNumber": current.attemptNumber,
            "progress": current.progress,
            "result": current.result,
            "startedAt": current.startedAt,
            "checkpointAt": current.checkpointAt,
            "completedAt": current.completedAt,
            "failure": (
                {
                    "category": diagnosis.category,
                    "summary": diagnosis.summary,
                    "retryDisposition": diagnosis.retryDisposition,
                    "metrics": diagnosis.metrics,
                    "suggestions": diagnosis.suggestions,
                }
                if diagnosis
                else None
            ),
            "optimizationContext": {
                "sourceKind": "workflow_version",
                "parentStrategyVersionId": version.strategyVersionId,
                "definition": version.definition,
                "parameters": version.parameters,
                "failureSuggestions": list(diagnosis.suggestions) if diagnosis else [],
                "targetRFloor": 2.0,
            },
            "optimizationCampaign": optimization_campaign,
            "structuralRedesignCampaign": structural_redesign_campaign,
            "historyEventCount": len(events),
            "archived": version.status == "archived",
        }
        if version.status == "archived":
            archived_items.append({**item, "page": "archive"})
        else:
            items.append(item)
    items.sort(
        key=lambda item: (
            -STAGE_ORDER[str(item["stage"])],
            str(item["displayName"]),
            str(item["strategyVersionId"]),
        )
    )
    archived_items.sort(
        key=lambda item: (
            str(item["displayName"]),
            str(item["strategyVersionId"]),
        )
    )
    page_counts = Counter(str(item["page"]) for item in items)
    status_counts = Counter(str(item["status"]) for item in items)
    return {
        "version": "V13.27.6",
        "source": "workflow_orchestrator_projection_v2",
        "generatedAt": utc_now(),
        "summary": {
            "totalStrategyVersionCount": len(items) + len(archived_items),
            "strategyCount": page_counts["strategy"],
            "localSimulationCount": page_counts["local_simulation"],
            "demoCount": page_counts["demo"],
            "liveCount": page_counts["live"],
            "awaitingCount": status_counts["awaiting"],
            "queuedCount": status_counts["queued"],
            "runningCount": status_counts["running"],
            "passedCount": status_counts["passed"],
            "failedCount": status_counts["failed"],
            "blockedCount": status_counts["blocked"],
            "pausedCount": status_counts["paused"],
            "archivedCount": len(archived_items),
        },
        "items": items,
        "archivedItems": archived_items,
        "byPage": {
            page: [item for item in items if item["page"] == page]
            for page in ("strategy", "local_simulation", "demo", "live")
        },
        "safetyBoundary": {
            "readOnlyProjection": True,
            "createsOrders": False,
            "usesApiKey": False,
            "tradeApiUsed": False,
            "withdrawApiUsed": False,
            "liveExecutionEnabled": False,
        },
    }
