"""Restart-safe research-smoke plus official-data backtest orchestration."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import os
from pathlib import Path
import subprocess
from typing import Any, Callable

from alphapilot.data_foundation.checkpoint import load_json, write_json_atomic
from alphapilot.data_foundation.formal_snapshot import freeze_formal_snapshot
from alphapilot.data_foundation.official_history import (
    OfficialCollectionResult,
    OfficialPartition,
    OkxOfficialHistoryCollector,
)
from alphapilot.data_foundation.okx_public import OkxPublicClient
from alphapilot.data_foundation.research_smoke import run_research_smoke
from alphapilot.data_foundation.warehouse import WarehouseLayout
from alphapilot.evolution.evaluation.formal_strategy_backtest import (
    run_formal_strategy_backtest,
)
from alphapilot.evolution.evaluation.validation_pack import (
    FormalValidationPack,
    build_formal_validation_pack,
)
from alphapilot.evolution.forward.public_market import OkxForwardPublicMarket
from alphapilot.evolution.forward.runner import ForwardPublicMarket
from alphapilot.evolution.registry.hashing import stable_hash
from alphapilot.evolution.registry.repositories import RegistryRepository
from alphapilot.evolution.registry.types import DataSnapshotRecord

from .backtest import BacktestAdapterResult, _apply_gate_rules
from .data_contract import derive_strategy_data_contract
from .evaluation_binding import create_formal_evaluation_binding
from .local_forward_bridge import start_local_forward_after_pass
from .repository import WorkflowRepository
from .service import (
    checkpoint_workflow_run,
    complete_workflow_run,
    queue_workflow_run,
    start_workflow_run,
)
from .states import WorkflowConflict, WorkflowTransitionError
from .types import StrategyDataContractRecord, WorkflowRunRecord


PHASES = (
    "checking_local_data",
    "research_smoke_running",
    "preparing_official_data",
    "validating_official_data",
    "freezing_data_snapshot",
    "building_validation_manifests",
    "formal_backtest_running",
    "evaluating_gate",
)


@dataclass(frozen=True)
class DualLayerDependencies:
    runResearchSmoke: Callable[..., dict[str, Any]]
    collectOfficialHistory: Callable[..., OfficialCollectionResult]
    freezeFormalSnapshot: Callable[..., DataSnapshotRecord]
    buildValidationPack: Callable[..., FormalValidationPack]
    runFormalBacktest: Callable[..., BacktestAdapterResult]
    marketData: ForwardPublicMarket | None = None
    codeCommit: str = ""


def resolve_code_commit() -> str:
    configured = str(os.environ.get("ALPHAPILOT_CODE_COMMIT") or "").strip()
    if configured:
        return configured
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=Path.cwd(),
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=5,
        ).strip()
    except (OSError, subprocess.SubprocessError):
        return "unresolved-working-tree-commit"


def _default_dependencies(
    *, stop_requested: Callable[[], bool] | None = None
) -> DualLayerDependencies:
    def collect(contract: StrategyDataContractRecord, layout: WarehouseLayout):
        return OkxOfficialHistoryCollector(
            client=OkxPublicClient(),
            layout=layout,
            stop_requested=stop_requested,
        ).collect(contract)

    return DualLayerDependencies(
        runResearchSmoke=run_research_smoke,
        collectOfficialHistory=collect,
        freezeFormalSnapshot=freeze_formal_snapshot,
        buildValidationPack=build_formal_validation_pack,
        runFormalBacktest=run_formal_strategy_backtest,
        marketData=OkxForwardPublicMarket(),
        codeCommit=resolve_code_commit(),
    )


def _collection_from_dict(value: dict[str, Any]) -> OfficialCollectionResult:
    return OfficialCollectionResult(
        status=str(value["status"]),
        strategyDataContractId=str(value["strategyDataContractId"]),
        instrumentCount=int(value["instrumentCount"]),
        completedPartitionCount=int(value["completedPartitionCount"]),
        reusedPartitionCount=int(value["reusedPartitionCount"]),
        failedPartitionCount=int(value["failedPartitionCount"]),
        fundingFileCount=int(value["fundingFileCount"]),
        partitions=tuple(
            OfficialPartition(**row) for row in value.get("partitions") or []
        ),
        checkpointPath=str(value["checkpointPath"]),
        generatedAt=str(value["generatedAt"]),
        fundingPaths=tuple(value.get("fundingPaths") or []),
    )


def _pack_from_dict(value: dict[str, Any]) -> FormalValidationPack:
    return FormalValidationPack(
        strategyDataContractId=str(value["strategyDataContractId"]),
        dataSnapshotId=str(value["dataSnapshotId"]),
        walkForwardManifestHash=str(value["walkForwardManifestHash"]),
        holdoutManifestHash=str(value["holdoutManifestHash"]),
        lockedOosManifestHash=str(value["lockedOosManifestHash"]),
        regimeManifestHash=str(value["regimeManifestHash"]),
        costManifestHash=str(value["costManifestHash"]),
        holdoutSymbols=tuple(value.get("holdoutSymbols") or []),
        trainingSymbols=tuple(value.get("trainingSymbols") or []),
        walkForwardFoldCount=int(value["walkForwardFoldCount"]),
        lockedStartIndex=int(value["lockedStartIndex"]),
        manifestPaths=tuple(value.get("manifestPaths") or []),
    )


def _adapter_from_dict(value: dict[str, Any]) -> BacktestAdapterResult:
    return BacktestAdapterResult(
        metrics=dict(value.get("metrics") or {}),
        checks={str(key): bool(item) for key, item in (value.get("checks") or {}).items()},
        evidence=dict(value.get("evidence") or {}),
    )


def _block(
    workflow: WorkflowRepository,
    run_id: str,
    *,
    blocker: str,
    category: str = "data_integrity",
) -> WorkflowRunRecord:
    return complete_workflow_run(
        workflow,
        run_id,
        status="blocked",
        actor="worker",
        result={"blocker": blocker},
        evidence={"blockerHash": stable_hash({"blocker": blocker})},
        failure={
            "category": category,
            "summary": blocker,
            "retryDisposition": "same_version_retry",
            "metrics": {"blocker": blocker},
            "suggestions": ["Resume official data preparation from its checkpoint."],
        },
    )


def run_dual_layer_backtest_workflow(
    workflow: WorkflowRepository,
    registry: RegistryRepository,
    workflow_run_id: str,
    warehouse_root: Path | str,
    output_root: Path | str,
    dependencies: DualLayerDependencies | None = None,
) -> WorkflowRunRecord:
    run = workflow.get_workflow_run(workflow_run_id)
    if run is None:
        raise WorkflowConflict(f"workflow_run_missing:{workflow_run_id}")
    if run.stage != "backtest":
        raise WorkflowTransitionError(f"workflow_run_is_not_backtest:{run.stage}")
    if run.status in {"passed", "failed", "blocked", "cancelled"}:
        return run
    if run.status == "awaiting":
        run = queue_workflow_run(workflow, run.workflowRunId, actor="system")
    if run.status == "queued":
        run = start_workflow_run(workflow, run.workflowRunId, actor="worker")
    if run.status == "paused":
        return run
    if run.status != "running":
        raise WorkflowTransitionError(f"workflow_run_not_executable:{run.status}")

    layout = WarehouseLayout.from_root(warehouse_root)
    layout.ensure_directories()
    run_root = Path(output_root).resolve() / run.workflowRunId
    run_root.mkdir(parents=True, exist_ok=True)
    progress = dict(run.progress or {})
    history = list(progress.get("phaseHistory") or [])
    completed = set(progress.get("completedPhases") or [])
    artifacts = dict(progress.get("artifacts") or {})

    def current() -> WorkflowRunRecord:
        value = workflow.get_workflow_run(run.workflowRunId)
        if value is None:
            raise WorkflowConflict(f"workflow_run_missing:{run.workflowRunId}")
        return value

    deps = dependencies or _default_dependencies(
        stop_requested=lambda: current().status in {"paused", "cancelled"}
    )

    def begin(name: str) -> bool:
        state = current()
        if state.status in {"paused", "cancelled"}:
            return False
        if name not in history:
            history.append(name)
        checkpoint_workflow_run(
            workflow,
            run.workflowRunId,
            progress={
                "phase": name,
                "phaseHistory": list(history),
                "completedPhases": sorted(completed, key=PHASES.index),
                "artifacts": dict(artifacts),
            },
            actor="worker",
        )
        return True

    def finish(name: str, **new_artifacts: Any) -> None:
        completed.add(name)
        artifacts.update(new_artifacts)
        checkpoint_workflow_run(
            workflow,
            run.workflowRunId,
            progress={
                "phase": name,
                "phaseHistory": list(history),
                "completedPhases": sorted(completed, key=PHASES.index),
                "artifacts": dict(artifacts),
            },
            actor="worker",
        )

    try:
        version = workflow.get_strategy_version(run.strategyVersionId)
        if version is None:
            raise WorkflowConflict(f"strategy_version_missing:{run.strategyVersionId}")

        if not begin("checking_local_data"):
            return current()
        contract = derive_strategy_data_contract(version, workflow)
        finish(
            "checking_local_data",
            strategyDataContractId=contract.strategyDataContractId,
        )

        smoke_path = run_root / "research-smoke.json"
        if not begin("research_smoke_running"):
            return current()
        if "research_smoke_running" in completed and smoke_path.is_file():
            smoke = load_json(smoke_path)
        else:
            smoke = deps.runResearchSmoke(contract, layout, smoke_path)
            write_json_atomic(smoke_path, smoke)
        finish("research_smoke_running", researchSmokePath=str(smoke_path))

        collection_path = run_root / "official-collection.json"
        if not begin("preparing_official_data"):
            return current()
        if "preparing_official_data" in completed and collection_path.is_file():
            collection = _collection_from_dict(load_json(collection_path))
            if collection.status != "completed":
                # V13.27.4 could mark a paused partial collection as complete.
                # Re-enter collection so existing durable partition checkpoints
                # are reused instead of validating the partial result.
                completed.discard("preparing_official_data")
                collection = deps.collectOfficialHistory(contract, layout)
                write_json_atomic(collection_path, collection.to_dict())
        else:
            collection = deps.collectOfficialHistory(contract, layout)
            write_json_atomic(collection_path, collection.to_dict())
        collection_artifacts = {
            "officialCollectionPath": str(collection_path),
            "downloadedPartitions": collection.completedPartitionCount,
            "requiredPartitions": (
                collection.completedPartitionCount + collection.failedPartitionCount
            ),
            "downloadedFundingFiles": collection.fundingFileCount,
        }
        state_after_collection = current()
        if (
            collection.status == "paused"
            or state_after_collection.status in {"paused", "cancelled"}
        ):
            artifacts.update(collection_artifacts)
            if state_after_collection.status in {"running", "paused"}:
                checkpoint_workflow_run(
                    workflow,
                    run.workflowRunId,
                    progress={
                        "phase": "preparing_official_data",
                        "phaseHistory": list(history),
                        "completedPhases": sorted(completed, key=PHASES.index),
                        "artifacts": dict(artifacts),
                    },
                    actor="worker",
                )
            return current()
        finish(
            "preparing_official_data",
            **collection_artifacts,
        )

        if not begin("validating_official_data"):
            return current()
        if collection.status != "completed":
            return _block(
                workflow,
                run.workflowRunId,
                blocker=f"official_collection_not_complete:{collection.status}",
            )
        if collection.failedPartitionCount:
            return _block(
                workflow,
                run.workflowRunId,
                blocker=f"official_collection_partition_failures:{collection.failedPartitionCount}",
            )
        finish("validating_official_data")

        if not begin("freezing_data_snapshot"):
            return current()
        snapshot_id = str(artifacts.get("dataSnapshotId") or "")
        snapshot = registry.get_data_snapshot(snapshot_id) if snapshot_id else None
        if snapshot is None:
            snapshot = deps.freezeFormalSnapshot(
                collection, contract, layout, registry
            )
        finish("freezing_data_snapshot", dataSnapshotId=snapshot.dataSnapshotId)

        pack_path = run_root / "validation-pack.json"
        if not begin("building_validation_manifests"):
            return current()
        if "building_validation_manifests" in completed and pack_path.is_file():
            pack = _pack_from_dict(load_json(pack_path))
        else:
            pack = deps.buildValidationPack(
                contract,
                snapshot,
                canonical_root=layout.canonicalRoot,
                manifest_root=layout.manifestRoot,
            )
            write_json_atomic(pack_path, asdict(pack))
        binding = create_formal_evaluation_binding(
            workflow,
            run=current(),
            contract=contract,
            snapshot=snapshot,
            validation_pack=pack,
            canonical_root=str(layout.canonicalRoot),
            research_smoke=smoke,
        )
        finish(
            "building_validation_manifests",
            validationPackPath=str(pack_path),
            evaluationBindingId=binding.evaluationBindingId,
        )

        adapter_path = run_root / "formal-adapter-result.json"
        if not begin("formal_backtest_running"):
            return current()
        if "formal_backtest_running" in completed and adapter_path.is_file():
            adapter_result = _adapter_from_dict(load_json(adapter_path))
        else:
            adapter_result = deps.runFormalBacktest(
                version, binding, snapshot, layout.manifestRoot
            )
            write_json_atomic(adapter_path, asdict(adapter_result))
        finish("formal_backtest_running", formalAdapterResultPath=str(adapter_path))

        if not begin("evaluating_gate"):
            return current()
        gate = workflow.get_gate_profile(str(run.gateProfileId or ""))
        if gate is None:
            return _block(
                workflow, run.workflowRunId, blocker="gate_profile_missing"
            )
        manifest = {
            "targetR": contract.contract["targetR"],
            "costModel": binding.costModel,
        }
        evaluated_checks = _apply_gate_rules(
            adapter_result,
            manifest=manifest,
            gate_rules=gate.rules,
        )
        passed = bool(evaluated_checks) and all(evaluated_checks.values())
        result = {
            "metrics": adapter_result.metrics,
            "checks": evaluated_checks,
            "researchSmoke": {
                "status": smoke.get("status"),
                "formalPromotionEligible": False,
            },
        }
        evidence = {
            **adapter_result.evidence,
            "evaluationBindingId": binding.evaluationBindingId,
            "strategyDataContractId": contract.strategyDataContractId,
            "dataSnapshotId": snapshot.dataSnapshotId,
            "formalEvidenceOnly": True,
        }
        finish("evaluating_gate")
        if passed:
            passed_run = complete_workflow_run(
                workflow,
                run.workflowRunId,
                status="passed",
                actor="worker",
                result=result,
                evidence=evidence,
            )
            if deps.marketData is None:
                return passed_run
            return start_local_forward_after_pass(
                workflow,
                registry,
                version,
                passed_run,
                binding,
                code_commit=deps.codeCommit or resolve_code_commit(),
                market_data=deps.marketData,
            )
        failed_checks = sorted(key for key, value in evaluated_checks.items() if not value)
        return complete_workflow_run(
            workflow,
            run.workflowRunId,
            status="failed",
            actor="worker",
            result=result,
            evidence=evidence,
            failure={
                "category": "strategy_performance",
                "summary": f"Backtest gates failed: {', '.join(failed_checks)}",
                "retryDisposition": "new_version_required",
                "metrics": {"failedChecks": failed_checks},
                "suggestions": ["Create a changed challenger strategy version."],
            },
        )
    except Exception as error:
        state = current()
        if state.status in {"paused", "cancelled", "blocked", "failed", "passed"}:
            return state
        return _block(
            workflow,
            run.workflowRunId,
            blocker=f"dual_layer_worker_error:{type(error).__name__}:{error}",
            category="worker_operational",
        )
