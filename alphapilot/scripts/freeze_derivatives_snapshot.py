"""Plan or freeze the audited V13.27.1.12 data-only snapshot."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from alphapilot.data_foundation.checkpoint import write_json_atomic
from alphapilot.derivatives_data.snapshot_freezer import freeze_data_snapshot


REQUIRED_REPORTS = {
    "apiCapability": "api_capability_audit.json",
    "dataQuality": "data_quality_by_instrument.json",
    "pitUniverse": "pit_universe_audit.json",
    "familyReadiness": "family_b_data_chain.json",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--git-commit", default="unknown")
    parser.add_argument("--environment-hash", default="unavailable")
    parser.add_argument("--created-at", default="2026-07-16T00:00:00Z")
    parser.add_argument("--run", action="store_true")
    return parser


def _plan(repo_root: Path) -> dict[str, Any]:
    return {
        "schemaVersion": "v13_27_1_12_snapshot_freeze_plan_v1",
        "mode": "plan_only",
        "repoRoot": str(repo_root),
        "requiredReports": sorted(REQUIRED_REPORTS.values()),
        "writeAttempted": False,
        "runFlagRequired": True,
        "containsStrategyResults": False,
        "containsHoldoutResults": False,
    }


def _execute(
    repo_root: Path,
    *,
    git_commit: str,
    environment_hash: str,
    created_at: str,
) -> dict[str, Any]:
    report_root = repo_root / "reports" / "v13_27_1_12"
    paths = {name: report_root / filename for name, filename in REQUIRED_REPORTS.items()}
    missing = [str(path) for path in paths.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"required audits are missing: {missing}")
    quality_rows = _read_json(paths["dataQuality"])
    pit_manifest_path = report_root / "pit_universe_manifest.json"
    pit_manifest_hash = _sha256(pit_manifest_path) if pit_manifest_path.is_file() else None
    audits = {
        "createdAt": created_at,
        "auditStatuses": {name: "completed" for name in REQUIRED_REPORTS},
        "sourceManifestHashes": [f"sha256:{_sha256(paths['apiCapability'])}"],
        "normalizedHashes": sorted(
            {
                str(row["contentHash"])
                for row in quality_rows
                if isinstance(row, dict) and row.get("contentHash")
            }
        ),
        "derivedHashes": [f"sha256:{pit_manifest_hash}"] if pit_manifest_hash else [],
        "pitHash": f"sha256:{pit_manifest_hash}" if pit_manifest_hash else None,
        "familyReadiness": {
            "B": _read_json(paths["familyReadiness"]),
            "C": _read_json(paths["pitUniverse"]),
        },
    }
    snapshot = freeze_data_snapshot(
        audits=audits,
        output_root=repo_root / "research" / "data_snapshots",
        git_commit=git_commit,
        environment_hash=environment_hash,
    )
    manifest = {
        "schemaVersion": "v13_27_1_12_snapshot_manifest_v1",
        "status": "frozen_data_only",
        "snapshotPath": str(
            repo_root / "research" / "data_snapshots" / f"{snapshot['snapshotId']}.json"
        ),
        "snapshot": snapshot,
        "strategyTrialCount": 0,
        "holdoutAccessCount": 0,
    }
    write_json_atomic(report_root / "snapshot_manifest.json", manifest)
    return {
        "schemaVersion": "v13_27_1_12_snapshot_freeze_result_v1",
        "mode": "run",
        "status": manifest["status"],
        "snapshotId": snapshot["snapshotId"],
        "snapshotHash": snapshot["snapshotHash"],
        "containsStrategyResults": False,
        "containsHoldoutResults": False,
    }


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    repo_root = args.repo_root.resolve()
    result = (
        _execute(
            repo_root,
            git_commit=args.git_commit,
            environment_hash=args.environment_hash,
            created_at=args.created_at,
        )
        if args.run
        else _plan(repo_root)
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
