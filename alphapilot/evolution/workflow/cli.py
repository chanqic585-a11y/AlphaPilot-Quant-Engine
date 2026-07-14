"""Command-line boundary for the local workflow orchestrator."""

from __future__ import annotations

import argparse
from concurrent.futures import Future, ThreadPoolExecutor
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Sequence

from alphapilot.evolution.registry.database import connect_registry
from alphapilot.evolution.registry.repositories import RegistryRepository
from alphapilot.evolution.forward.public_market import OkxForwardPublicMarket
from alphapilot.data_foundation.research_smoke import run_research_smoke
from alphapilot.data_foundation.warehouse import WarehouseLayout

from .backtest import run_backtest_workflow
from .bounded_optimization_service import (
    process_bounded_optimization_result,
    recover_terminal_optimization_results,
)
from .bootstrap import (
    register_evidence_redesigned_short_cycle_candidate_pack,
    register_redesigned_short_cycle_candidate_pack,
    register_alpha191_observer,
    register_optimized_legacy_strategy,
    register_short_cycle_candidate_pack,
    register_v13_27_17_event_window_candidate_pack,
    register_v13_27_18_cross_timeframe_candidate_pack,
)
from .dual_layer import resolve_code_commit, run_dual_layer_backtest_workflow
from .local_forward_bridge import run_local_forward_cycle
from .local_formal_migration import migrate_active_backtests_to_local_formal
from .data_contract import derive_strategy_data_contract
from .projection import build_workflow_projection
from .repository import WorkflowRepository
from .service import (
    archive_strategy_version,
    cancel_workflow_run,
    create_challenger_version,
    create_next_stage_run,
    pause_workflow_run,
    queue_workflow_run,
    retry_workflow_run,
    retry_backtest_for_data_preparation,
    yield_workflow_run,
)
from .structural_redesign_service import (
    process_structural_redesign_result,
    recover_terminal_structural_redesigns,
)
from .states import WorkflowConflict, WorkflowError, WorkflowTransitionError
from .worker_lock import workflow_batch_lock, workflow_worker_lock


APPROVED_WAREHOUSE_ROOT = Path(r"D:\Codex-Workspace\回测数据")
MAX_AUTOMATIC_OPERATIONAL_ATTEMPTS = 3


def _json_object(value: str, field_name: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as error:
        raise argparse.ArgumentTypeError(f"{field_name} must be valid JSON") from error
    if not isinstance(parsed, dict):
        raise argparse.ArgumentTypeError(f"{field_name} must be a JSON object")
    return parsed


def _run_dual_layer_once(
    workflow: WorkflowRepository,
    registry: RegistryRepository,
    workflow_run_id: str,
    *,
    warehouse_root: Path | str,
    output_root: Path | str,
    queue_before_run: bool = False,
    stop_after_phase: str | None = None,
):
    wait_seconds = 120.0 if queue_before_run else 0.0
    with workflow_worker_lock(
        output_root,
        workflow_run_id,
        wait_seconds=wait_seconds,
    ) as acquired:
        if not acquired:
            current = workflow.get_workflow_run(workflow_run_id)
            if current is None:
                raise WorkflowError(f"workflow_run_missing:{workflow_run_id}")
            return current
        if queue_before_run:
            current = workflow.get_workflow_run(workflow_run_id)
            if current is None:
                raise WorkflowError(f"workflow_run_missing:{workflow_run_id}")
            if current.status in {"awaiting", "paused"}:
                queue_workflow_run(
                    workflow, current.workflowRunId, actor="user"
                )
        return run_dual_layer_backtest_workflow(
            workflow,
            registry,
            workflow_run_id,
            warehouse_root=warehouse_root,
            output_root=output_root,
            stop_after_phase=stop_after_phase,
        )


def _prepare_dual_layer_once(
    workflow: WorkflowRepository,
    registry: RegistryRepository,
    workflow_run_id: str,
    *,
    warehouse_root: Path | str,
    output_root: Path | str,
):
    return _run_dual_layer_once(
        workflow,
        registry,
        workflow_run_id,
        warehouse_root=warehouse_root,
        output_root=output_root,
        stop_after_phase="validating_official_data",
    )


def _registry_path(workflow: WorkflowRepository) -> Path:
    for row in workflow.connection.execute("PRAGMA database_list").fetchall():
        if str(row[1]) == "main" and str(row[2]).strip():
            return Path(str(row[2])).resolve()
    raise WorkflowError("workflow_registry_path_unavailable")


def _prepare_backtest_in_fresh_connection(
    *,
    registry_path: Path | str,
    workflow_run_id: str,
    warehouse_root: Path | str,
    output_root: Path | str,
) -> None:
    connection = connect_registry(registry_path, initialize=False)
    try:
        _prepare_dual_layer_once(
            WorkflowRepository(connection),
            RegistryRepository(connection),
            workflow_run_id,
            warehouse_root=warehouse_root,
            output_root=output_root,
        )
        _return_prefetched_run_to_queue(
            WorkflowRepository(connection),
            workflow_run_id,
        )
    finally:
        connection.close()


def _prioritize_backtest_runs(runs: Sequence[Any]) -> list[Any]:
    def completed_phase_count(run: Any) -> int:
        progress = run.progress if isinstance(run.progress, dict) else {}
        completed_phases = progress.get("completedPhases")
        return len(completed_phases) if isinstance(completed_phases, list) else 0

    return sorted(runs, key=completed_phase_count, reverse=True)


def _requires_data_prefetch(run: Any) -> bool:
    progress = run.progress if isinstance(run.progress, dict) else {}
    completed_phases = set(progress.get("completedPhases") or [])
    return "validating_official_data" not in completed_phases


def _return_prefetched_run_to_queue(
    workflow: WorkflowRepository,
    workflow_run_id: str,
):
    current = workflow.get_workflow_run(workflow_run_id)
    if current is None:
        raise WorkflowError(f"workflow_run_missing:{workflow_run_id}")
    completed_phases = set((current.progress or {}).get("completedPhases") or [])
    if (
        current.status != "running"
        or "validating_official_data" not in completed_phases
    ):
        return current
    try:
        return yield_workflow_run(workflow, workflow_run_id, actor="worker")
    except (WorkflowConflict, WorkflowTransitionError):
        latest = workflow.get_workflow_run(workflow_run_id)
        if latest is not None and latest.status in {"paused", "cancelled", "queued"}:
            return latest
        raise


def _run_selected_backtests(
    workflow: WorkflowRepository,
    registry: RegistryRepository,
    workflow_run_ids: Sequence[str],
    *,
    warehouse_root: Path | str,
    output_root: Path | str,
) -> dict[str, Any]:
    run_ids = [str(value).strip() for value in workflow_run_ids]
    if not run_ids or any(not value for value in run_ids):
        raise WorkflowError("selected_backtest_run_ids_required")
    if len(set(run_ids)) != len(run_ids):
        raise WorkflowError("selected_backtest_run_ids_must_be_unique")
    validated_runs = []
    for run_id in run_ids:
        run = workflow.get_workflow_run(run_id)
        if run is None:
            raise WorkflowError(f"selected_backtest_run_missing:{run_id}")
        if run.stage != "backtest" or run.status not in {
            "awaiting",
            "paused",
            "queued",
            "running",
        }:
            raise WorkflowError(
                f"selected_backtest_run_not_eligible:{run_id}:{run.stage}:{run.status}"
            )
        validated_runs.append(run)

    queued_runs = _prioritize_backtest_runs(
        [
            queue_workflow_run(workflow, run.workflowRunId, actor="user")
            if run.status in {"awaiting", "paused"}
            else run
            for run in validated_runs
        ]
    )
    with workflow_batch_lock(output_root) as batch_acquired:
        if not batch_acquired:
            return {
                "processedCount": 0,
                "workflowRunIds": run_ids,
                "runs": [],
                "batchAlreadyRunning": True,
            }
        registry_path = _registry_path(workflow)
        recover_terminal_optimization_results(workflow, registry)
        recover_terminal_structural_redesigns(
            workflow,
            registry,
            registry_path=registry_path,
        )
        pending = list(queued_runs)
        pending_ids = {run.workflowRunId for run in pending}
        for candidate in workflow.list_workflow_runs(
            stage="backtest",
            status="queued",
        ):
            if candidate.workflowRunId not in pending_ids:
                pending.append(candidate)
                pending_ids.add(candidate.workflowRunId)
        pending = _prioritize_backtest_runs(pending)
        processed_ids: set[str] = set()
        processed_order: list[str] = []
        completed: list[dict[str, Any]] = []
        prefetch_futures: dict[str, Future[None]] = {}
        with ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="alphapilot-data-prefetch",
        ) as prefetch_executor:
            def schedule_pending_prefetches() -> None:
                for candidate in pending:
                    candidate_id = candidate.workflowRunId
                    if (
                        candidate_id in processed_ids
                        or candidate_id in prefetch_futures
                        or not _requires_data_prefetch(candidate)
                    ):
                        continue
                    prefetch_futures[candidate_id] = prefetch_executor.submit(
                        _prepare_backtest_in_fresh_connection,
                        registry_path=registry_path,
                        workflow_run_id=candidate_id,
                        warehouse_root=warehouse_root,
                        output_root=output_root,
                    )

            while pending:
                queued = pending.pop(0)
                pending_ids.discard(queued.workflowRunId)
                if queued.workflowRunId in processed_ids:
                    continue
                processed_ids.add(queued.workflowRunId)
                processed_order.append(queued.workflowRunId)

                prefetch_future = prefetch_futures.pop(
                    queued.workflowRunId,
                    None,
                )
                if prefetch_future is not None:
                    prefetch_future.result()
                else:
                    _prepare_dual_layer_once(
                        workflow,
                        registry,
                        queued.workflowRunId,
                        warehouse_root=warehouse_root,
                        output_root=output_root,
                    )

                schedule_pending_prefetches()

                finished = _run_dual_layer_once(
                    workflow,
                    registry,
                    queued.workflowRunId,
                    warehouse_root=warehouse_root,
                    output_root=output_root,
                )
                completed.append(asdict(finished))
                if finished.status in {"passed", "failed", "blocked"}:
                    bounded = process_bounded_optimization_result(
                        workflow,
                        registry,
                        finished,
                    )
                    if bounded.decision.terminalStatus == "structural_redesign_required":
                        process_structural_redesign_result(
                            workflow,
                            registry,
                            finished,
                        )
                    if (
                        finished.status == "blocked"
                        and finished.attemptNumber < MAX_AUTOMATIC_OPERATIONAL_ATTEMPTS
                    ):
                        try:
                            retry = retry_backtest_for_data_preparation(
                                workflow,
                                finished.workflowRunId,
                                actor="system",
                            )
                        except WorkflowTransitionError:
                            retry = None
                        if (
                            retry is not None
                            and retry.workflowRunId not in processed_ids
                            and retry.workflowRunId not in pending_ids
                        ):
                            pending.append(retry)
                            pending_ids.add(retry.workflowRunId)
                for candidate in workflow.list_workflow_runs(
                    stage="backtest",
                    status="queued",
                ):
                    if (
                        candidate.workflowRunId not in processed_ids
                        and candidate.workflowRunId not in pending_ids
                    ):
                        pending.append(candidate)
                        pending_ids.add(candidate.workflowRunId)
                schedule_pending_prefetches()
        return {
            "processedCount": len(completed),
            "workflowRunIds": run_ids,
            "drainedWorkflowRunIds": processed_order,
            "runs": completed,
            "batchAlreadyRunning": False,
            "dataPrefetchEnabled": True,
            "formalWorkerCount": 1,
            "dataPrefetchWorkerCount": 1,
        }


def _run_local_forward_once(
    workflow: WorkflowRepository,
    registry: RegistryRepository,
    workflow_run_id: str,
    *,
    output_root: Path | str,
):
    with workflow_worker_lock(output_root, workflow_run_id) as acquired:
        if not acquired:
            current = workflow.get_workflow_run(workflow_run_id)
            if current is None:
                raise WorkflowError(f"workflow_run_missing:{workflow_run_id}")
            return current
        return run_local_forward_cycle(
            workflow,
            registry,
            workflow_run_id,
            code_commit=resolve_code_commit(),
            market_data=OkxForwardPublicMarket(),
        )


def _run_selected_forward_cycles(
    workflow: WorkflowRepository,
    registry: RegistryRepository,
    workflow_run_ids: Sequence[str],
    *,
    output_root: Path | str,
) -> dict[str, Any]:
    run_ids = [str(value).strip() for value in workflow_run_ids]
    if not run_ids or any(not value for value in run_ids):
        raise WorkflowError("selected_forward_run_ids_required")
    if len(set(run_ids)) != len(run_ids):
        raise WorkflowError("selected_forward_run_ids_must_be_unique")
    for run_id in run_ids:
        run = workflow.get_workflow_run(run_id)
        if run is None:
            raise WorkflowError(f"selected_forward_run_missing:{run_id}")
        if run.stage != "local_forward" or run.status != "running":
            raise WorkflowError(
                f"selected_forward_run_not_eligible:{run_id}:{run.stage}:{run.status}"
            )

    completed = [
        asdict(
            _run_local_forward_once(
                workflow,
                registry,
                run_id,
                output_root=output_root,
            )
        )
        for run_id in run_ids
    ]
    return {
        "processedCount": len(completed),
        "workflowRunIds": run_ids,
        "runs": completed,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AlphaPilot workflow orchestrator")
    parser.add_argument("--registry", default="data/evolution_registry.sqlite")
    parser.add_argument("--output-root", default="data/workflow/backtests")
    parser.add_argument("--warehouse-root", default=str(APPROVED_WAREHOUSE_ROOT))
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("bootstrap")
    commands.add_parser("bootstrap-short-cycle")
    commands.add_parser("bootstrap-redesigned-short-cycle")
    commands.add_parser("bootstrap-evidence-redesigned-short-cycle")
    commands.add_parser("bootstrap-v13-27-17-event-window")
    commands.add_parser("bootstrap-v13-27-18-cross-timeframe")
    commands.add_parser("projection")
    resolve_backtest = commands.add_parser("resolve-backtest-run")
    resolve_backtest.add_argument("--strategy-name")

    for command in ("queue", "run", "recover", "pause", "cancel", "retry"):
        child = commands.add_parser(command)
        child.add_argument("--run-id", required=True)
    one_click = commands.add_parser("one-click-backtest")
    one_click.add_argument("--run-id", required=True)
    smoke = commands.add_parser("research-smoke")
    smoke.add_argument("--run-id", required=True)

    archive = commands.add_parser("archive")
    archive.add_argument("--strategy-version-id", required=True)
    advance = commands.add_parser("advance")
    advance.add_argument("--strategy-version-id", required=True)
    commands.add_parser("run-all-awaiting")
    selected_backtests = commands.add_parser("run-selected-backtests")
    selected_backtests.add_argument("--run-id", action="append", required=True)
    selected_forward = commands.add_parser("run-selected-forward-cycles")
    selected_forward.add_argument("--run-id", action="append", required=True)
    recover_optimizations = commands.add_parser(
        "recover-bounded-optimizations"
    )
    recover_optimizations.add_argument(
        "--strategy-version-id",
        action="append",
    )
    recover_structural = commands.add_parser(
        "recover-structural-redesigns"
    )
    recover_structural.add_argument(
        "--strategy-version-id",
        action="append",
    )
    migrate_local_formal = commands.add_parser("migrate-local-formal")
    migrate_local_formal.add_argument(
        "--strategy-version-id",
        action="append",
    )

    challenger = commands.add_parser("challenger")
    challenger.add_argument("--parent-version-id", required=True)
    challenger.add_argument("--display-name", required=True)
    challenger.add_argument("--source-type", default="manual_challenger")
    challenger.add_argument("--definition-json", required=True)
    challenger.add_argument("--parameters-json", required=True)
    legacy_optimized = commands.add_parser("import-optimized")
    legacy_optimized.add_argument("--legacy-strategy-id", required=True)
    legacy_optimized.add_argument("--display-name", required=True)
    legacy_optimized.add_argument(
        "--source-type", default="legacy_stage_optimization"
    )
    legacy_optimized.add_argument("--definition-json", required=True)
    legacy_optimized.add_argument("--base-parameters-json", required=True)
    legacy_optimized.add_argument("--parameters-json", required=True)
    return parser


def _execute(args: argparse.Namespace) -> dict[str, Any]:
    connection = connect_registry(Path(args.registry))
    try:
        registry = RegistryRepository(connection)
        workflow = WorkflowRepository(connection)
        if args.command == "bootstrap":
            return asdict(register_alpha191_observer(registry, workflow))
        if args.command == "bootstrap-short-cycle":
            versions = register_short_cycle_candidate_pack(registry, workflow)
            return {
                "count": len(versions),
                "strategyVersionIds": [
                    version.strategyVersionId for version in versions
                ],
                "displayNames": [version.displayName for version in versions],
            }
        if args.command == "bootstrap-redesigned-short-cycle":
            versions = register_redesigned_short_cycle_candidate_pack(
                registry, workflow
            )
            return {
                "count": len(versions),
                "strategyVersionIds": [
                    version.strategyVersionId for version in versions
                ],
                "displayNames": [version.displayName for version in versions],
            }
        if args.command == "bootstrap-evidence-redesigned-short-cycle":
            versions = register_evidence_redesigned_short_cycle_candidate_pack(
                registry, workflow
            )
            return {
                "count": len(versions),
                "strategyVersionIds": [
                    version.strategyVersionId for version in versions
                ],
                "displayNames": [version.displayName for version in versions],
            }
        if args.command == "bootstrap-v13-27-17-event-window":
            versions = register_v13_27_17_event_window_candidate_pack(
                registry, workflow
            )
            return {
                "count": len(versions),
                "strategyVersionIds": [
                    version.strategyVersionId for version in versions
                ],
                "displayNames": [version.displayName for version in versions],
            }
        if args.command == "bootstrap-v13-27-18-cross-timeframe":
            versions = register_v13_27_18_cross_timeframe_candidate_pack(
                registry, workflow
            )
            return {
                "count": len(versions),
                "strategyVersionIds": [
                    version.strategyVersionId for version in versions
                ],
                "displayNames": [version.displayName for version in versions],
            }
        if args.command == "projection":
            return build_workflow_projection(
                workflow, warehouse_root=args.warehouse_root
            )
        if args.command == "recover-bounded-optimizations":
            return asdict(
                recover_terminal_optimization_results(
                    workflow,
                    registry,
                    strategy_version_ids=args.strategy_version_id,
                )
            )
        if args.command == "recover-structural-redesigns":
            return asdict(
                recover_terminal_structural_redesigns(
                    workflow,
                    registry,
                    registry_path=Path(args.registry),
                    strategy_version_ids=args.strategy_version_id,
                )
            )
        if args.command == "migrate-local-formal":
            return asdict(
                migrate_active_backtests_to_local_formal(
                    workflow,
                    registry,
                    registry_path=Path(args.registry),
                    strategy_version_ids=args.strategy_version_id,
                )
            )
        if args.command == "resolve-backtest-run":
            projection = build_workflow_projection(
                workflow, warehouse_root=args.warehouse_root
            )
            matches = [
                item
                for item in projection["items"]
                if item["stage"] == "backtest"
                and (
                    not args.strategy_name
                    or item["displayName"] == args.strategy_name
                )
            ]
            if not matches:
                raise WorkflowError("matching_backtest_workflow_missing")
            return {"workflowRunId": matches[0]["workflowRunId"]}
        if args.command == "queue":
            return asdict(queue_workflow_run(workflow, args.run_id, actor="user"))
        if args.command == "run":
            return asdict(
                run_backtest_workflow(
                    workflow,
                    registry,
                    args.run_id,
                    output_root=args.output_root,
                )
            )
        if args.command == "recover":
            return asdict(
                _run_dual_layer_once(
                    workflow,
                    registry,
                    args.run_id,
                    warehouse_root=args.warehouse_root,
                    output_root=args.output_root,
                )
            )
        if args.command == "one-click-backtest":
            run = workflow.get_workflow_run(args.run_id)
            if run is None:
                raise WorkflowError(f"workflow_run_missing:{args.run_id}")
            queue_before_run = run.status in {"awaiting", "paused"}
            if run.status == "blocked":
                run = retry_backtest_for_data_preparation(
                    workflow, run.workflowRunId, actor="user"
                )
            elif queue_before_run:
                run = queue_workflow_run(
                    workflow,
                    run.workflowRunId,
                    actor="user",
                )
            with workflow_batch_lock(args.output_root) as batch_acquired:
                if not batch_acquired:
                    return {
                        **asdict(run),
                        "batchAlreadyRunning": True,
                    }
                return {
                    **asdict(
                        _run_dual_layer_once(
                            workflow,
                            registry,
                            run.workflowRunId,
                            warehouse_root=args.warehouse_root,
                            output_root=args.output_root,
                            queue_before_run=queue_before_run,
                        )
                    ),
                    "batchAlreadyRunning": False,
                }
        if args.command == "research-smoke":
            run = workflow.get_workflow_run(args.run_id)
            if run is None:
                raise WorkflowError(f"workflow_run_missing:{args.run_id}")
            version = workflow.get_strategy_version(run.strategyVersionId)
            if version is None:
                raise WorkflowError(
                    f"strategy_version_missing:{run.strategyVersionId}"
                )
            contract = derive_strategy_data_contract(version, workflow)
            layout = WarehouseLayout.from_root(args.warehouse_root)
            return run_research_smoke(
                contract,
                layout,
                Path(args.output_root) / run.workflowRunId / "research-smoke.json",
            )
        if args.command == "pause":
            return asdict(pause_workflow_run(workflow, args.run_id, actor="user"))
        if args.command == "cancel":
            return asdict(cancel_workflow_run(workflow, args.run_id, actor="user"))
        if args.command == "retry":
            return asdict(retry_workflow_run(workflow, args.run_id, actor="user"))
        if args.command == "archive":
            return asdict(
                archive_strategy_version(
                    workflow, args.strategy_version_id, actor="user"
                )
            )
        if args.command == "advance":
            return asdict(
                create_next_stage_run(
                    workflow, args.strategy_version_id, actor="user"
                )
            )
        if args.command == "challenger":
            return asdict(
                create_challenger_version(
                    workflow,
                    parent_strategy_version_id=args.parent_version_id,
                    display_name=args.display_name,
                    source_type=args.source_type,
                    definition=_json_object(args.definition_json, "definition-json"),
                    parameters=_json_object(args.parameters_json, "parameters-json"),
                )
            )
        if args.command == "import-optimized":
            return asdict(
                register_optimized_legacy_strategy(
                    registry,
                    workflow,
                    legacy_strategy_id=args.legacy_strategy_id,
                    display_name=args.display_name,
                    source_type=args.source_type,
                    definition=_json_object(args.definition_json, "definition-json"),
                    base_parameters=_json_object(
                        args.base_parameters_json, "base-parameters-json"
                    ),
                    parameters=_json_object(args.parameters_json, "parameters-json"),
                )
            )
        if args.command == "run-all-awaiting":
            projection = build_workflow_projection(
                workflow, warehouse_root=args.warehouse_root
            )
            run_ids = [
                item["workflowRunId"]
                for item in projection["items"]
                if item["stage"] == "backtest" and item["status"] == "awaiting"
            ]
            if not run_ids:
                return {"processedCount": 0, "workflowRunIds": [], "runs": []}
            return _run_selected_backtests(
                workflow,
                registry,
                run_ids,
                warehouse_root=args.warehouse_root,
                output_root=args.output_root,
            )
        if args.command == "run-selected-backtests":
            return _run_selected_backtests(
                workflow,
                registry,
                args.run_id,
                warehouse_root=args.warehouse_root,
                output_root=args.output_root,
            )
        if args.command == "run-selected-forward-cycles":
            return _run_selected_forward_cycles(
                workflow,
                registry,
                args.run_id,
                output_root=args.output_root,
            )
        raise WorkflowError(f"unsupported_workflow_command:{args.command}")
    finally:
        connection.close()


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        payload = _execute(args)
    except (WorkflowError, ValueError) as error:
        print(
            json.dumps(
                {"status": "error", "error": str(error)},
                ensure_ascii=False,
                indent=2,
            )
        )
        return 2
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
