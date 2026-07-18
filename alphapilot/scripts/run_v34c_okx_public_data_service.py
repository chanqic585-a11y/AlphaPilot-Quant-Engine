"""Run one or more bounded V34C OKX public-data collection cycles."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import socket
import time
from typing import Any, Callable

from alphapilot.data_foundation.okx_official_v1 import OkxOfficialV1Layout
from alphapilot.data_foundation.okx_official_v1_incremental import (
    OkxOfficialV1IncrementalCollector,
)
from alphapilot.data_foundation.okx_official_v1_quality_monitor import (
    OkxOfficialV1QualityMonitor,
)
from alphapilot.data_foundation.okx_official_v1_schedule import (
    OkxPublicCollectionPolicy,
    SchedulerStateStore,
)
from alphapilot.data_foundation.okx_official_v1_service import (
    OkxOfficialV1PublicDataService,
)
from alphapilot.data_foundation.okx_public import OkxPublicClient


DEFAULT_WAREHOUSE_ROOT = Path("D:/Codex-Workspace") / "回测数据"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--warehouse-root", type=Path, default=DEFAULT_WAREHOUSE_ROOT)
    parser.add_argument("--program-root", type=Path, required=True)
    parser.add_argument("--base-snapshot-id", required=True)
    parser.add_argument(
        "--instruments",
        default="BTC-USDT-SWAP,ETH-USDT-SWAP,SOL-USDT-SWAP",
    )
    parser.add_argument("--mode", choices=("once", "loop"), default="once")
    parser.add_argument("--sleep-seconds", type=float, default=30.0)
    parser.add_argument("--max-cycles", type=int)
    parser.add_argument("--pause-file", type=Path)
    return parser


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def build_service(args: argparse.Namespace) -> OkxOfficialV1PublicDataService:
    program_root = Path(args.program_root).resolve()
    summary_path = program_root / "program_summary.json"
    if not summary_path.is_file():
        raise FileNotFoundError("v33_program_summary_missing")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    base_snapshot_id = str(args.base_snapshot_id).strip()
    if summary.get("dataSnapshotId") != base_snapshot_id:
        raise ValueError("v34c_base_snapshot_identity_mismatch")
    instruments = tuple(
        value.strip()
        for value in str(args.instruments).split(",")
        if value.strip()
    )
    policy = OkxPublicCollectionPolicy.default(instruments=instruments)
    layout = OkxOfficialV1Layout.from_warehouse(args.warehouse_root)
    layout.ensure_directories()
    state_store = SchedulerStateStore(
        layout.checkpointRoot / "v34c" / f"scheduler-{policy.policy_hash}.json",
        policy=policy,
    )
    collector = OkxOfficialV1IncrementalCollector(
        warehouse_root=args.warehouse_root,
        client=OkxPublicClient(),
        instruments=instruments,
    )
    quality_monitor = OkxOfficialV1QualityMonitor(
        warehouse_root=args.warehouse_root,
        policy=policy,
        state_store=state_store,
    )
    pause_file = args.pause_file or layout.checkpointRoot / "V34C_PAUSE_REQUESTED"
    return OkxOfficialV1PublicDataService(
        policy=policy,
        state_store=state_store,
        collector=collector,
        quality_monitor=quality_monitor,
        lease_path=layout.checkpointRoot / "v34c" / "public-data-service.lock",
        cycle_ledger_path=layout.manifestRoot / "v34c" / "cycle_ledger.jsonl",
        owner=f"{socket.gethostname()}:{os.getpid()}",
        pause_file=pause_file,
    )


def run_service(
    service: OkxOfficialV1PublicDataService,
    *,
    mode: str,
    sleep_seconds: float,
    max_cycles: int | None,
    now_provider: Callable[[], str] = _now,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> list[dict[str, Any]]:
    if mode not in {"once", "loop"}:
        raise ValueError(f"unsupported_v34c_service_mode:{mode}")
    if sleep_seconds < 0:
        raise ValueError("sleep_seconds_must_not_be_negative")
    if max_cycles is not None and max_cycles <= 0:
        raise ValueError("max_cycles_must_be_positive")
    cycle_limit = 1 if mode == "once" else max_cycles
    results: list[dict[str, Any]] = []
    try:
        while cycle_limit is None or len(results) < cycle_limit:
            results.append(service.run_due_cycle(now=now_provider()))
            if cycle_limit is not None and len(results) >= cycle_limit:
                break
            sleep_fn(sleep_seconds)
    except KeyboardInterrupt:
        results.append(service.record_operator_stop(now=now_provider()))
    return results


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    service = build_service(args)
    results = run_service(
        service,
        mode=args.mode,
        sleep_seconds=args.sleep_seconds,
        max_cycles=args.max_cycles,
    )
    print(json.dumps(results, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
