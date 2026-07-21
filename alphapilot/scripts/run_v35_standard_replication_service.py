"""Run the bounded V35 research service without execution credentials."""

from __future__ import annotations

import argparse
import json
import os
import socket
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from alphapilot.research_service import (
    ResearchService,
    ResearchServicePolicy,
    ResearchServiceStateStore,
    ResearchWorkerBoundary,
)
from alphapilot.research_factory.program_v33 import record_v35_research_cycle
from alphapilot.standard_replication import (
    ReplicationPlanExecutor,
    ReplicationSourceRegistry,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--state-root",
        type=Path,
        default=Path("reports/background_research/v35"),
    )
    parser.add_argument("--enqueue-default", action="store_true")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--interval-seconds", type=float, default=300.0)
    parser.add_argument("--max-cycles", type=int, default=0)
    parser.add_argument("--program-root", type=Path)
    parser.add_argument("--now")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    worker_boundary = ResearchWorkerBoundary.default()
    worker_boundary.enforce_current_process_environment()
    repo_root = args.repo_root.resolve()
    state_root = args.state_root.resolve()
    registry = ReplicationSourceRegistry.load(
        repo_root
        / "research"
        / "source_registry"
        / "strategy_research_source_registry.json"
    )
    policy = ResearchServicePolicy.default()
    state_store = ResearchServiceStateStore(
        state_root / "state.json",
        policy=policy,
    )
    executor = ReplicationPlanExecutor(
        registry=registry,
        output_root=state_root / "campaigns",
    )
    service = ResearchService(
        policy=policy,
        state_store=state_store,
        executor=executor,
        lease_path=state_root / "service.lease.json",
        receipt_path=state_root / "receipts.jsonl",
        owner=f"{socket.gethostname()}:{os.getpid()}",
        pause_file=state_root / "PAUSE",
        worker_boundary=worker_boundary,
    )

    initial_now = str(args.now or _utc_now())
    state = state_store.load_or_initialize(now=initial_now)
    if args.enqueue_default and not state["jobs"]:
        service.enqueue(
            campaign_id="v35-standard-replication-default",
            family_ids=registry.family_ids,
            candidate_ids=tuple(
                variant.candidate_id
                for family in registry.items
                for variant in family.variants
            ),
            queued_at=initial_now,
        )

    cycle_count = 0
    while True:
        cycle_now = str(args.now or _utc_now())
        result = service.run_cycle(now=cycle_now)
        if args.program_root and result.get("status") in {
            "ready_for_prefilter",
            "prefilter_failed",
            "formal_failed",
            "waiting_exact_release_approval",
        }:
            record_v35_research_cycle(
                program_root=args.program_root.resolve(),
                cycle_result=result,
                created_at=cycle_now,
                writer_id=f"v35-research-service:{socket.gethostname()}:{os.getpid()}",
            )
        state = state_store.load_or_initialize(now=cycle_now)
        health = {
            "schemaVersion": "v35_research_service_health_v1",
            "checkedAt": cycle_now,
            "serviceStatus": result["status"],
            "campaignCount": len(state["jobs"]),
            "policyHash": policy.policy_hash,
            "campaignId": result.get("campaignId"),
            "campaignHash": result.get("campaignHash"),
            "artifactPath": result.get("artifactPath"),
            "candidateCount": int(result.get("candidateCount") or 0),
            "blockedFamilyCount": int(
                result.get("blockedFamilyCount") or 0
            ),
            "formalRunCount": int(result.get("formalRunCount") or 0),
            "resultReadCount": int(result.get("resultReadCount") or 0),
            "lockedOosReadCount": int(result.get("lockedOosReadCount") or 0),
            "releaseCount": int(result.get("releaseCount") or 0),
            "demoReleaseCount": 0,
            "approvalCount": 0,
            "demoArm": False,
            "orderCount": 0,
            "tradeApiUsed": False,
            "withdrawApiUsed": False,
            "privateAccountReadUsed": False,
        }
        _write_json_atomic(state_root / "health.json", health)
        cycle_count += 1
        if args.once or (args.max_cycles > 0 and cycle_count >= args.max_cycles):
            return 0
        time.sleep(max(1.0, float(args.interval_seconds)))


if __name__ == "__main__":
    raise SystemExit(main())
