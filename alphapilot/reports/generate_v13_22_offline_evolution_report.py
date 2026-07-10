"""Run the bounded V13.22 offline feedback loop and write compact evidence."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from alphapilot.data_foundation.checkpoint import write_json_atomic
from alphapilot.evolution.offline.loop import OfflineEvolutionConfig, run_offline_evolution_loop
from alphapilot.evolution.registry.database import connect_registry
from alphapilot.evolution.registry.repositories import RegistryRepository


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _compact_loop(loop: dict[str, Any]) -> dict[str, Any]:
    compact = json.loads(json.dumps(loop, ensure_ascii=False, allow_nan=False))
    ingestion = compact["evidenceIngestion"]
    quarantined = ingestion.get("quarantined", [])
    ingestion["quarantined"] = quarantined[:25]
    ingestion["quarantinedDetailOmittedCount"] = max(0, len(quarantined) - 25)
    accepted = ingestion.get("acceptedOutcomeIds", {})
    ingestion["acceptedOutcomeIds"] = {
        name: values[:50] for name, values in accepted.items()
    }
    ingestion["acceptedOutcomeIdOmittedCounts"] = {
        name: max(0, len(values) - 50) for name, values in accepted.items()
    }
    return compact


def build_v13_22_report(
    *,
    registry_path: str | Path,
    code_commit: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not str(code_commit).strip():
        raise ValueError("V13.22 report requires a code commit")
    connection = connect_registry(registry_path)
    try:
        repository = RegistryRepository(connection)
        counts_before = {
            "outcomes": repository.count("OutcomeLedger"),
            "factorDefinitions": repository.count("FactorDefinitions"),
            "models": repository.count("Models"),
            "strategyCandidates": repository.count("StrategyCandidates"),
            "forwardReleases": repository.count("ForwardReleases"),
            "demoReleases": repository.count("DemoReleases"),
            "liveCandidatePackages": repository.count("LiveCandidatePackages"),
        }
        loop = run_offline_evolution_loop(repository=repository, config=OfflineEvolutionConfig())
        counts_after = {
            "outcomes": repository.count("OutcomeLedger"),
            "factorDefinitions": repository.count("FactorDefinitions"),
            "models": repository.count("Models"),
            "strategyCandidates": repository.count("StrategyCandidates"),
            "forwardReleases": repository.count("ForwardReleases"),
            "demoReleases": repository.count("DemoReleases"),
            "liveCandidatePackages": repository.count("LiveCandidatePackages"),
        }
    finally:
        connection.close()
    compact_loop = _compact_loop(loop)
    report = {
        "reportId": "v13_22_offline_evolution_report",
        "version": "V13.22.0",
        "status": loop["status"],
        "generatedAt": _utc_now(),
        "codeCommit": str(code_commit),
        "registryCountsBefore": counts_before,
        "registryCountsAfter": counts_after,
        "loop": compact_loop,
        "safetyBoundary": loop["safetyBoundary"],
    }
    triggers = {
        "schemaVersion": "offline_research_trigger_manifest_v1",
        "version": "V13.22.0",
        "loopId": loop["loopId"],
        "status": loop["status"],
        "formalOutcomeCount": loop["evidenceIngestion"]["formalOutcomeCount"],
        "quarantinedOutcomeCount": loop["evidenceIngestion"]["quarantinedCount"],
        "triggers": loop["researchTriggers"],
        "maximumLifecycleStage": "shadow_candidate",
        "automaticPromotionAllowed": False,
        "runningReleaseMutationAllowed": False,
        "createsOrders": False,
    }
    return report, triggers


def _summary(report: dict[str, Any]) -> str:
    loop = report["loop"]
    ingestion = loop["evidenceIngestion"]
    registration = loop["candidateRegistration"]
    return "\n".join(
        [
            "# AlphaPilot V13.22 Offline Evolution Summary",
            "",
            f"- Status: `{report['status']}`",
            f"- Formal outcomes: `{ingestion['formalOutcomeCount']}`",
            f"- Quarantined outcomes: `{ingestion['quarantinedCount']}`",
            f"- Research triggers: `{len(loop['researchTriggers'])}`",
            f"- New shadow candidates: `{registration['registeredCount']}`",
            f"- Release lineage unchanged: `{str(loop['releaseLineage']['unchanged']).lower()}`",
            "- Probe/synthetic evidence cannot drive evolution.",
            "- Challengers cannot mutate or replace a running release.",
            "",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", default="data/evolution_registry.sqlite")
    parser.add_argument("--code-commit", required=True)
    parser.add_argument("--report", default="reports/v13_22_offline_evolution_report.json")
    parser.add_argument("--triggers", default="reports/v13_22_offline_research_triggers.json")
    parser.add_argument("--summary", default="reports/v13_22_offline_evolution_summary.md")
    args = parser.parse_args()
    report, triggers = build_v13_22_report(
        registry_path=args.registry,
        code_commit=args.code_commit,
    )
    write_json_atomic(Path(args.report), report)
    write_json_atomic(Path(args.triggers), triggers)
    Path(args.summary).write_text(_summary(report), encoding="utf-8", newline="\n")
    print(
        json.dumps(
            {
                "reportId": report["reportId"],
                "status": report["status"],
                "formalOutcomes": report["loop"]["evidenceIngestion"]["formalOutcomeCount"],
                "quarantinedOutcomes": report["loop"]["evidenceIngestion"]["quarantinedCount"],
                "shadowCandidates": report["loop"]["candidateRegistration"]["registeredCount"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
