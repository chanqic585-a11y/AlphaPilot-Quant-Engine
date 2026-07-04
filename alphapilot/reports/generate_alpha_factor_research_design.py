"""Generate V13.4.20 Alpha Factor Research Layer design artifacts.

This generator writes design reports only. It does not copy external project
code, implement trading strategies, download data, run backtests, enter
Dry-run, call exchange APIs, read accounts, create orders, or auto trade.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from alphapilot.benchmarks.benchmark_suite_spec import build_benchmark_suite_spec
from alphapilot.factors.factor_evaluation_schema import build_factor_evaluation_design
from alphapilot.factors.factor_operator_spec import build_factor_operator_subset
from alphapilot.factors.factor_schema import build_factor_data_panel_schema
from alphapilot.factors.manual_factor_library import build_manual_factor_library_v01
from alphapilot.reports.alpha_factor_research_design_schema import AlphaFactorResearchDesignReport
from alphapilot.research_factory.research_factory_schema import build_strategy_research_factory_spec

REPORT_ID = "v13_4_20_alpha_factor_research_design"
DEFAULT_SOURCE_REPORT = Path("reports/v13_4_19_probability_bucket_coarsening_report.json")
DEFAULT_SOURCE_SUMMARY = Path("reports/v13_4_19_probability_bucket_coarsening_summary.md")
DEFAULT_OUTPUT_JSON = Path("reports/v13_4_20_alpha_factor_research_design.json")
DEFAULT_OUTPUT_SUMMARY = Path("reports/v13_4_20_alpha_factor_research_summary.md")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path, warnings: list[str]) -> dict[str, Any]:
    if not path.exists():
        warnings.append(f"Missing input report: {path.as_posix()}")
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        warnings.append(f"Unable to parse input report {path.as_posix()}: {exc}")
        return {}


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")


def _integration_with_dynamic_regime(source_report: dict[str, Any]) -> dict[str, Any]:
    return {
        "currentEvidence": {
            "v13_4_19_rootCause": source_report.get("rootCauseConclusion", "unavailable"),
            "v13_4_19_recommendedNextStep": source_report.get("recommendedNextStep", "unavailable"),
            "currentGatePassBucketCount": source_report.get("currentGateSummary", {}).get("passBucketCount", "unavailable"),
            "researchGatePassBucketCount": source_report.get("researchGateSummary", {}).get("passBucketCount", "unavailable"),
        },
        "futureFlow": [
            "historical_ohlcv",
            "historical_dynamic_universe_snapshots",
            "regime_labels",
            "factor_data_panel",
            "factor_library",
            "factor_evaluation_report",
            "benchmark_strategy_suite",
            "strategy_research_factory",
            "dynamic_regime_strategy_candidate",
        ],
        "rule": "Do not wire coarse probability buckets directly into strategy entries without raw sample factor research.",
    }


def build_report(source_report_path: Path, source_summary_path: Path) -> AlphaFactorResearchDesignReport:
    warnings = [
        "Design-only report. No backtest was run.",
        "No strategy code was written or modified.",
        "No external source code was copied.",
        "dryRunApproved and liveTradingApproved remain false.",
        "V13.4.19 coarse bucket PF is bucket-level approximate evidence and is not an entry gate.",
    ]
    source_report = _read_json(source_report_path, warnings)
    if not source_summary_path.exists():
        warnings.append(f"Missing input summary: {source_summary_path.as_posix()}")

    factory = build_strategy_research_factory_spec()
    return AlphaFactorResearchDesignReport(
        reportId=REPORT_ID,
        purpose="Design Alpha Factor Research Layer and Benchmark Suite",
        sourceInsights=[
            "alpha101 factor research workflow",
            "CryptoAgentPro regime and benchmark architecture",
            "AlphaPilot V13.4.x failed strategy evidence",
            "V13.4.19 probability bucket coarsening limitations",
        ],
        factorDataPanel=build_factor_data_panel_schema().to_dict(),
        operatorSubset=build_factor_operator_subset(),
        manualFactorLibrary=build_manual_factor_library_v01(),
        factorEvaluationMetrics=build_factor_evaluation_design(),
        benchmarkSuite=build_benchmark_suite_spec(),
        strategyResearchFactory=factory,
        integrationWithDynamicRegime=_integration_with_dynamic_regime(source_report),
        dryRunApproved=False,
        liveTradingApproved=False,
        nextStepRecommendation="V13.4.21 - Factor Data Panel and Manual Factor Library Implementation",
        generatedAt=_utc_now(),
        warnings=warnings,
    )


def _summary(report: AlphaFactorResearchDesignReport) -> str:
    payload = report.to_dict()
    factors = payload["manualFactorLibrary"]
    operators = payload["operatorSubset"]
    benchmarks = payload["benchmarkSuite"]["benchmarks"]
    metrics = payload["factorEvaluationMetrics"]["metrics"]
    return f"""# AlphaPilot V13.4.20 Alpha Factor Research Summary

Status: design-only, research-only.

No trading strategy was written. No backtest was run. No Dry-run or live
trading approval was granted.

## Purpose

{payload["purpose"]}

V13.4.20 replaces the previously considered probability-gate wiring step with
an Alpha Factor Research Layer and Benchmark Strategy Suite design. The reason
is that V13.4.19 coarse probability buckets are bucket-level approximations and
should not be promoted directly into strategy entry logic.

## Factor Data Panel

- panelId: {payload["factorDataPanel"]["panelId"]}
- primaryIndex: {payload["factorDataPanel"]["primaryIndex"]}
- fieldCount: {len(payload["factorDataPanel"]["fields"])}
- futureFieldCount: {len(payload["factorDataPanel"]["futureFields"])}

## Operator Subset

- timeSeriesOperators: {len(operators["timeSeriesOperators"])}
- crossSectionalOperators: {len(operators["crossSectionalOperators"])}
- combinationOperators: {len(operators["combinationOperators"])}
- excludedFamilies: {", ".join(operators["excludedOperatorFamilies"])}

## Manual Factor Library V01

- factorCount: {len(factors)}
- factors: {", ".join(item["factorId"] for item in factors)}

## Factor Evaluation

- metricCount: {len(metrics)}
- forwardWindowsBars: {payload["factorEvaluationMetrics"]["forwardWindowsBars"]}
- regimeSegments: {payload["factorEvaluationMetrics"]["regimeSegments"]}
- universeSegments: {payload["factorEvaluationMetrics"]["universeSegments"]}

## Benchmark Strategy Suite

- benchmarkCount: {len(benchmarks)}
- benchmarks: {", ".join(item["benchmarkId"] for item in benchmarks)}
- rejectedIdeas: {", ".join(item["benchmarkId"] for item in payload["benchmarkSuite"]["rejectedBenchmarkIdeas"])}

## Strategy Research Factory

Workflow:

{chr(10).join(f"- {step}" for step in payload["strategyResearchFactory"]["workflow"])}

## Safety Boundary

- dryRunApproved: {payload["dryRunApproved"]}
- liveTradingApproved: {payload["liveTradingApproved"]}
- no external source code copied
- no API key
- no Trade API
- no Withdraw API
- no account or position reads
- no real orders
- no auto trading
- no backtest execution

## Next Step

{payload["nextStepRecommendation"]}
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Alpha factor research design report.")
    parser.add_argument("--source-report", default=str(DEFAULT_SOURCE_REPORT))
    parser.add_argument("--source-summary", default=str(DEFAULT_SOURCE_SUMMARY))
    parser.add_argument("--output-json", default=str(DEFAULT_OUTPUT_JSON))
    parser.add_argument("--output-summary", default=str(DEFAULT_OUTPUT_SUMMARY))
    args = parser.parse_args()

    report = build_report(Path(args.source_report), Path(args.source_summary))
    _write_json(Path(args.output_json), report.to_dict())
    _write_text(Path(args.output_summary), _summary(report))
    print(json.dumps({"report": args.output_json, "summary": args.output_summary}, indent=2))


if __name__ == "__main__":
    main()
