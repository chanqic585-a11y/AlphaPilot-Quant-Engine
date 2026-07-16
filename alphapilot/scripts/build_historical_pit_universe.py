"""Plan or build V13.27.1.12 historical PIT and quality reports."""

from __future__ import annotations

import argparse
import csv
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from alphapilot.data_foundation.checkpoint import write_json_atomic
from alphapilot.derivatives_data.historical_pit_reports import build_stage3_reports


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--data-root", type=Path, default=Path("D:/Codex-Workspace/回测数据"))
    parser.add_argument("--checked-at", default="2026-07-16T00:00:00Z")
    parser.add_argument("--run", action="store_true")
    return parser


def _plan(repo_root: Path, data_root: Path) -> dict[str, Any]:
    return {
        "schemaVersion": "v13_27_1_12_pit_build_plan_v1",
        "mode": "plan_only",
        "repoRoot": str(repo_root),
        "dataRoot": str(data_root),
        "networkAccessAttempted": False,
        "writeAttempted": False,
        "currentTopNBackfillAllowed": False,
        "runFlagRequired": True,
    }


def _write_csv(
    path: Path,
    rows: list[dict[str, Any]],
    *,
    fields: list[str] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = fields or sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        if fieldnames:
            writer.writeheader()
            for row in rows:
                writer.writerow(
                    {
                        field: json.dumps(value, ensure_ascii=False, sort_keys=True)
                        if isinstance(value, (dict, list))
                        else value
                        for field, value in ((field, row.get(field)) for field in fieldnames)
                    }
                )


def _execute(repo_root: Path, data_root: Path, checked_at: str) -> dict[str, Any]:
    reports = build_stage3_reports(data_root=data_root, checked_at=checked_at)
    output_root = repo_root / "reports" / "v13_27_1_12"
    write_json_atomic(output_root / "family_b_data_chain.json", reports["familyB"])
    write_json_atomic(output_root / "pit_universe_audit.json", reports["pitAudit"])
    write_json_atomic(output_root / "pit_universe_manifest.json", reports["pitManifest"])
    write_json_atomic(output_root / "pit_universe_coverage.json", reports["pitCoverage"])
    _write_csv(
        output_root / "pit_universe_coverage.csv",
        reports["pitCoverage"],
        fields=[
            "snapshotTimeUtc",
            "eligibleInstrumentCount",
            "researchSymbolCount",
            "holdoutSymbolCount",
            "coverageStatus",
        ],
    )
    write_json_atomic(output_root / "data_quality_by_source.json", reports["qualityBySource"])
    write_json_atomic(
        output_root / "data_quality_by_instrument.json",
        reports["qualityByInstrument"],
    )
    _write_csv(
        output_root / "data_quality_by_instrument.csv",
        reports["qualityByInstrument"],
    )
    return {
        "schemaVersion": "v13_27_1_12_pit_build_result_v1",
        "mode": "run",
        "status": reports["readiness"]["status"],
        "familyBStatus": reports["familyB"]["status"],
        "historicalPitFormalReady": reports["pitAudit"]["historicalFormalReady"],
        "normalizedPartitionCount": len(reports["qualityByInstrument"]),
        "networkAccessAttempted": False,
        "outputRoot": str(output_root),
    }


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    repo_root = args.repo_root.resolve()
    data_root = args.data_root.resolve()
    result = (
        _execute(repo_root, data_root, args.checked_at)
        if args.run
        else _plan(repo_root, data_root)
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
