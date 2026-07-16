"""Plan or execute a bounded scan before any formal public-data collection."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from alphapilot.data_foundation.checkpoint import write_json_atomic
from alphapilot.derivatives_data.checkpoint_store import scan_existing_partitions


DEFAULT_DOWNLOAD_BUDGET: dict[str, int | float] = {
    "maximumRequestsPerMinute": 60,
    "maximumRetriesPerPage": 3,
    "maximumTotalRequests": 5_000,
    "maximumDownloadBytes": 5 * 1024 * 1024 * 1024,
    "minimumFreeDiskBytes": 20 * 1024 * 1024 * 1024,
    "maximumRunHours": 6,
}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--data-root",
        type=Path,
        default=Path("D:/Codex-Workspace/回测数据"),
    )
    parser.add_argument("--run", action="store_true")
    return parser


def _plan(repo_root: Path, data_root: Path) -> dict[str, Any]:
    return {
        "schemaVersion": "v13_27_1_12_collection_plan_v1",
        "mode": "plan_only",
        "repoRoot": str(repo_root),
        "dataRoot": str(data_root),
        "networkAccessAttempted": False,
        "writeAttempted": False,
        "budget": DEFAULT_DOWNLOAD_BUDGET,
        "policy": {
            "existingDataFirst": True,
            "gapOnlyDownload": True,
            "crossExchangeCoreFieldSplicingAllowed": False,
            "runFlagRequired": True,
        },
    }


def _execute(repo_root: Path, data_root: Path) -> dict[str, Any]:
    output_root = repo_root / "reports" / "v13_27_1_12"
    scan = scan_existing_partitions(data_root / "normalized")
    budget = {
        "schemaVersion": "v13_27_1_12_download_budget_v1",
        **DEFAULT_DOWNLOAD_BUDGET,
        "publicDataOnly": True,
        "preRegisteredBeforeCollection": True,
    }
    resume = {
        "schemaVersion": "v13_27_1_12_download_resume_manifest_v1",
        "status": "existing_data_scanned_no_download",
        "reason": "no_verified_complete_same_exchange_source_chain",
        "networkAccessAttempted": False,
        "networkRequestCount": 0,
        "retryCount": 0,
        "downloadedBytes": 0,
        "resumeCount": 0,
        "existingDataScan": scan,
    }
    deduplication = {
        "schemaVersion": "v13_27_1_12_deduplication_report_v1",
        "status": "not_run_no_new_records",
        "primaryKey": ["exchange", "instrumentId", "dataType", "timestampUtc"],
        "inputRecordCount": 0,
        "outputRecordCount": 0,
        "duplicateRecordCount": 0,
    }
    gap_repair = {
        "schemaVersion": "v13_27_1_12_gap_repair_report_v1",
        "status": "not_run_no_verified_collection_chain",
        "detectedGapCount": 0,
        "repairedGapCount": 0,
        "unresolvedGapCount": 0,
        "existingDataDeleted": False,
    }
    write_json_atomic(output_root / "download_budget.json", budget)
    write_json_atomic(output_root / "download_resume_manifest.json", resume)
    write_json_atomic(output_root / "deduplication_report.json", deduplication)
    write_json_atomic(output_root / "gap_repair_report.json", gap_repair)
    return {
        "schemaVersion": "v13_27_1_12_collection_execution_v1",
        "mode": "run",
        "status": resume["status"],
        "networkRequestCount": 0,
        "existingFormalPartitionCount": scan["formalEligiblePartitionCount"],
        "outputRoot": str(output_root),
    }


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    repo_root = args.repo_root.resolve()
    data_root = args.data_root.resolve()
    result = _execute(repo_root, data_root) if args.run else _plan(repo_root, data_root)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
