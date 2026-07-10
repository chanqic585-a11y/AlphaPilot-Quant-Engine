"""Manifest-bound, restart-safe backtest workflow execution."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from alphapilot.data_foundation.checkpoint import write_json_atomic
from alphapilot.evolution.registry.hashing import sha256_file, stable_hash
from alphapilot.evolution.registry.repositories import RegistryRepository

from .repository import WorkflowRepository
from .service import (
    checkpoint_workflow_run,
    complete_workflow_run,
    start_workflow_run,
)
from .states import WorkflowConflict, WorkflowTransitionError
from .types import EvaluationBindingRecord, StrategyVersionRecord, WorkflowRunRecord


@dataclass(frozen=True)
class BacktestAdapterResult:
    metrics: dict[str, Any]
    checks: dict[str, bool]
    evidence: dict[str, Any]


class BacktestAdapterError(RuntimeError):
    """Raised when an allowlisted backtest adapter cannot complete."""


CheckpointCallback = Callable[[dict[str, Any]], None]
BacktestAdapterExecutor = Callable[
    [dict[str, Any], CheckpointCallback],
    BacktestAdapterResult,
]


ADAPTERS = {
    "alpha191_crypto_subset_v13_5_23": {
        "module": "alphapilot.reports.generate_v13_5_23_alpha191_crypto_subset_replay_report",
        "reportPath": "reports/v13_5_23_alpha191_crypto_subset_replay_report.json",
        "parser": "alpha191_v13_5_23",
    },
    "factor_run_research_v13_17": {
        "module": "alphapilot.reports.generate_v13_17_factor_run_backtest_report",
        "reportPath": "reports/v13_17_factor_run_backtest_report.json",
        "parser": "factor_run_v13_17",
    },
}


@contextmanager
def _adapter_process_lock(
    lock_path: Path,
    status_reader: Any,
):
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+b") as lock_handle:
        lock_handle.seek(0, os.SEEK_END)
        if lock_handle.tell() == 0:
            lock_handle.write(b"0")
            lock_handle.flush()
        acquired = False
        try:
            while not acquired:
                status = status_reader() if callable(status_reader) else "running"
                if status in {"paused", "cancelled"}:
                    raise BacktestAdapterError(f"backtest_worker_{status}")
                try:
                    lock_handle.seek(0)
                    if os.name == "nt":
                        import msvcrt

                        msvcrt.locking(lock_handle.fileno(), msvcrt.LK_NBLCK, 1)
                    else:
                        import fcntl

                        fcntl.flock(
                            lock_handle.fileno(),
                            fcntl.LOCK_EX | fcntl.LOCK_NB,
                        )
                    acquired = True
                except OSError:
                    time.sleep(0.25)
            yield
        finally:
            if acquired:
                lock_handle.seek(0)
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(lock_handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)


def _float(value: Any, fallback: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return fallback
    return parsed if parsed == parsed else fallback


def _build_manifest(
    run: WorkflowRunRecord,
    version: StrategyVersionRecord,
    gate_rules: dict[str, Any],
    snapshot: Any,
    binding: EvaluationBindingRecord | None = None,
) -> dict[str, Any]:
    backtest = version.definition.get("backtest")
    backtest_config = backtest if isinstance(backtest, dict) else {}
    bound = binding is not None
    core = {
        "schemaVersion": "workflow_backtest_manifest_v1",
        "workflowRunId": run.workflowRunId,
        "strategyVersionId": version.strategyVersionId,
        "strategyContentHash": version.contentHash,
        "gateProfileId": run.gateProfileId,
        "gateRules": gate_rules,
        "adapterId": backtest_config.get("adapterId"),
        "evaluationBindingId": binding.evaluationBindingId if binding else None,
        "strategyDataContractId": (
            binding.strategyDataContractId if binding else None
        ),
        "dataSnapshotId": (
            binding.dataSnapshotId if binding else backtest_config.get("dataSnapshotId")
        ),
        "dataSnapshotContentHash": getattr(snapshot, "contentHash", None),
        "walkForwardManifestHash": (
            binding.walkForwardManifestHash
            if bound
            else backtest_config.get("walkForwardManifestHash")
        ),
        "holdoutManifestHash": (
            binding.holdoutManifestHash if bound else None
        ),
        "lockedOosManifestHash": (
            binding.lockedOosManifestHash
            if bound
            else backtest_config.get("lockedOosManifestHash")
        ),
        "regimeManifestHash": (
            binding.evidence.get("regimeManifestHash") if bound else None
        ),
        "costManifestHash": (
            binding.evidence.get("costManifestHash") if bound else None
        ),
        "costModel": (
            binding.costModel if bound else backtest_config.get("costModel")
        ),
        "targetR": version.definition.get("targetR"),
        "attemptNumber": run.attemptNumber,
    }
    return {**core, "manifestHash": stable_hash(core, prefix="backtest_manifest")}


def _prerequisite_errors(
    manifest: dict[str, Any],
    *,
    snapshot: Any,
) -> list[str]:
    errors: list[str] = []
    adapter_id = str(manifest.get("adapterId") or "")
    if adapter_id not in ADAPTERS and adapter_id != "test_adapter":
        errors.append(f"unsupported_adapter:{adapter_id or 'missing'}")
    snapshot_id = str(manifest.get("dataSnapshotId") or "")
    if not snapshot_id:
        errors.append("data_snapshot_id_missing")
    elif snapshot is None:
        errors.append(f"data_snapshot_not_registered:{snapshot_id}")
    elif not bool(snapshot.manifest.get("pointInTimeValidated")):
        errors.append(f"data_snapshot_not_point_in_time_validated:{snapshot_id}")
    elif not bool(snapshot.manifest.get("formalResearchEligible")):
        errors.append(f"data_snapshot_not_formal_research_eligible:{snapshot_id}")
    walk_forward = str(manifest.get("walkForwardManifestHash") or "")
    if not walk_forward.startswith("walk_forward_"):
        errors.append("purged_walk_forward_manifest_missing")
    if not str(manifest.get("lockedOosManifestHash") or ""):
        errors.append("locked_oos_manifest_missing")
    cost_model = manifest.get("costModel")
    if not isinstance(cost_model, dict):
        errors.append("cost_model_missing")
    else:
        for key in ("feeRate", "slippageRate"):
            if key not in cost_model or _float(cost_model.get(key), -1.0) < 0:
                errors.append(f"cost_model_{key}_invalid")
    if _float(manifest.get("targetR")) < 2.0:
        errors.append("target_r_below_2")
    return errors


def _apply_gate_rules(
    adapter_result: BacktestAdapterResult,
    *,
    manifest: dict[str, Any],
    gate_rules: dict[str, Any],
) -> dict[str, bool]:
    metrics = adapter_result.metrics
    supplied = adapter_result.checks
    trade_count = metrics.get("tradeCount", metrics.get("filledSignalCount"))
    maximum_drawdown = metrics.get(
        "maximumDrawdownR", metrics.get("maxDrawdownR")
    )
    checks = {
        "minimumTargetR": _float(manifest.get("targetR"))
        >= _float(gate_rules.get("minimumTargetR"), 2.0),
        "minimumTradeCount": _float(trade_count, -1.0)
        >= _float(gate_rules.get("minimumTradeCount"), 30.0),
        "minimumProfitFactor": _float(metrics.get("profitFactor"), -1.0)
        >= _float(gate_rules.get("minimumProfitFactor"), 1.1),
        "positiveAverageNetR": _float(metrics.get("averageNetR"), -1.0)
        >= _float(gate_rules.get("minimumAverageNetR"), 0.0),
        "maximumDrawdown": maximum_drawdown is not None
        and _float(maximum_drawdown, float("inf"))
        <= _float(gate_rules.get("maximumDrawdownR"), 20.0),
        "costStress": (not bool(gate_rules.get("requiresCostStress")))
        or bool(supplied.get("costStress")),
        "stability": (not bool(gate_rules.get("requiresStability")))
        or bool(supplied.get("stability")),
        "lockedOos": (not bool(gate_rules.get("requiresLockedOos")))
        or bool(supplied.get("lockedOos")),
    }
    for key, value in supplied.items():
        if key not in checks:
            checks[key] = bool(value)
    return checks


def _parse_alpha191(report: dict[str, Any], report_path: Path) -> BacktestAdapterResult:
    decision = report.get("decision") if isinstance(report.get("decision"), dict) else {}
    paper = (
        report.get("localPaperSimulation")
        if isinstance(report.get("localPaperSimulation"), dict)
        else {}
    )
    metrics = paper.get("ledgerMetrics") if isinstance(paper.get("ledgerMetrics"), dict) else {}
    best = report.get("bestRawCandidate") if isinstance(report.get("bestRawCandidate"), dict) else {}
    best_metrics = best.get("metrics") if isinstance(best.get("metrics"), dict) else {}
    checks = {
        "rawReplayGate": bool(decision.get("rawReplayGatePassed")),
        "exitAwareGate": bool(decision.get("exitAwareGatePassed")),
        "localPaperGate": bool(decision.get("localPaperGatePassed")),
        "minimumTradeCount": _float(metrics.get("filledSignalCount")) >= 30,
        "minimumProfitFactor": _float(metrics.get("profitFactor")) >= 1.1,
        "targetR": _float(best.get("targetRMultiple")) >= 2.0,
    }
    return BacktestAdapterResult(
        metrics={**best_metrics, **metrics},
        checks=checks,
        evidence={
            "reportPath": str(report_path),
            "reportSha256": sha256_file(report_path),
            "reportId": report.get("reportId"),
            "reportVersion": report.get("version"),
        },
    )


def _parse_factor_run(report: dict[str, Any], report_path: Path) -> BacktestAdapterResult:
    blockers = report.get("blockers") if isinstance(report.get("blockers"), list) else []
    checks = {
        "formalPromotionEligible": bool(report.get("formalPromotionEligible")),
        "noFormalBlockers": len(blockers) == 0,
    }
    return BacktestAdapterResult(
        metrics={
            "matrixRows": (report.get("matrix") or {}).get("rowCount"),
            "experimentCount": len(report.get("experiments") or []),
            "modelCount": len(report.get("models") or []),
            "candidateCount": len(report.get("strategyCandidates") or []),
        },
        checks=checks,
        evidence={
            "reportPath": str(report_path),
            "reportSha256": sha256_file(report_path),
            "reportId": report.get("reportId"),
            "reportVersion": report.get("version"),
            "blockers": blockers,
        },
    )


def execute_registered_adapter(
    context: dict[str, Any],
    checkpoint: CheckpointCallback,
) -> BacktestAdapterResult:
    adapter_id = str(context.get("adapterId") or "")
    adapter = ADAPTERS.get(adapter_id)
    if adapter is None:
        raise BacktestAdapterError(f"backtest_adapter_not_allowlisted:{adapter_id}")
    project_root = Path(context["projectRoot"])
    run_root = Path(context["runRoot"])
    run_root.mkdir(parents=True, exist_ok=True)
    log_path = run_root / "adapter.log"
    report_path = project_root / str(adapter["reportPath"])
    command = [sys.executable, "-m", str(adapter["module"])]
    if adapter_id == "factor_run_research_v13_17":
        command.extend(["--snapshot-id", str(context["dataSnapshotId"])])
    checkpoint({"phase": "adapter_lock_waiting", "commandId": adapter_id})
    status_reader = context.get("workflowStatus")
    lock_path = Path(context["adapterLockPath"])
    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    with _adapter_process_lock(lock_path, status_reader):
        checkpoint({"phase": "adapter_process_started", "commandId": adapter_id})
        with log_path.open("a", encoding="utf-8") as log_handle:
            process = subprocess.Popen(
                command,
                cwd=project_root,
                stdin=subprocess.DEVNULL,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                creationflags=creation_flags,
            )
            while process.poll() is None:
                status = status_reader() if callable(status_reader) else "running"
                if status in {"paused", "cancelled"}:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)
                    raise BacktestAdapterError(f"backtest_worker_{status}")
                time.sleep(0.25)
            return_code = int(process.returncode or 0)
    if return_code != 0:
        error_tail = log_path.read_text(encoding="utf-8", errors="replace")[-2000:]
        raise BacktestAdapterError(
            f"backtest_adapter_failed:{adapter_id}:{return_code}:{error_tail}"
        )
    if not report_path.is_file():
        raise BacktestAdapterError(f"backtest_report_missing:{report_path}")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if not isinstance(report, dict):
        raise BacktestAdapterError(f"backtest_report_invalid:{report_path}")
    checkpoint({"phase": "adapter_report_loaded", "reportPath": str(report_path)})
    if adapter["parser"] == "alpha191_v13_5_23":
        return _parse_alpha191(report, report_path)
    if adapter["parser"] == "factor_run_v13_17":
        return _parse_factor_run(report, report_path)
    raise BacktestAdapterError(f"backtest_parser_not_allowlisted:{adapter['parser']}")


def _load_persisted_result(
    path: Path,
    *,
    manifest_hash: str,
) -> BacktestAdapterResult | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    expected_hash = str(payload.get("resultHash") or "")
    core = {key: value for key, value in payload.items() if key != "resultHash"}
    if expected_hash != stable_hash(core, prefix="backtest_result"):
        return None
    evidence = payload.get("evidence")
    if not isinstance(evidence, dict) or evidence.get("manifestHash") != manifest_hash:
        return None
    metrics = payload.get("metrics")
    checks = payload.get("checks")
    if not isinstance(metrics, dict) or not isinstance(checks, dict):
        return None
    return BacktestAdapterResult(
        metrics=metrics,
        checks={str(key): bool(value) for key, value in checks.items()},
        evidence=evidence,
    )


def run_backtest_workflow(
    workflow: WorkflowRepository,
    registry: RegistryRepository,
    workflow_run_id: str,
    *,
    output_root: Path | str = "data/workflow/backtests",
    adapter_executor: BacktestAdapterExecutor = execute_registered_adapter,
    recover_running: bool = False,
) -> WorkflowRunRecord:
    run = workflow.get_workflow_run(workflow_run_id)
    if run is None:
        raise WorkflowConflict(f"workflow_run_missing:{workflow_run_id}")
    if run.stage != "backtest":
        raise WorkflowTransitionError(f"workflow_run_is_not_backtest:{run.stage}")
    if run.status in {"passed", "failed", "blocked", "cancelled"}:
        return run
    if run.status == "queued":
        run = start_workflow_run(workflow, run.workflowRunId, actor="worker")
    elif run.status == "running" and not recover_running:
        raise WorkflowTransitionError("backtest_run_already_has_active_worker")
    elif run.status != "running":
        raise WorkflowTransitionError(f"backtest_run_not_executable:{run.status}")

    version = workflow.get_strategy_version(run.strategyVersionId)
    if version is None:
        raise WorkflowConflict(f"strategy_version_missing:{run.strategyVersionId}")
    gate = workflow.get_gate_profile(str(run.gateProfileId or ""))
    gate_rules = gate.rules if gate is not None else {}
    backtest = version.definition.get("backtest")
    backtest_config = backtest if isinstance(backtest, dict) else {}
    binding = workflow.get_evaluation_binding_for_run(run.workflowRunId)
    contracts = workflow.list_strategy_data_contracts(
        strategy_version_id=version.strategyVersionId
    )
    snapshot_id = str(
        binding.dataSnapshotId
        if binding is not None
        else backtest_config.get("dataSnapshotId") or ""
    )
    snapshot = registry.get_data_snapshot(snapshot_id) if snapshot_id else None
    manifest = _build_manifest(
        run, version, gate_rules, snapshot, binding=binding
    )
    run_root = Path(output_root).resolve() / run.workflowRunId
    write_json_atomic(run_root / "manifest.json", manifest)
    checkpoint_workflow_run(
        workflow,
        run.workflowRunId,
        progress={"phase": "manifest_validated", "manifestHash": manifest["manifestHash"]},
        actor="worker",
    )

    prerequisite_errors = [] if gate is not None else ["gate_profile_missing"]
    if contracts and binding is None:
        prerequisite_errors.append("evaluation_binding_missing")
    if binding is not None and binding.gateProfileId != run.gateProfileId:
        prerequisite_errors.append("evaluation_binding_gate_profile_mismatch")
    prerequisite_errors.extend(_prerequisite_errors(manifest, snapshot=snapshot))
    if prerequisite_errors:
        return complete_workflow_run(
            workflow,
            run.workflowRunId,
            status="blocked",
            actor="worker",
            result={"prerequisiteErrors": prerequisite_errors},
            evidence={"manifestHash": manifest["manifestHash"]},
            failure={
                "category": "data_integrity",
                "summary": "; ".join(prerequisite_errors),
                "retryDisposition": "manual_review",
                "metrics": {"prerequisiteErrors": prerequisite_errors},
                "suggestions": [
                    "Bind a registered point-in-time DataSnapshot and formal evaluation manifests in a new strategy version."
                ],
            },
        )

    def save_checkpoint(progress: dict[str, Any]) -> None:
        current = workflow.get_workflow_run(run.workflowRunId)
        if current is None or current.status == "cancelled":
            return
        checkpoint_workflow_run(
            workflow,
            run.workflowRunId,
            progress={**progress, "manifestHash": manifest["manifestHash"]},
            actor="worker",
        )

    result_path = run_root / "result.json"
    adapter_result = _load_persisted_result(
        result_path,
        manifest_hash=manifest["manifestHash"],
    )
    if adapter_result is None:
        def workflow_status() -> str:
            current = workflow.get_workflow_run(run.workflowRunId)
            return current.status if current is not None else "cancelled"

        context = {
            **manifest,
            "projectRoot": str(Path.cwd().resolve()),
            "runRoot": str(run_root),
            "adapterLockPath": str(
                Path(output_root).resolve()
                / ".adapter_locks"
                / f"{manifest['adapterId']}.lock"
            ),
            "strategyDefinition": version.definition,
            "strategyParameters": version.parameters,
            "workflowStatus": workflow_status,
        }
        try:
            adapter_result = adapter_executor(context, save_checkpoint)
        except Exception as error:
            current = workflow.get_workflow_run(run.workflowRunId)
            if current is not None and current.status in {"paused", "cancelled"}:
                return current
            return complete_workflow_run(
                workflow,
                run.workflowRunId,
                status="blocked",
                actor="worker",
                result={"adapterError": str(error)},
                evidence={"manifestHash": manifest["manifestHash"]},
                failure={
                    "category": "worker_operational",
                    "summary": str(error),
                    "retryDisposition": "same_version_retry",
                    "metrics": {},
                    "suggestions": ["Retry from the latest persisted checkpoint."],
                },
            )

    evaluated_checks = _apply_gate_rules(
        adapter_result,
        manifest=manifest,
        gate_rules=gate_rules,
    )
    passed = bool(evaluated_checks) and all(evaluated_checks.values())
    result_payload = {
        "status": "passed" if passed else "failed",
        "metrics": adapter_result.metrics,
        "checks": evaluated_checks,
        "evidence": {
            **adapter_result.evidence,
            "manifestHash": manifest["manifestHash"],
            "dataSnapshotId": manifest["dataSnapshotId"],
            "dataSnapshotContentHash": manifest["dataSnapshotContentHash"],
            "evaluationBindingId": manifest.get("evaluationBindingId"),
            "strategyDataContractId": manifest.get("strategyDataContractId"),
            "walkForwardManifestHash": manifest["walkForwardManifestHash"],
            "holdoutManifestHash": manifest.get("holdoutManifestHash"),
            "lockedOosManifestHash": manifest["lockedOosManifestHash"],
            "regimeManifestHash": manifest.get("regimeManifestHash"),
            "costManifestHash": manifest.get("costManifestHash"),
        },
    }
    result_payload["resultHash"] = stable_hash(result_payload, prefix="backtest_result")
    write_json_atomic(result_path, result_payload)
    current = workflow.get_workflow_run(run.workflowRunId)
    if current is None:
        raise WorkflowConflict(f"workflow_run_missing:{run.workflowRunId}")
    if current.status == "cancelled":
        return current
    save_checkpoint(
        {
            "phase": "result_persisted",
            "resultHash": result_payload["resultHash"],
        }
    )
    current = workflow.get_workflow_run(run.workflowRunId)
    if current is None:
        raise WorkflowConflict(f"workflow_run_missing:{run.workflowRunId}")
    if current.status == "paused":
        return current
    if current.status != "running":
        return current
    if passed:
        return complete_workflow_run(
            workflow,
            run.workflowRunId,
            status="passed",
            actor="worker",
            result={"metrics": adapter_result.metrics, "checks": evaluated_checks},
            evidence=result_payload["evidence"],
        )
    failed_checks = sorted(
        key for key, value in evaluated_checks.items() if not bool(value)
    )
    return complete_workflow_run(
        workflow,
        run.workflowRunId,
        status="failed",
        actor="worker",
        result={"metrics": adapter_result.metrics, "checks": evaluated_checks},
        evidence=result_payload["evidence"],
        failure={
            "category": "strategy_performance",
            "summary": f"Backtest gates failed: {', '.join(failed_checks)}",
            "retryDisposition": "new_version_required",
            "metrics": {
                "failedChecks": failed_checks,
                "metrics": adapter_result.metrics,
            },
            "suggestions": [
                "Create a changed challenger version and restart from backtesting."
            ],
        },
    )
