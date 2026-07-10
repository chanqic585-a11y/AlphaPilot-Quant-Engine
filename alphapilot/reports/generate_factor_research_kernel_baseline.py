"""Generate the V13.12.0 legacy-factor compatibility baseline."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from alphapilot.evolution.adapters.legacy_factor_adapter import adapt_legacy_factor_library
from alphapilot.evolution.registry.database import DEFAULT_REGISTRY_PATH, connect_registry
from alphapilot.evolution.registry.repositories import RegistryRepository

VERSION = "V13.12.0"
SOURCE = "alphapilot_factor_research_kernel_v13_12_0"
DEFAULT_MANUAL_REPORT = Path("reports/v13_7_13_manual_factor_library_report.json")
DEFAULT_EVALUATION_REPORT = Path("reports/v13_7_13_factor_evaluation_report.json")
DEFAULT_OUTPUT_JSON = Path("reports/factor_research_kernel_baseline_report.json")
DEFAULT_OUTPUT_MARKDOWN = Path("reports/factor_research_kernel_baseline_summary.md")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _build_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# AlphaPilot V13.12.0 Factor Research Kernel",
        "",
        "This baseline registers legacy factor definitions without recalculating or mutating values.",
        "DSL compatibility is not evidence of profitability or promotion readiness.",
        "",
        "## Summary",
        "",
        f"- Factors: {summary['factorCount']}",
        f"- DSL supported: {summary['dslSupportedCount']}",
        f"- DSL blocked: {summary['dslBlockedCount']}",
        f"- Legacy candidate factors: {summary['legacyCandidateFactorCount']}",
        f"- Formal research ready: {summary['formalResearchReadyCount']}",
        f"- Values mutated: {str(summary['valueMutationPerformed']).lower()}",
        "",
        "## Factor Compatibility",
        "",
        "| Factor | DSL | Kernel status | Canonical expression |",
        "| --- | --- | --- | --- |",
    ]
    for factor in summary["factors"]:
        expression = factor.get("canonicalExpression") or "--"
        lines.append(
            f"| {factor['factorId']} | {str(factor['dslSupported']).lower()} | "
            f"{factor['newKernelStatus']} | `{expression}` |"
        )
    lines.extend(
        [
            "",
            "## Promotion Boundary",
            "",
            "All factors remain blocked from formal promotion until point-in-time validation,",
            "purged walk-forward, FDR, Deflated Sharpe, PBO, bootstrap, stability, and cost",
            "stress evidence exists in the new registry.",
            "",
        ]
    )
    return "\n".join(lines)


def generate_factor_research_kernel_baseline(
    *,
    manual_report_path: Path | str = DEFAULT_MANUAL_REPORT,
    evaluation_report_path: Path | str = DEFAULT_EVALUATION_REPORT,
    registry_path: Path | str = DEFAULT_REGISTRY_PATH,
    output_json: Path | str = DEFAULT_OUTPUT_JSON,
    output_markdown: Path | str = DEFAULT_OUTPUT_MARKDOWN,
) -> dict[str, Any]:
    connection = connect_registry(registry_path)
    try:
        summary = adapt_legacy_factor_library(
            manual_report_path=manual_report_path,
            evaluation_report_path=evaluation_report_path,
            repository=RegistryRepository(connection),
        )
    finally:
        connection.close()
    payload = {
        "version": VERSION,
        "source": SOURCE,
        "generatedAt": datetime.now(UTC).isoformat(),
        "status": "completed_with_blocks",
        "summary": summary,
        "requiredFormalEvidence": [
            "point_in_time_validation",
            "purged_walk_forward_with_embargo",
            "benjamini_hochberg_fdr",
            "deflated_sharpe_probability",
            "probability_of_backtest_overfitting",
            "block_bootstrap_confidence_interval",
            "pair_month_exchange_regime_stability",
            "transaction_cost_latency_and_gap_stress",
        ],
        "safetyBoundary": {
            "researchOnly": True,
            "factorValuesMutated": False,
            "createsStrategyCandidate": False,
            "createsDemoRelease": False,
            "createsOrders": False,
            "usesApiKey": False,
            "tradeApiUsed": False,
            "withdrawApiUsed": False,
            "automaticLivePromotion": False,
        },
        "nextStep": "Run new point-in-time datasets through the formal evaluation kernel.",
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
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    payload = generate_factor_research_kernel_baseline(
        manual_report_path=args.manual_report,
        evaluation_report_path=args.evaluation_report,
        registry_path=args.registry_path,
        output_json=args.output_json,
        output_markdown=args.output_markdown,
    )
    print(json.dumps({key: value for key, value in payload["summary"].items() if key != "factors"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
