"""Generate the V13.14.0 evidence-only Demo promotion readiness report."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from alphapilot.evolution.adapters.control_console_contract import build_control_console_contract
from alphapilot.evolution.registry.database import DEFAULT_REGISTRY_PATH, connect_registry
from alphapilot.evolution.registry.repositories import RegistryRepository


DEFAULT_OUTPUT = Path("reports/demo_promotion_readiness_report.json")
DEFAULT_SUMMARY = Path("reports/demo_promotion_readiness_summary.md")


def build_report(registry_path: Path) -> dict[str, Any]:
    connection = connect_registry(registry_path)
    try:
        repository = RegistryRepository(connection)
        candidates = repository.list_strategy_candidates()
        decisions = repository.list_promotion_decisions()
        releases = repository.list_demo_releases()
        contracts = [build_control_console_contract(release) for release in releases]
    finally:
        connection.close()
    passed_decisions = [decision for decision in decisions if decision.passed]
    return {
        "version": "V13.14.0",
        "source": "demo_promotion_readiness_report_v1",
        "generatedAt": datetime.now(UTC).isoformat(),
        "status": "ready" if releases else "blocked",
        "summary": {
            "strategyCandidateCount": len(candidates),
            "promotionDecisionCount": len(decisions),
            "passedPromotionDecisionCount": len(passed_decisions),
            "demoReleaseCount": len(releases),
            "controlConsoleContractCount": len(contracts),
            "initialDemoEquityUsdt": 1000.0,
            "maxOrderNotionalUsdt": 250.0,
        },
        "candidateStates": [
            {
                "strategyCandidateId": candidate.strategyCandidateId,
                "name": candidate.name,
                "status": candidate.status,
                "contentHash": candidate.contentHash,
            }
            for candidate in candidates
        ],
        "promotionDecisions": [
            {
                "promotionDecisionId": decision.promotionDecisionId,
                "strategyCandidateId": decision.strategyCandidateId,
                "passed": decision.passed,
                "toStatus": decision.toStatus,
                "reasons": decision.reasons,
            }
            for decision in decisions
        ],
        "demoReleases": [
            {
                "demoReleaseId": release.demoReleaseId,
                "strategyCandidateId": release.strategyCandidateId,
                "status": release.status,
                "contentHash": release.contentHash,
            }
            for release in releases
        ],
        "controlConsoleContracts": contracts,
        "blockers": [] if releases else ["no_formal_strategy_candidate_has_passed_all_demo_hard_gates"],
        "safetyBoundary": {
            "okxDemoOnly": True,
            "rawCredentialStorageAllowed": False,
            "withdrawAllowed": False,
            "liveAutomaticPromotionAllowed": False,
        },
    }


def write_outputs(report: dict[str, Any], output: Path, summary: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    summary.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for contract in report.get("controlConsoleContracts", []):
        release_id = str(contract.get("demoReleaseId") or "").strip()
        if release_id:
            contract_path = output.parent / f"demo_release_contract_{release_id}.json"
            contract_path.write_text(
                json.dumps(contract, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
    values = report["summary"]
    summary.write_text(
        "\n".join(
            [
                "# V13.14.0 Demo Promotion Readiness",
                "",
                f"- Status: `{report['status']}`",
                f"- Strategy candidates: {values['strategyCandidateCount']}",
                f"- Promotion decisions: {values['promotionDecisionCount']}",
                f"- Demo releases: {values['demoReleaseCount']}",
                f"- Console contracts: {values['controlConsoleContractCount']}",
                "- Demo equity: 1000 USDT; max order notional: 250 USDT.",
                "- Live automatic promotion and Withdraw remain disabled.",
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
