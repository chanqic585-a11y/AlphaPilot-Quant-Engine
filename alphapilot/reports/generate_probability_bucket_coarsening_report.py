"""Generate V13.4.19 probability bucket coarsening analysis.

This command reads existing local probability reports and writes research-only
coarsened bucket tables. It does not run a Freqtrade backtest, modify the
strategy, loosen production gates, enter Dry-run, use API keys, read accounts,
create orders, or auto trade.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from alphapilot.probability.coarsen_probability_buckets import COARSENING_SCHEMES, build_all_coarsened_tables
from alphapilot.probability.probability_bucket_coverage import (
    CURRENT_GATE,
    EXPLORATORY_GATE,
    RESEARCH_GATE,
    current_gate_pass,
    exploratory_gate_pass,
    research_gate_pass,
    summarize_gate_coverage,
    top_exploratory_buckets,
    top_research_buckets,
)
from alphapilot.reports.probability_bucket_coarsening_schema import ProbabilityBucketCoarseningReport

REPORT_ID = "v13_4_19_probability_bucket_coarsening"
DEFAULT_PROBABILITY_TABLE = Path("reports/v13_4_14_probability_score_table.json")
DEFAULT_DATASET_REPORT = Path("reports/v13_4_14_probability_dataset_report.json")
DEFAULT_DIAGNOSIS = Path("reports/v13_4_18_dynamic_regime_pipeline_diagnosis_report.json")
DEFAULT_OUTPUT_REPORT = Path("reports/v13_4_19_probability_bucket_coarsening_report.json")
DEFAULT_OUTPUT_SUMMARY = Path("reports/v13_4_19_probability_bucket_coarsening_summary.md")
OUTPUT_TABLES = {
    "coarse_a_remove_time": Path("reports/v13_4_19_probability_score_table_coarse_a.json"),
    "coarse_b_merge_rsi_ema_bb": Path("reports/v13_4_19_probability_score_table_coarse_b.json"),
    "coarse_c_regime_liquidity_btc": Path("reports/v13_4_19_probability_score_table_coarse_c.json"),
    "coarse_d_regime_module_volatility": Path("reports/v13_4_19_probability_score_table_coarse_d.json"),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path, warnings: list[str]) -> Any:
    if not path.exists():
        warnings.append(f"Missing input file: {path.as_posix()}")
        return [] if path.name.endswith("score_table.json") else {}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")


def _gate_summary(rows: list[dict[str, Any]], gate_name: str) -> dict[str, Any]:
    if gate_name == "currentGate":
        predicate = current_gate_pass
        definition = CURRENT_GATE
    elif gate_name == "researchGate":
        predicate = research_gate_pass
        definition = RESEARCH_GATE
    else:
        predicate = exploratory_gate_pass
        definition = EXPLORATORY_GATE
    passed = [row for row in rows if predicate(row)]
    return {
        "gateName": gate_name,
        "definition": definition,
        "bucketCount": len(rows),
        "passBucketCount": len(passed),
        "passSampleCount": sum(int(row.get("sampleCount") or 0) for row in passed),
        "usage": definition.get("usage"),
    }


def _scheme_summary(scheme_id: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    coverage = summarize_gate_coverage(rows)
    research = top_research_buckets(rows)
    exploratory = top_exploratory_buckets(rows)
    scheme = COARSENING_SCHEMES[scheme_id]
    return {
        "schemeId": scheme_id,
        "description": scheme["description"],
        "bucketCount": coverage["bucketCount"],
        "totalSampleCount": coverage["totalSampleCount"],
        "sufficientSampleBucketCount": coverage["sufficientSampleBucketCount"],
        "currentGatePassBucketCount": coverage["currentGatePassBucketCount"],
        "researchGatePassBucketCount": coverage["researchGatePassBucketCount"],
        "exploratoryGatePassBucketCount": coverage["exploratoryGatePassBucketCount"],
        "topResearchBuckets": research,
        "topExploratoryBuckets": exploratory,
        "coverage": coverage,
        "outputTable": str(OUTPUT_TABLES[scheme_id]),
        "warnings": [
            *scheme["warnings"],
            "Coarsened table is research-only and is not wired to strategy entry.",
            "Profit factor is approximated from bucket-level score table rows because the full raw sample dataset is not committed.",
        ],
    }


def _root_cause_conclusion(
    original_rows: list[dict[str, Any]],
    scheme_summaries: list[dict[str, Any]],
    dataset_report: dict[str, Any],
) -> tuple[str, list[str], str]:
    original_coverage = summarize_gate_coverage(original_rows)
    research_pass = sum(item["researchGatePassBucketCount"] for item in scheme_summaries)
    exploratory_pass = sum(item["exploratoryGatePassBucketCount"] for item in scheme_summaries)
    sample_count = int(dataset_report.get("sampleCount") or dataset_report.get("labeledSampleCount") or 0)

    if sample_count < 1000:
        return (
            "D. dataset_insufficient_for_probability_score",
            [f"Probability dataset sampleCount is {sample_count}, below a robust broad-market research threshold."],
            "V13.4.20 - Expand Probability Dataset Timerange / Universe",
        )
    if research_pass > 0:
        return (
            "A. probability_table_too_sparse",
            [
                f"Original current gate pass buckets: {original_coverage['currentGatePassBucketCount']}.",
                f"Coarsened research gate pass buckets across schemes: {research_pass}.",
                "Coarsening reveals research candidates, so the original table is likely too fragmented.",
            ],
            "V13.4.20 - Probability Gate Candidate Wiring and Backtest Plan",
        )
    if exploratory_pass > 0:
        return (
            "F. mixed_result_requires_manual_review",
            [
                f"Coarsened exploratory gate buckets exist: {exploratory_pass}.",
                "Research gate still has no pass buckets, so the result is not strong enough for strategy wiring.",
            ],
            "V13.4.20 - Strategy Research Factory / Benchmark Suite",
        )
    if original_coverage["sufficientSampleBucketCount"] <= 2:
        return (
            "A. probability_table_too_sparse",
            [
                f"Only {original_coverage['sufficientSampleBucketCount']} original buckets have sampleCount >= 50.",
                "Coarsening did not recover research buckets, but the original table is still sparse.",
            ],
            "V13.4.20 - Expand Probability Dataset Timerange / Universe",
        )
    return (
        "C. no_statistical_edge_found_even_after_coarsening",
        ["No research or exploratory buckets survived after coarsening."],
        "V13.4.20 - Strategy Research Factory / Benchmark Suite",
    )


def build_report(args: argparse.Namespace) -> ProbabilityBucketCoarseningReport:
    warnings = [
        "Research-only coarsening analysis. No backtest was run.",
        "Original V13.4.14 probability score table is read-only and not modified.",
        "Coarsened tables are not wired to AlphaPilotDynamicRegimeV01.",
        "dryRunApproved and liveTradingApproved remain false.",
    ]
    score_rows_raw = _read_json(Path(args.probability_table), warnings)
    score_rows = score_rows_raw if isinstance(score_rows_raw, list) else []
    dataset_report = _read_json(Path(args.dataset_report), warnings)
    diagnosis = _read_json(Path(args.diagnosis), warnings)
    if diagnosis.get("bucketKeyConsistency", {}).get("bucketKeyMismatchSuspected"):
        warnings.append("V13.4.18 suspected bucket key mismatch; coarsening output should be manually reviewed.")

    coarsened_tables = build_all_coarsened_tables(score_rows)
    scheme_summaries = []
    for scheme_id, rows in coarsened_tables.items():
        _write_json(OUTPUT_TABLES[scheme_id], rows)
        scheme_summaries.append(_scheme_summary(scheme_id, rows))

    root_cause, evidence, next_step = _root_cause_conclusion(score_rows, scheme_summaries, dataset_report)
    return ProbabilityBucketCoarseningReport(
        reportId=REPORT_ID,
        sourceProbabilityTable=str(Path(args.probability_table)),
        sourceDiagnosis=str(Path(args.diagnosis)),
        currentGateSummary=_gate_summary(score_rows, "currentGate"),
        researchGateSummary=_gate_summary(score_rows, "researchGate"),
        exploratoryGateSummary=_gate_summary(score_rows, "exploratoryGate"),
        coarseningSchemes=scheme_summaries,
        rootCauseConclusion=root_cause,
        rootCauseEvidence=evidence,
        recommendedNextStep=next_step,
        dryRunApproved=False,
        liveTradingApproved=False,
        warnings=warnings,
        generatedAt=_utc_now(),
    )


def _summary(report: ProbabilityBucketCoarseningReport) -> str:
    payload = report.to_dict()
    scheme_lines: list[str] = []
    top_research_lines: list[str] = []
    for scheme in payload["coarseningSchemes"]:
        scheme_lines.append(
            f"- {scheme['schemeId']}: buckets={scheme['bucketCount']}, "
            f"sufficient={scheme['sufficientSampleBucketCount']}, "
            f"current={scheme['currentGatePassBucketCount']}, "
            f"research={scheme['researchGatePassBucketCount']}, "
            f"exploratory={scheme['exploratoryGatePassBucketCount']}"
        )
        for bucket in scheme["topResearchBuckets"][:5]:
            top_research_lines.append(
                f"- {scheme['schemeId']} / {bucket['bucketId']}: samples={bucket['sampleCount']}, "
                f"pf={bucket['profitFactor']}, expectancy={bucket['expectancy']}, "
                f"tpProb={bucket['hitTpBeforeSlProbability']}"
            )
    if not top_research_lines:
        top_research_lines.append("- none")

    evidence_lines = "\n".join(f"- {item}" for item in payload["rootCauseEvidence"])
    return f"""# AlphaPilot V13.4.19 Probability Bucket Coarsening Summary

Status: research-only analysis.

No backtest was run. The original probability table and strategy code were not
modified. Coarsened tables are not wired to strategy entry, Dry-run, or live
execution.

## Original Probability Table

- sourceProbabilityTable: {payload['sourceProbabilityTable']}
- sourceDiagnosis: {payload['sourceDiagnosis']}
- currentGatePassBucketCount: {payload['currentGateSummary']['passBucketCount']}
- researchGatePassBucketCount: {payload['researchGateSummary']['passBucketCount']}
- exploratoryGatePassBucketCount: {payload['exploratoryGateSummary']['passBucketCount']}

## Coarsening Schemes

{chr(10).join(scheme_lines)}

## Top Research Buckets

{chr(10).join(top_research_lines)}

## Root Cause Conclusion

{payload['rootCauseConclusion']}

Evidence:

{evidence_lines}

## Recommended Next Step

{payload['recommendedNextStep']}

## Safety Boundary

- dryRunApproved: false
- liveTradingApproved: false
- researchGate is not used for trading.
- exploratoryGate is for analysis only.
- Do not connect coarsened tables to strategy entry without a separate backtest plan.
"""


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--probability-table", default=str(DEFAULT_PROBABILITY_TABLE))
    parser.add_argument("--dataset-report", default=str(DEFAULT_DATASET_REPORT))
    parser.add_argument("--diagnosis", default=str(DEFAULT_DIAGNOSIS))
    parser.add_argument("--output-report", default=str(DEFAULT_OUTPUT_REPORT))
    parser.add_argument("--output-summary", default=str(DEFAULT_OUTPUT_SUMMARY))
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    report = build_report(args)
    payload = report.to_dict()
    _write_json(Path(args.output_report), payload)
    _write_text(Path(args.output_summary), _summary(report))
    print(json.dumps({"report": args.output_report, "summary": args.output_summary}, indent=2))


if __name__ == "__main__":
    main()
