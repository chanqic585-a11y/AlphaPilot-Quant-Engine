"""Build checksum-bound Live review candidates while execution remains absent."""

from __future__ import annotations

import argparse
import json
from dataclasses import fields
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from alphapilot.data_foundation.checkpoint import write_json_atomic
from alphapilot.evolution.promotion.live_candidate import (
    DemoValidationEvidence,
    LiveCandidateNotEligible,
    LiveRiskBudgetProposal,
    build_live_candidate_package,
)
from alphapilot.evolution.registry.database import connect_registry
from alphapilot.evolution.registry.repositories import RegistryRepository


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _parse_evidence(raw: Any) -> DemoValidationEvidence:
    if not isinstance(raw, dict):
        raise ValueError("demo_validation_evidence_missing")
    required = {item.name for item in fields(DemoValidationEvidence)}
    missing = sorted(required - set(raw))
    if missing:
        raise ValueError("demo_validation_evidence_incomplete:" + ",".join(missing))
    return DemoValidationEvidence(**{key: raw[key] for key in required})


def _export(record: Any) -> dict[str, Any]:
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
            "liveReleaseExecutionApprovalImplemented": False,
            "liveExecutionAdapterPresent": False,
            "withdrawAllowed": False,
        },
    }


def build_v13_21_report(
    *,
    registry_path: str | Path,
    code_commit: str,
    package_directory: str | Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not str(code_commit).strip():
        raise ValueError("V13.21 report requires a code commit")
    directory = Path(package_directory)
    directory.mkdir(parents=True, exist_ok=True)
    connection = connect_registry(registry_path)
    evaluations: list[dict[str, Any]] = []
    exports: list[dict[str, Any]] = []
    try:
        repository = RegistryRepository(connection)
        releases = repository.list_demo_releases()
        for release in releases:
            row: dict[str, Any] = {
                "demoReleaseId": release.demoReleaseId,
                "demoReleaseHash": release.contentHash,
                "strategyCandidateId": release.strategyCandidateId,
                "demoStatus": release.status,
            }
            try:
                if release.status not in {"demo_validated", "demo_completed"}:
                    raise LiveCandidateNotEligible("demo_release_validation_not_completed")
                evidence = _parse_evidence(release.release.get("demoValidationEvidence"))
                rollback_target = str(release.release.get("rollbackTargetDemoReleaseId") or "").strip()
                package = build_live_candidate_package(
                    demoRelease=release,
                    demoEvidence=evidence,
                    proposedRiskBudget=LiveRiskBudgetProposal(),
                    rollbackTargetReleaseId=rollback_target,
                    repository=repository,
                )
                exported = _export(package)
                output_path = directory / f"live_candidate_package_{package.liveCandidatePackageId}.json"
                write_json_atomic(output_path, exported)
                exports.append({**exported, "exportPath": str(output_path.resolve())})
                row.update(
                    {
                        "status": "awaiting_manual_approval",
                        "liveCandidatePackageId": package.liveCandidatePackageId,
                        "packageHash": package.contentHash,
                        "exportPath": str(output_path.resolve()),
                    }
                )
            except (LiveCandidateNotEligible, TypeError, ValueError) as exc:
                row.update({"status": "blocked", "blocker": str(exc)})
            evaluations.append(row)
    finally:
        connection.close()

    if not releases:
        status = "blocked_no_validated_demo_release"
        blockers = ["no_demo_release", "no_demo_validation_evidence", "no_live_candidate_package"]
    elif not exports:
        status = "completed_no_live_candidate"
        blockers = ["no_demo_release_passed_all_live_candidate_gates"]
    else:
        status = "live_candidate_review_ready"
        blockers = [
            "manual_live_release_approval_still_required",
            "live_release_execution_approval_not_implemented",
            "live_adapter_absent",
        ]
    report = {
        "reportId": "v13_21_live_safety_candidate_report",
        "version": "V13.21.0",
        "status": status,
        "generatedAt": _utc_now(),
        "codeCommit": str(code_commit),
        "demoReleaseCount": len(releases),
        "liveCandidatePackageCount": len(exports),
        "releaseEvaluations": evaluations,
        "packages": exports,
        "blockers": blockers,
        "fixedRiskBudget": {
            "capitalLimitUsdt": 1000.0,
            "riskPerTradePercent": 0.25,
            "maxOpenRiskPercent": 1.0,
            "maxOrderNotionalUsdt": 250.0,
            "maxConcurrentPositions": 3,
            "maxLeverage": 2,
            "dailyLossStopPercent": 2.0,
            "maxDrawdownStopPercent": 5.0,
        },
        "safetyBoundary": {
            "manualApprovalRequired": True,
            "approvalEnablesExecution": False,
            "liveReleaseExecutionApprovalImplemented": False,
            "liveExecutionAdapterPresent": False,
            "liveExecutionEnabled": False,
            "withdrawApiEnabled": False,
            "requestExpiryRequired": True,
            "idempotencyRequired": True,
            "privateStateReconciliationRequired": True,
            "killSwitchRequired": True,
        },
    }
    readiness = {
        "schemaVersion": "live_safety_readiness_contract_v1",
        "stage": "future_live_review_only",
        "status": status,
        "demoReleaseCount": len(releases),
        "liveCandidatePackageCount": len(exports),
        "blockers": blockers,
        "manualApprovalRequired": True,
        "approvalEnablesExecution": False,
        "liveReleaseExecutionApprovalImplemented": False,
        "liveExecutionAdapterPresent": False,
        "liveExecutionEnabled": False,
        "withdrawApiEnabled": False,
    }
    return report, readiness


def _summary(report: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# AlphaPilot V13.21 Live Safety Candidate Summary",
            "",
            f"- Status: `{report['status']}`",
            f"- Demo releases: `{report['demoReleaseCount']}`",
            f"- Live review packages: `{report['liveCandidatePackageCount']}`",
            "- Manual review approval does not enable execution.",
            "- No Live exchange adapter or Withdraw capability exists.",
            "",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", default="data/evolution_registry.sqlite")
    parser.add_argument("--code-commit", required=True)
    parser.add_argument("--package-directory", default="reports")
    parser.add_argument("--report", default="reports/v13_21_live_safety_candidate_report.json")
    parser.add_argument("--contract", default="reports/v13_21_live_safety_readiness_contract.json")
    parser.add_argument("--summary", default="reports/v13_21_live_safety_candidate_summary.md")
    args = parser.parse_args()
    report, readiness = build_v13_21_report(
        registry_path=args.registry,
        code_commit=args.code_commit,
        package_directory=args.package_directory,
    )
    write_json_atomic(Path(args.report), report)
    write_json_atomic(Path(args.contract), readiness)
    Path(args.summary).write_text(_summary(report), encoding="utf-8", newline="\n")
    print(
        json.dumps(
            {
                "reportId": report["reportId"],
                "status": report["status"],
                "demoReleases": report["demoReleaseCount"],
                "liveCandidatePackages": report["liveCandidatePackageCount"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
