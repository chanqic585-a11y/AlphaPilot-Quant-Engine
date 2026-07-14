"""Build immutable-version and current-family workflow projections."""

from __future__ import annotations

from collections import Counter, defaultdict
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
    "preparing_official_data": "准备本地正式数据",
    "validating_official_data": "校验本地正式数据",
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


def _current_family_projection(
    items: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Keep one user-facing current item per family without deleting evidence."""

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        grouped[str(item["strategyFamilyId"])].append(item)

    status_priority = {
        "running": 7,
        "queued": 6,
        "awaiting": 5,
        "paused": 4,
        "passed": 3,
        "blocked": 2,
        "failed": 1,
        "cancelled": 0,
    }
    current_items: list[dict[str, Any]] = []
    history_items: list[dict[str, Any]] = []
    for family_items in grouped.values():
        furthest_stage = max(STAGE_ORDER[str(item["stage"])] for item in family_items)
        candidates = [
            item
            for item in family_items
            if STAGE_ORDER[str(item["stage"])] == furthest_stage
        ]
        candidate_parent_ids = {
            str(item.get("parentStrategyVersionId") or "")
            for item in candidates
            if item.get("parentStrategyVersionId")
        }
        leaves = [
            item
            for item in candidates
            if str(item["strategyVersionId"]) not in candidate_parent_ids
        ] or candidates
        current = max(
            leaves,
            key=lambda item: (
                str(item.get("strategyVersionCreatedAt") or ""),
                status_priority.get(str(item.get("status") or ""), -1),
                int(item.get("attemptNumber") or 0),
                str(item["strategyVersionId"]),
            ),
        )
        current_items.append(
            {
                **current,
                "familyCurrent": True,
                "familyVersionCount": len(family_items),
                "historicalAttemptCount": max(0, len(family_items) - 1),
            }
        )
        for item in family_items:
            if item["strategyVersionId"] == current["strategyVersionId"]:
                continue
            history_items.append(
                {
                    **item,
                    "familyCurrent": False,
                    "superseded": True,
                    "supersededByStrategyVersionId": current["strategyVersionId"],
                }
            )

    sort_key = lambda item: (
        -STAGE_ORDER[str(item["stage"])],
        str(item["displayName"]),
        str(item["strategyVersionId"]),
    )
    current_items.sort(key=sort_key)
    history_items.sort(key=sort_key)
    return current_items, history_items


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
        / "local-formal"
        / f"{contract.strategyDataContractId}.json"
    )
    if not checkpoint_path.is_file():
        return None
    checkpoint = load_json(checkpoint_path)
    selected = checkpoint.get("selectedInstruments") or []
    if not isinstance(selected, list):
        selected = []
    timeframes = checkpoint.get("requiredTimeframes") or []
    if not isinstance(timeframes, list):
        timeframes = []
    target_members = int(
        (contract.contract.get("universePolicy") or {}).get("targetMembers", 0)
    )
    required = target_members * len(timeframes)
    progress: dict[str, Any] = {
        "completed": len(selected) * len(timeframes),
        "required": required,
        "fundingFiles": max(funding_files, len(selected)),
        "mode": "user_approved_local",
        "status": str(checkpoint.get("status") or "unknown"),
    }
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
            "strategyVersionCreatedAt": version.createdAt,
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
    current_family_items, history_items = _current_family_projection(items)
    page_counts = Counter(str(item["page"]) for item in items)
    status_counts = Counter(str(item["status"]) for item in items)
    current_page_counts = Counter(str(item["page"]) for item in current_family_items)
    current_status_counts = Counter(
        str(item["status"]) for item in current_family_items
    )
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
            "activeStrategyFamilyCount": len(current_family_items),
            "archivedStrategyFamilyCount": len(
                {str(item["strategyFamilyId"]) for item in archived_items}
            ),
            "historicalAttemptCount": len(history_items),
            "currentStrategyCount": current_page_counts["strategy"],
            "currentLocalSimulationCount": current_page_counts["local_simulation"],
            "currentDemoCount": current_page_counts["demo"],
            "currentLiveCount": current_page_counts["live"],
            "currentAwaitingCount": current_status_counts["awaiting"],
            "currentQueuedCount": current_status_counts["queued"],
            "currentRunningCount": current_status_counts["running"],
            "currentPassedCount": current_status_counts["passed"],
            "currentFailedCount": current_status_counts["failed"],
            "currentBlockedCount": current_status_counts["blocked"],
            "currentPausedCount": current_status_counts["paused"],
        },
        "items": items,
        "currentFamilyItems": current_family_items,
        "historyItems": history_items,
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
