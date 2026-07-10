"""Generate the V13.26 formal execution outcome feedback report."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from alphapilot.data_foundation.checkpoint import write_json_atomic
from alphapilot.evolution.offline.execution_outcome_importer import (
    import_execution_outcome_export,
)
from alphapilot.evolution.offline.loop import run_offline_evolution_loop
from alphapilot.evolution.registry.database import connect_registry
from alphapilot.evolution.registry.repositories import RegistryRepository


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EXECUTION_OUTCOME_EXPORT = (
    REPO_ROOT.parent
    / "AlphaPilot-Control-Console"
    / "data"
    / "formal_outcome_exports"
    / "latest_execution_outcomes.json"
)


def _release_fingerprints(repository: RegistryRepository) -> dict[str, dict[str, str]]:
    return {
        "forwardReleases": {
            row.forwardReleaseId: row.contentHash for row in repository.list_forward_releases()
        },
        "demoReleases": {
            row.demoReleaseId: row.contentHash for row in repository.list_demo_releases()
        },
        "liveCandidatePackages": {
            row.liveCandidatePackageId: row.contentHash
            for row in repository.list_live_candidate_packages()
        },
        "liveReleases": {
            row.liveReleaseId: row.contentHash for row in repository.list_live_releases()
        },
    }


def _blocked_loop(releases: dict[str, dict[str, str]]) -> dict[str, Any]:
    return {
        "version": "V13.26.0",
        "status": "blocked_no_formal_execution_feedback",
        "maximumLifecycleStage": "shadow_candidate",
        "releaseLineage": {"before": releases, "after": releases, "unchanged": True},
        "safetyBoundary": {
            "offlineOnly": True,
            "onlineModelMutation": False,
            "autoReplacesRunningRelease": False,
            "createsDemoRelease": False,
            "createsLiveRelease": False,
            "createsOrders": False,
        },
    }


def build_v13_26_execution_feedback_report(
    *,
    registry_path: str | Path,
    execution_outcome_export: str | Path,
    code_commit: str,
) -> dict[str, Any]:
    if not str(code_commit).strip():
        raise ValueError("V13.26 report requires a code commit")
    source = Path(execution_outcome_export)
    connection = connect_registry(registry_path)
    try:
        repository = RegistryRepository(connection)
        import_result: dict[str, Any]
        if source.exists():
            try:
                import_result = import_execution_outcome_export(
                    source,
                    repository=repository,
                ).to_dict()
            except (OSError, TypeError, ValueError, json.JSONDecodeError) as error:
                import_result = {
                    "status": "blocked_invalid_execution_outcome_export",
                    "sourcePath": str(source.resolve()),
                    "recordCount": 0,
                    "importedCount": 0,
                    "duplicateCount": 0,
                    "quarantinedCount": 0,
                    "quarantined": [],
                    "reason": str(error),
                    "inventedLineage": False,
                }
        else:
            import_result = {
                "status": "blocked_execution_outcome_export_missing",
                "sourcePath": str(source.resolve()),
                "recordCount": 0,
                "importedCount": 0,
                "duplicateCount": 0,
                "quarantinedCount": 0,
                "quarantined": [],
                "inventedLineage": False,
            }
        outcomes = repository.list_outcomes()
        execution_outcomes = [
            row for row in outcomes if row.evidenceClass in {"okx_demo", "live"}
        ]
        counts = {
            "formalExecutionOutcomeCount": len(execution_outcomes),
            "okxDemoOutcomeCount": sum(row.evidenceClass == "okx_demo" for row in execution_outcomes),
            "liveOutcomeCount": sum(row.evidenceClass == "live" for row in execution_outcomes),
        }
        releases_before = _release_fingerprints(repository)
        if execution_outcomes:
            offline_loop = run_offline_evolution_loop(repository=repository)
        else:
            offline_loop = _blocked_loop(releases_before)
        releases_after = _release_fingerprints(repository)
        if releases_before != releases_after:
            raise RuntimeError("V13.26 offline feedback mutated a running release")
    finally:
        connection.close()

    if not execution_outcomes:
        status = "blocked_no_formal_execution_outcomes"
    elif offline_loop.get("status") == "blocked_no_formal_feedback_evidence":
        status = "completed_import_waiting_minimum_feedback_evidence"
    else:
        status = "completed_offline_feedback_only"
    return {
        "reportId": "v13_26_execution_feedback_report",
        "version": "V13.26.0",
        "status": status,
        "generatedAt": datetime.now(UTC).isoformat(),
        "codeCommit": str(code_commit),
        "executionOutcomeImport": import_result,
        "executionEvidence": counts,
        "offlineEvolution": offline_loop,
        "releaseLineage": {
            "before": releases_before,
            "after": releases_after,
            "unchanged": releases_before == releases_after,
        },
        "safetyBoundary": {
            "closedReconciledOutcomesOnly": True,
            "incompleteExecutionsPromoted": False,
            "inventedLineage": False,
            "offlineOnly": True,
            "onlineModelMutation": False,
            "autoPromotion": False,
            "createsDemoRelease": False,
            "createsLiveRelease": False,
            "createsOrders": False,
            "readsCredentials": False,
            "readsPrivateAccount": False,
            "withdrawApiUsed": False,
        },
    }


def _summary(report: dict[str, Any]) -> str:
    evidence = report["executionEvidence"]
    imported = report["executionOutcomeImport"]
    return "\n".join([
        "# AlphaPilot V13.26 Execution Feedback Summary",
        "",
        f"- Status: `{report['status']}`",
        f"- Formal closed outcomes: `{evidence['formalExecutionOutcomeCount']}`",
        f"- OKX Demo outcomes: `{evidence['okxDemoOutcomeCount']}`",
        f"- Live outcomes: `{evidence['liveOutcomeCount']}`",
        f"- Newly imported: `{imported.get('importedCount', 0)}`",
        f"- Quarantined: `{imported.get('quarantinedCount', 0)}`",
        "- Only closed, reconciled, checksum-bound outcomes can enter the offline ledger.",
        "- This report does not update a model online, promote a release, or create an order.",
        "",
    ])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", default="data/evolution_registry.sqlite")
    parser.add_argument(
        "--execution-outcome-export",
        default=str(DEFAULT_EXECUTION_OUTCOME_EXPORT),
    )
    parser.add_argument("--code-commit", required=True)
    parser.add_argument("--report", default="reports/v13_26_execution_feedback_report.json")
    parser.add_argument("--summary", default="reports/v13_26_execution_feedback_summary.md")
    args = parser.parse_args()
    report = build_v13_26_execution_feedback_report(
        registry_path=args.registry,
        execution_outcome_export=args.execution_outcome_export,
        code_commit=args.code_commit,
    )
    write_json_atomic(Path(args.report), report)
    Path(args.summary).write_text(_summary(report), encoding="utf-8", newline="\n")
    print(json.dumps({
        "reportId": report["reportId"],
        "status": report["status"],
        **report["executionEvidence"],
        "createsOrders": report["safetyBoundary"]["createsOrders"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
