"""Generate the V13.13.0 bounded evolution and ML readiness report."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from alphapilot.evolution.adapters.legacy_factor_adapter import adapt_legacy_factor_library
from alphapilot.evolution.orchestrator import EvolutionCycleConfig, run_evolution_cycle
from alphapilot.evolution.registry.database import DEFAULT_REGISTRY_PATH, connect_registry
from alphapilot.evolution.registry.repositories import RegistryRepository

VERSION = "V13.13.0"
SOURCE = "alphapilot_evolution_and_ml_v13_13_0"
DEFAULT_MANUAL_REPORT = Path("reports/v13_7_13_manual_factor_library_report.json")
DEFAULT_EVALUATION_REPORT = Path("reports/v13_7_13_factor_evaluation_report.json")
DEFAULT_OUTPUT_JSON = Path("reports/evolution_cycle_report.json")
DEFAULT_OUTPUT_MARKDOWN = Path("reports/evolution_cycle_summary.md")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _build_markdown(payload: dict[str, Any]) -> str:
    cycle = payload["cycle"]
    lines = [
        "# AlphaPilot V13.13.0 Evolution and ML",
        "",
        "This cycle performs bounded AST research and stops at shadow research.",
        "It does not fabricate factor values or training labels when registered data is missing.",
        "",
        "## Summary",
        "",
        f"- Cycle: `{cycle['cycleId']}`",
        f"- Seed factors: {cycle['seedFactorCount']}",
        f"- Generated candidates: {cycle['generatedCandidateCount']}",
        f"- Semantic unique: {cycle['semanticUniqueCount']}",
        f"- Newly registered factor definitions: {cycle['newRegisteredFactorDefinitionCount']}",
        f"- Correlation filter: {cycle['correlationFilterStatus']}",
        f"- Model training: {cycle['modelTrainingStatus']}",
        f"- Strategy candidates: {cycle['strategyCandidateCount']}",
        f"- Demo releases: {cycle['demoReleaseCount']}",
        f"- Maximum lifecycle stage: {cycle['maximumLifecycleStage']}",
        "",
        "## Generated Research Factors",
        "",
        "| Candidate | Mutation | Expression |",
        "| --- | --- | --- |",
    ]
    for candidate in cycle["registeredGeneratedFactors"]:
        lines.append(
            f"| `{candidate['candidateId']}` | {candidate['mutationType']} | "
            f"`{candidate['canonicalExpression']}` |"
        )
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "The Bandit allocates research units only. Model training is blocked until a",
            "registered point-in-time FactorRun, materialized feature matrix, binary label",
            "set, and purged walk-forward manifest are available. No StrategyCandidate,",
            "DemoRelease, live release, or order is created by this cycle.",
            "",
        ]
    )
    return "\n".join(lines)


def generate_evolution_cycle_report(
    *,
    manual_report_path: Path | str = DEFAULT_MANUAL_REPORT,
    evaluation_report_path: Path | str = DEFAULT_EVALUATION_REPORT,
    registry_path: Path | str = DEFAULT_REGISTRY_PATH,
    output_json: Path | str = DEFAULT_OUTPUT_JSON,
    output_markdown: Path | str = DEFAULT_OUTPUT_MARKDOWN,
    config: EvolutionCycleConfig | None = None,
) -> dict[str, Any]:
    connection = connect_registry(registry_path)
    try:
        repository = RegistryRepository(connection)
        factor_baseline = adapt_legacy_factor_library(
            manual_report_path=manual_report_path,
            evaluation_report_path=evaluation_report_path,
            repository=repository,
        )
        cycle = run_evolution_cycle(repository=repository, config=config)
    finally:
        connection.close()
    safety = {
        "researchOnly": True,
        "banditAllocatesResearchOnly": True,
        "onlineModelMutation": False,
        "createsStrategyCandidate": False,
        "createsDemoRelease": False,
        "createsLiveRelease": False,
        "createsOrders": False,
        "usesApiKey": False,
        "tradeApiUsed": False,
        "withdrawApiUsed": False,
    }
    payload = {
        "version": VERSION,
        "source": SOURCE,
        "generatedAt": datetime.now(UTC).isoformat(),
        "status": "completed_shadow_research",
        "factorBaseline": {
            key: value for key, value in factor_baseline.items() if key != "factors"
        },
        "cycle": cycle,
        "safetyBoundary": safety,
        "nextStep": "Materialize registered point-in-time FactorRuns before offline model training.",
    }
    output_json_path = Path(output_json)
    output_markdown_path = Path(output_markdown)
    _write_json(output_json_path, payload)
    output_markdown_path.parent.mkdir(parents=True, exist_ok=True)
    output_markdown_path.write_text(_build_markdown(payload), encoding="utf-8")
    return payload


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manual-report", default=str(DEFAULT_MANUAL_REPORT))
    parser.add_argument("--evaluation-report", default=str(DEFAULT_EVALUATION_REPORT))
    parser.add_argument("--registry-path", default=str(DEFAULT_REGISTRY_PATH))
    parser.add_argument("--output-json", default=str(DEFAULT_OUTPUT_JSON))
    parser.add_argument("--output-markdown", default=str(DEFAULT_OUTPUT_MARKDOWN))
    parser.add_argument("--research-budget", type=int, default=96)
    parser.add_argument("--max-candidates", type=int, default=48)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    payload = generate_evolution_cycle_report(
        manual_report_path=args.manual_report,
        evaluation_report_path=args.evaluation_report,
        registry_path=args.registry_path,
        output_json=args.output_json,
        output_markdown=args.output_markdown,
        config=EvolutionCycleConfig(
            researchBudget=args.research_budget,
            maxCandidates=args.max_candidates,
        ),
    )
    print(
        json.dumps(
            {
                key: value
                for key, value in payload["cycle"].items()
                if key not in {"registeredGeneratedFactors", "researchAllocation"}
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
