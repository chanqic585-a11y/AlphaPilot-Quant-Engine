"""Generate immutable Live candidate artifacts without enabling live execution."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from alphapilot.evolution.registry.database import DEFAULT_REGISTRY_PATH, connect_registry
from alphapilot.evolution.registry.repositories import RegistryRepository


DEFAULT_OUTPUT = Path("reports/live_candidate_boundary_report.json")
DEFAULT_SUMMARY = Path("reports/live_candidate_boundary_summary.md")


def _export_package(record: Any) -> dict[str, Any]:
    return {
        "schemaVersion": "alphapilot_live_candidate_review_v1",
        "liveCandidatePackageId": record.liveCandidatePackageId,
        "demoReleaseId": record.demoReleaseId,
        "status": record.status,
        "packageHash": record.contentHash,
        "createdAt": record.createdAt,
        "package": record.package,
        "approvalBoundary": {
            "manualApprovalRequired": True,
            "automaticApprovalAllowed": False,
            "approvalEnablesExecution": False,
            "liveExecutionAdapterPresent": False,
            "withdrawAllowed": False,
        },
    }


def build_report(registry_path: Path) -> dict[str, Any]:
    connection = connect_registry(registry_path)
    try:
        packages = RegistryRepository(connection).list_live_candidate_packages()
    finally:
        connection.close()
    exports = [_export_package(record) for record in packages]
    return {
        "version": "V13.15.0",
        "source": "live_candidate_boundary_report_v1",
        "generatedAt": datetime.now(UTC).isoformat(),
        "status": "awaiting_manual_review" if packages else "blocked",
        "summary": {
            "liveCandidatePackageCount": len(packages),
            "awaitingManualApprovalCount": sum(record.status == "awaiting_manual_approval" for record in packages),
            "automaticApprovalCount": 0,
            "liveExecutionAdapterCount": 0,
        },
        "packages": exports,
        "blockers": [] if packages else ["no_demo_release_has_completed_live_candidate_validation"],
        "safetyBoundary": {
            "automaticLivePromotionAllowed": False,
            "aiApprovalAllowed": False,
            "banditApprovalAllowed": False,
            "mlApprovalAllowed": False,
            "approvalEnablesExecution": False,
            "liveExecutionAdapterPresent": False,
            "withdrawAllowed": False,
        },
    }


def write_outputs(report: dict[str, Any], output: Path, summary: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    summary.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for export in report.get("packages", []):
        package_id = str(export.get("liveCandidatePackageId") or "").strip()
        if package_id:
            path = output.parent / f"live_candidate_package_{package_id}.json"
            path.write_text(json.dumps(export, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    values = report["summary"]
    summary.write_text(
        "\n".join(
            [
                "# V13.15.0 Live Candidate Boundary",
                "",
                f"- Status: `{report['status']}`",
                f"- Live candidate packages: {values['liveCandidatePackageCount']}",
                f"- Awaiting manual approval: {values['awaitingManualApprovalCount']}",
                "- Automatic approvals: 0",
                "- Live execution adapters: 0",
                "- Approval records do not enable execution.",
                "- Withdraw remains disabled.",
                "",
            ]
        ),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    args = parser.parse_args()
    report = build_report(args.registry)
    write_outputs(report, args.output, args.summary)
    print(json.dumps(report["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
