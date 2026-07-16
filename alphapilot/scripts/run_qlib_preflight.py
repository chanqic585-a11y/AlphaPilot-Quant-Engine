"""Plan or execute the V13.27.1.12 Qlib preflight-only gate."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from alphapilot.data_foundation.checkpoint import write_json_atomic
from alphapilot.qlib_adapter.preflight import build_qlib_preflight


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--run", action="store_true")
    return parser


def _plan(repo_root: Path) -> dict[str, Any]:
    return {
        "schemaVersion": "v13_27_1_12_qlib_preflight_plan_v1",
        "mode": "plan_only",
        "repoRoot": str(repo_root),
        "installationAttempted": False,
        "modelCampaignRun": False,
        "writeAttempted": False,
        "runFlagRequired": True,
    }


def _execute(repo_root: Path) -> dict[str, Any]:
    report_root = repo_root / "reports" / "v13_27_1_12"
    pit_path = report_root / "pit_universe_audit.json"
    snapshot_path = report_root / "snapshot_manifest.json"
    environment_path = repo_root / "reports" / "reproducibility" / "environment_manifest.json"
    missing = [str(path) for path in (pit_path, snapshot_path, environment_path) if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Qlib preflight inputs are missing: {missing}")
    pit = _read_json(pit_path)
    snapshot_manifest = _read_json(snapshot_path)
    environment = _read_json(environment_path)
    preflight = build_qlib_preflight(
        c_status=str(pit.get("status") or "unavailable"),
        pit_metrics={
            "medianInvestableContracts": pit.get("medianInvestableContracts", 0),
            "freshHoldoutReady": pit.get("freshHoldoutReady", False),
        },
        snapshot=dict(snapshot_manifest.get("snapshot") or {}),
        environment={
            "dockerDaemonAvailable": bool(environment.get("dockerDaemonAvailable"))
            or bool(environment.get("dockerVersion")),
            "dockerImageAvailable": bool(environment.get("dockerImageAvailable"))
            or bool(environment.get("dockerImageDigest")),
        },
    )
    readiness = {
        "schemaVersion": "v13_27_1_12_qlib_readiness_gate_v1",
        "status": "ready" if preflight["qlibCampaignMayRun"] else "blocked",
        "qlibCampaignMayRun": preflight["qlibCampaignMayRun"],
        "blockers": preflight["blockers"],
        "modelCampaignRun": False,
    }
    write_json_atomic(report_root / "qlib_preflight.json", preflight)
    write_json_atomic(report_root / "qlib_readiness_gate.json", readiness)
    return {"mode": "run", **preflight}


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    repo_root = args.repo_root.resolve()
    result = _execute(repo_root) if args.run else _plan(repo_root)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
