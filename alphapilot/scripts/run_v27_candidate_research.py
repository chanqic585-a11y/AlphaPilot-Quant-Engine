"""Execute the bounded V27 candidate-research campaign from frozen local data."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import pandas as pd

from alphapilot.data_foundation.checkpoint import write_json_atomic
from alphapilot.research_factory.catalog_frames import load_catalog_window
from alphapilot.research_factory.data_profiles import build_verified_capacity_profile
from alphapilot.research_factory.program_v26 import _manifest
from alphapilot.research_factory.program_v27 import (
    build_v27_data_readiness_receipt,
    build_v27_fixed_universe_semantics_matrix,
    run_v27_candidate_research,
)


DEFAULT_PROGRAM_ID = "automatic_strategy_to_demo_v26_2aff44adf84d039c"
SOURCE_PROGRAM_ID = "automatic_strategy_demo_f57c443abeaf06c0"
PREFILTER_START = "2020-03-11T00:00:00Z"
PREFILTER_END_EXCLUSIVE = "2023-01-01T00:00:00Z"
TIMEFRAMES = ("1h", "4h")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        handle.write("\n")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--program-id", default=DEFAULT_PROGRAM_ID)
    parser.add_argument("--implementation-commit", required=True)
    parser.add_argument(
        "--generated-at",
        default=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    repo = args.repo_root.resolve()
    reports = repo / "reports"
    program_root = reports / "automatic_strategy_to_demo" / args.program_id
    source_root = reports / "automatic_research_program" / SOURCE_PROGRAM_ID
    if not (program_root / "program_state.json").is_file():
        raise FileNotFoundError(program_root / "program_state.json")

    state = _read_json(program_root / "program_state.json")
    if state.get("nextAllowedStage") != "v27_new_candidate_research":
        raise RuntimeError(f"v27_stage_not_allowed:{state.get('nextAllowedStage')}")

    catalog_path = reports / "backtest_screening" / "data_readiness" / "dataset_catalog.json"
    source_matrix_path = source_root / "data_capability_matrix.parquet"
    v25_root = source_root / "v25"
    capacity_capability = _read_json(v25_root / "capacity_data_capability.json")
    volume_audit = _read_json(v25_root / "volume_provenance_audit.json")
    source_matrix = pd.read_parquet(source_matrix_path).to_dict(orient="records")
    window = load_catalog_window(
        catalog_path,
        start=PREFILTER_START,
        end_exclusive=PREFILTER_END_EXCLUSIVE,
        timeframes=TIMEFRAMES,
        verify_hashes=False,
    )

    profiles: dict[str, dict[str, Any]] = {}
    receipts: dict[str, dict[str, Any]] = {}
    semantics: list[dict[str, Any]] = []
    for timeframe in TIMEFRAMES:
        instruments = sorted(window.frames[timeframe])
        profile = build_verified_capacity_profile(
            volume_audit=volume_audit,
            capacity_capability=capacity_capability,
            required_timeframes=[timeframe],
            minimum_history_rows=10_000,
            required_instruments=instruments,
        )
        profiles[timeframe] = profile
        matrix = build_v27_fixed_universe_semantics_matrix(
            timeframe=timeframe,
            source_matrix=source_matrix,
            frames=window.frames[timeframe],
            start=PREFILTER_START,
            end_exclusive=PREFILTER_END_EXCLUSIVE,
        )
        semantics.extend(matrix)
        receipts[timeframe] = build_v27_data_readiness_receipt(
            timeframe=timeframe,
            matrix=matrix,
            capacity_profile=profile,
        )

    summary = run_v27_candidate_research(
        reports_root=reports,
        program_id=args.program_id,
        generated_at=args.generated_at,
        implementation_commit=args.implementation_commit,
        frames=window.frames,
        receipts=receipts,
        capacity_profiles=profiles,
        source_references=[
            "reports/full_archived_strategy_inventory.json",
            f"reports/automatic_research_program/{SOURCE_PROGRAM_ID}/v25/volume_provenance_audit.json",
            f"reports/automatic_strategy_to_demo/{args.program_id}/ranking_semantics_derivation_audit.json",
        ],
        data_access_report=window.access_report,
        candidate_semantics_matrix=semantics,
    )

    state.update(
        {
            "stage": "v27_completed",
            "nextAllowedStage": summary["nextStage"],
            "terminalRoute": (
                summary["nextStage"]
                if summary["nextStage"] == "completed_zero_prefilter_survivors"
                else None
            ),
            "generatedAt": args.generated_at,
            "formalRunCount": 0,
            "resultReadCount": 0,
            "lockedOosReadCount": 0,
            "releaseCount": 0,
            "approvalCount": 0,
            "demoArm": False,
            "orderCount": 0,
        }
    )
    budget = _read_json(program_root / "program_budget.json")
    budget.update(
        {
            "campaignsConsumed": int(budget.get("campaignsConsumed") or 0) + 1,
            "candidateTrialsConsumed": int(budget.get("candidateTrialsConsumed") or 0)
            + int(summary["candidateTrialCount"]),
            "formalAttemptsConsumed": 0,
            "formalClaimsConsumed": 0,
            "formalResultsRead": 0,
            "lockedOosReads": 0,
            "releaseCount": 0,
            "approvalCount": 0,
            "orderCount": 0,
        }
    )
    write_json_atomic(program_root / "program_state.json", state)
    write_json_atomic(program_root / "program_budget.json", budget)
    _append_jsonl(
        program_root / "program_ledger.jsonl",
        {
            "schemaVersion": "automatic_strategy_to_demo_ledger_event_v1",
            "eventType": "v27_candidate_research_completed",
            "createdAt": args.generated_at,
            "programId": args.program_id,
            "stage": state["stage"],
            "nextAllowedStage": state["nextAllowedStage"],
            "summaryHash": summary["summaryHash"],
            "formalRunCount": 0,
            "resultReadCount": 0,
            "lockedOosReadCount": 0,
        },
    )
    _append_jsonl(
        program_root / "program_budget_ledger.jsonl",
        {
            "eventType": "v27_budget_snapshot",
            "createdAt": args.generated_at,
            "budget": budget,
        },
    )
    write_json_atomic(program_root / "artifact_manifest.json", _manifest(program_root))
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
