"""Generate the V13.11.0 evolution registry foundation report."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from alphapilot.evolution.registry.database import DEFAULT_REGISTRY_PATH, connect_registry
from alphapilot.evolution.registry.legacy_importer import import_legacy_reports
from alphapilot.evolution.registry.repositories import RegistryRepository

VERSION = "V13.11.0"
SOURCE = "alphapilot_evolution_registry_foundation_v13_11_0"

DEFAULT_REPORTS_DIR = Path("reports")
DEFAULT_OUTPUT_JSON = DEFAULT_REPORTS_DIR / "evolution_registry_foundation_report.json"
DEFAULT_OUTPUT_MARKDOWN = DEFAULT_REPORTS_DIR / "evolution_registry_foundation_summary.md"


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _build_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    classifications = summary.get("classificationCounts", {})
    assessment = summary["candidateFormationAssessment"]
    lines = [
        "# AlphaPilot V13.11.0 Evolution Registry Foundation",
        "",
        "This report imports existing local JSON reports as immutable research evidence.",
        "It does not create runnable strategy candidates, Demo releases, or orders.",
        "",
        "## Summary",
        "",
        f"- Scanned JSON files: {summary['scannedFileCount']}",
        f"- Valid JSON artifacts: {summary['validJsonCount']}",
        f"- Valid JSON objects: {summary['validObjectCount']}",
        f"- Invalid files: {summary['invalidFileCount']}",
        f"- Registered evidence: {summary['totalEvidenceCount']}",
        f"- Independent legacy strategy families: {summary['independentStrategyFamilyCount']}",
        f"- Runnable strategy candidates created: {summary['strategyCandidateCount']}",
        f"- Demo releases created: {summary['demoReleaseCount']}",
        "",
        "## Classification",
        "",
    ]
    for name, count in classifications.items():
        lines.append(f"- {name}: {count}")
    lines.extend(
        [
            "",
            "## Candidate Formation Assessment",
            "",
            f"- Legacy candidate evidence: {assessment['legacyCandidateEvidenceCount']}",
            f"- Blocked from runnable candidate creation: {assessment['blockedFromRunnableCandidateCount']}",
            f"- Duplicate family members: {summary['duplicateFamilyMemberCount']}",
            "- Automatic creation allowed: false",
            "- Blocking reasons:",
        ]
    )
    for reason in assessment["blockingReasons"]:
        lines.append(f"  - {reason}")
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "Legacy evidence requires point-in-time validation, semantic deduplication,",
            "formal strategy contracts, and locked out-of-sample evaluation before promotion.",
            "",
        ]
    )
    return "\n".join(lines)


def generate_registry_foundation_report(
    *,
    reports_dir: Path | str = DEFAULT_REPORTS_DIR,
    registry_path: Path | str = DEFAULT_REGISTRY_PATH,
    output_json: Path | str = DEFAULT_OUTPUT_JSON,
    output_markdown: Path | str = DEFAULT_OUTPUT_MARKDOWN,
) -> dict[str, Any]:
    connection = connect_registry(registry_path)
    try:
        repository = RegistryRepository(connection)
        import_summary = import_legacy_reports(Path(reports_dir), repository)
        persisted = repository.list_legacy_evidence()
        classification_counts = Counter(item.evidenceType for item in persisted)
        non_candidate_reason_counts = Counter(
            reason
            for item in persisted
            if item.evidenceType != "strategy_candidate_evidence"
            for reason in item.classificationReasons
        )
        duplicate_members = [
            {
                "sourcePath": item.sourcePath,
                "strategyFamilyId": item.strategyFamilyId,
                "familyFingerprint": item.familyFingerprint,
                "ruleFingerprint": item.ruleFingerprint,
            }
            for item in persisted
            if item.evidenceType == "duplicate_family_member"
        ]
        legacy_candidate_evidence_count = classification_counts["strategy_candidate_evidence"]
        family_ids = {item.strategyFamilyId for item in persisted if item.strategyFamilyId}
        summary = {
            **import_summary,
            "totalEvidenceCount": len(persisted),
            "independentStrategyFamilyCount": len(family_ids),
            "classificationCounts": dict(sorted(classification_counts.items())),
            "nonCandidateReasonCounts": dict(sorted(non_candidate_reason_counts.items())),
            "duplicateFamilyMemberCount": len(duplicate_members),
            "duplicateFamilyMembers": duplicate_members,
            "candidateFormationAssessment": {
                "legacyCandidateEvidenceCount": legacy_candidate_evidence_count,
                "blockedFromRunnableCandidateCount": len(persisted),
                "automaticCreationAllowed": False,
                "blockingReasons": [
                    "formal_strategy_contract_required",
                    "point_in_time_validation_required",
                    "semantic_and_correlation_dedup_required",
                    "purged_walk_forward_evaluation_required",
                    "cost_and_multiple_testing_controls_required",
                ],
            },
            "strategyCandidateCount": repository.count("StrategyCandidates"),
            "demoReleaseCount": repository.count("DemoReleases"),
        }
    finally:
        connection.close()

    payload = {
        "version": VERSION,
        "source": SOURCE,
        "generatedAt": utc_now(),
        "status": "completed_with_errors" if summary["invalidFileCount"] else "completed",
        "summary": summary,
        "safetyBoundary": {
            "researchOnly": True,
            "createsStrategyCandidate": False,
            "createsDemoRelease": False,
            "createsOrders": False,
            "usesApiKey": False,
            "tradeApiUsed": False,
            "withdrawApiUsed": False,
            "automaticLivePromotion": False,
        },
        "nextStep": "Validate Factor DSL and point-in-time research inputs before candidate creation.",
    }
    output_json_path = Path(output_json)
    output_markdown_path = Path(output_markdown)
    _write_json(output_json_path, payload)
    output_markdown_path.parent.mkdir(parents=True, exist_ok=True)
    output_markdown_path.write_text(_build_markdown(payload), encoding="utf-8")
    return payload


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reports-dir", default=str(DEFAULT_REPORTS_DIR))
    parser.add_argument("--registry-path", default=str(DEFAULT_REGISTRY_PATH))
    parser.add_argument("--output-json", default=str(DEFAULT_OUTPUT_JSON))
    parser.add_argument("--output-markdown", default=str(DEFAULT_OUTPUT_MARKDOWN))
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    payload = generate_registry_foundation_report(
        reports_dir=args.reports_dir,
        registry_path=args.registry_path,
        output_json=args.output_json,
        output_markdown=args.output_markdown,
    )
    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
