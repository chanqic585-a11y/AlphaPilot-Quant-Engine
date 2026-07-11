"""Build one current, page-specific workflow projection per strategy version."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from alphapilot.data_foundation.checkpoint import load_json
from alphapilot.data_foundation.warehouse import WarehouseLayout
from alphapilot.evolution.registry.types import utc_now

from .repository import WorkflowRepository
from .states import STAGE_LABELS, STAGE_ORDER, STAGE_PAGES, STATUS_LABELS
from .types import StrategyDataContractRecord, WorkflowRunRecord


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
) -> dict[str, int] | None:
    if contract is None or warehouse_root is None:
        return None
    checkpoint_path = (
        WarehouseLayout.from_root(warehouse_root).checkpointRoot
        / f"official-{contract.strategyDataContractId}.json"
    )
    if not checkpoint_path.is_file():
        return None
    completed = load_json(checkpoint_path).get("completed")
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
    return {
        "completed": len(completed),
        "required": max(len(completed), required),
        "fundingFiles": funding_files,
    }


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
        "version": "V13.27.3",
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
