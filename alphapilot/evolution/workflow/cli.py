"""Command-line boundary for the local workflow orchestrator."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Sequence

from alphapilot.evolution.registry.database import connect_registry
from alphapilot.evolution.registry.repositories import RegistryRepository
from alphapilot.data_foundation.research_smoke import run_research_smoke
from alphapilot.data_foundation.warehouse import WarehouseLayout

from .backtest import run_backtest_workflow
from .bootstrap import register_alpha191_observer, register_optimized_legacy_strategy
from .dual_layer import run_dual_layer_backtest_workflow
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
)
from .states import WorkflowError
from .worker_lock import workflow_worker_lock


APPROVED_WAREHOUSE_ROOT = Path(r"D:\Codex-Workspace\回测数据")


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
):
    with workflow_worker_lock(output_root, workflow_run_id) as acquired:
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
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AlphaPilot workflow orchestrator")
    parser.add_argument("--registry", default="data/evolution_registry.sqlite")
    parser.add_argument("--output-root", default="data/workflow/backtests")
    parser.add_argument("--warehouse-root", default=str(APPROVED_WAREHOUSE_ROOT))
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("bootstrap")
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
        if args.command == "projection":
            return build_workflow_projection(workflow)
        if args.command == "resolve-backtest-run":
            projection = build_workflow_projection(workflow)
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
            return asdict(
                _run_dual_layer_once(
                    workflow,
                    registry,
                    run.workflowRunId,
                    warehouse_root=args.warehouse_root,
                    output_root=args.output_root,
                    queue_before_run=queue_before_run,
                )
            )
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
            completed: list[dict[str, Any]] = []
            projection = build_workflow_projection(workflow)
            for item in projection["items"]:
                if item["stage"] != "backtest" or item["status"] != "awaiting":
                    continue
                queued = queue_workflow_run(
                    workflow, item["workflowRunId"], actor="user"
                )
                completed.append(
                    asdict(
                        _run_dual_layer_once(
                            workflow,
                            registry,
                            queued.workflowRunId,
                            warehouse_root=args.warehouse_root,
                            output_root=args.output_root,
                        )
                    )
                )
            return {"processedCount": len(completed), "runs": completed}
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
