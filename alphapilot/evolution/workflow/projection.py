"""Build one current, page-specific workflow projection per strategy version."""

from __future__ import annotations

from collections import Counter
from typing import Any

from alphapilot.evolution.registry.types import utc_now

from .repository import WorkflowRepository
from .states import STAGE_LABELS, STAGE_ORDER, STAGE_PAGES, STATUS_LABELS
from .types import WorkflowRunRecord


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


def build_workflow_projection(repository: WorkflowRepository) -> dict[str, Any]:
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
        binding = repository.get_evaluation_binding_for_run(current.workflowRunId)
        diagnosis = repository.get_latest_failure_diagnosis(current.workflowRunId)
        events = repository.list_stage_events(
            strategy_version_id=version.strategyVersionId
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
        "version": "V13.27.1",
        "source": "workflow_orchestrator_projection_v1",
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
