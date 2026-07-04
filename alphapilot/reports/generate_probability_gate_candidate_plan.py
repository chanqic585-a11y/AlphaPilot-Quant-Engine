"""Generate V13.4.20 probability gate candidate wiring plan.

The generated configs and reports are research-only. This command does not run
Freqtrade backtests, modify default probability gates, modify strategy code,
enter Dry-run, call exchange APIs, read accounts, create orders, or auto trade.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from alphapilot.probability.probability_gate_candidate_loader import list_probability_gate_candidates
from alphapilot.probability.probability_gate_candidates import (
    DEFAULT_CANDIDATE_CONFIG_DIR,
    REJECTED_DIAGNOSTIC_BUCKETS,
)
from alphapilot.reports.probability_gate_candidate_plan_schema import ProbabilityGateCandidatePlanReport

REPORT_ID = "v13_4_20_probability_gate_candidate_plan"
DEFAULT_COARSENING_REPORT = Path("reports/v13_4_19_probability_bucket_coarsening_report.json")
DEFAULT_OUTPUT_REPORT = Path("reports/v13_4_20_probability_gate_candidate_plan.json")
DEFAULT_OUTPUT_SUMMARY = Path("reports/v13_4_20_probability_gate_candidate_summary.md")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path, warnings: list[str]) -> Any:
    if not path.exists():
        warnings.append(f"Missing input file: {path.as_posix()}")
        return {} if path.suffix == ".json" else []
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")


def _load_source_tables(paths: list[str], warnings: list[str]) -> dict[str, dict[str, dict[str, Any]]]:
    tables: dict[str, dict[str, dict[str, Any]]] = {}
    for raw_path in paths:
        path = Path(raw_path)
        rows = _read_json(path, warnings)
        if not isinstance(rows, list):
            warnings.append(f"Source table is not a list: {raw_path}")
            rows = []
        tables[raw_path] = {str(row.get("bucketId")): row for row in rows if isinstance(row, dict)}
    return tables


def _find_bucket(
    bucket_id: str,
    source_tables: list[str],
    table_cache: dict[str, dict[str, dict[str, Any]]],
) -> dict[str, Any] | None:
    for source_table in source_tables:
        row = table_cache.get(source_table, {}).get(bucket_id)
        if row is not None:
            return {"sourceTable": source_table, **row}
    return None


def _candidate_gate_payload(candidate: Any, table_cache: dict[str, dict[str, dict[str, Any]]]) -> dict[str, Any]:
    matched_buckets = []
    missing_buckets = []
    for bucket_id in candidate.allowedBuckets:
        row = _find_bucket(bucket_id, candidate.sourceTables, table_cache)
        if row is None:
            missing_buckets.append(bucket_id)
        else:
            matched_buckets.append(row)
    return {
        **candidate.to_dict(),
        "matchedBuckets": matched_buckets,
        "missingBuckets": missing_buckets,
        "entryAllowed": False,
        "backtestCandidate": True,
        "strategyWired": False,
        "validationStatus": "valid_research_only" if not missing_buckets else "missing_bucket_review_required",
        "safetyNotes": [
            "Candidate gate is for backtest research only.",
            "Candidate gate is not wired to AlphaPilotDynamicRegimeV01.",
            "Candidate gate does not approve Dry-run or live trading.",
        ],
    }


def _rejected_bucket_payload(
    rejected_bucket: dict[str, Any],
    table_cache: dict[str, dict[str, dict[str, Any]]],
) -> dict[str, Any]:
    source_table = str(rejected_bucket["sourceTable"])
    bucket_id = str(rejected_bucket["bucketId"])
    row = table_cache.get(source_table, {}).get(bucket_id, {})
    return {
        **rejected_bucket,
        "matchedBucket": {"sourceTable": source_table, **row} if row else None,
        "useForTrading": False,
        "useForDryRun": False,
        "entryAllowed": False,
    }


def _backtest_plan(candidate_gate_ids: list[str]) -> dict[str, Any]:
    return {
        "version": "V13.4.21",
        "name": "Probability Gate Candidate Backtest",
        "runInThisVersion": False,
        "comparisonVariants": [
            {
                "variantId": "baseline_dynamic_regime_current_gate",
                "description": "Existing AlphaPilotDynamicRegimeV01 current probability gate.",
            },
            *[
                {
                    "variantId": candidate_gate_id,
                    "description": "Research-only candidate gate configuration for comparison backtest.",
                }
                for candidate_gate_id in candidate_gate_ids
            ],
        ],
        "scopes": [
            {
                "scopeId": "smoke",
                "pairs": ["BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT"],
                "timerange": "20260401-",
                "timeframe": "1h",
            },
            {
                "scopeId": "expanded_dynamic_universe",
                "pairs": "historical dynamic universe selectedPairs union",
                "timerange": "20260101-",
                "timeframe": "1h",
            },
        ],
        "requiredComparisons": [
            "entry count",
            "trade count",
            "profit factor",
            "expectancy",
            "max drawdown",
            "slippage stress",
            "liquidity gate interaction",
            "dryRunApproved must remain false",
        ],
        "safetyRules": [
            "Candidate gates are for backtest research only.",
            "Passing candidate backtest does not approve Dry-run.",
            "Candidate gates must go through expanded validation, slippage stress, liquidity gate, and shadow trading before any Dry-run decision.",
        ],
    }


def build_report(args: argparse.Namespace) -> ProbabilityGateCandidatePlanReport:
    warnings = [
        "Research-only candidate wiring plan. No backtest was run.",
        "Default probability gate and strategy code were not modified.",
        "Candidate configs are not wired to Dry-run or live trading.",
    ]
    coarsening_report = _read_json(Path(args.coarsening_report), warnings)
    candidates = list_probability_gate_candidates(Path(args.config_dir))
    source_tables = sorted({source for candidate in candidates for source in candidate.sourceTables})
    source_tables.extend(
        str(item["sourceTable"])
        for item in REJECTED_DIAGNOSTIC_BUCKETS
        if str(item["sourceTable"]) not in source_tables
    )
    table_cache = _load_source_tables(source_tables, warnings)
    candidate_gates = [_candidate_gate_payload(candidate, table_cache) for candidate in candidates]
    rejected_buckets = [_rejected_bucket_payload(item, table_cache) for item in REJECTED_DIAGNOSTIC_BUCKETS]
    current_gate_summary = coarsening_report.get("currentGateSummary", {}) or {}

    return ProbabilityGateCandidatePlanReport(
        reportId=REPORT_ID,
        sourceCoarseningReport=str(Path(args.coarsening_report)),
        currentGateStatus={
            "currentGatePassBucketCount": current_gate_summary.get("passBucketCount", 0),
            "dryRunApproved": False,
            "source": str(Path(args.coarsening_report)),
        },
        candidateGates=candidate_gates,
        rejectedBuckets=rejected_buckets,
        backtestPlan=_backtest_plan([candidate.candidateGateId for candidate in candidates]),
        safetyBoundary={
            "useForTrading": False,
            "useForDryRun": False,
            "modifiesDefaultProbabilityGate": False,
            "modifiesStrategyCode": False,
            "runsBacktest": False,
            "status": "research_only",
        },
        recommendedNextStep="V13.4.21 - Probability Gate Candidate Backtest",
        warnings=warnings,
        generatedAt=_utc_now(),
    )


def _summary(report: ProbabilityGateCandidatePlanReport) -> str:
    payload = report.to_dict()
    candidate_lines = []
    for candidate in payload["candidateGates"]:
        buckets = ", ".join(candidate["allowedBuckets"])
        matched = len(candidate["matchedBuckets"])
        candidate_lines.append(
            f"- {candidate['candidateGateId']}: allowed={buckets}; matchedBuckets={matched}; "
            f"status={candidate['status']}; useForDryRun={candidate['useForDryRun']}; useForTrading={candidate['useForTrading']}"
        )
    rejected_lines = [
        f"- {bucket['bucketId']}: {bucket['status']}; entryAllowed={bucket['entryAllowed']}; reason={bucket['reason']}"
        for bucket in payload["rejectedBuckets"]
    ]
    variant_lines = [
        f"- {variant['variantId']}: {variant['description']}"
        for variant in payload["backtestPlan"]["comparisonVariants"]
    ]
    scope_lines = [
        f"- {scope['scopeId']}: pairs={scope['pairs']}; timerange={scope['timerange']}; timeframe={scope['timeframe']}"
        for scope in payload["backtestPlan"]["scopes"]
    ]
    return f"""# AlphaPilot V13.4.20 Probability Gate Candidate Summary

Status: research-only candidate wiring plan.

No backtest was run. Default probability gate and strategy code were not
modified. Candidate configs are not wired to Dry-run or live trading.

## Candidate Gates

{chr(10).join(candidate_lines)}

## Rejected Diagnostic Buckets

{chr(10).join(rejected_lines)}

## V13.4.21 Backtest Plan

Comparison variants:

{chr(10).join(variant_lines)}

Scopes:

{chr(10).join(scope_lines)}

## Safety Boundary

- useForTrading: false
- useForDryRun: false
- modifiesDefaultProbabilityGate: false
- modifiesStrategyCode: false
- runsBacktest: false
- recommendedNextStep: {payload['recommendedNextStep']}
"""


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--coarsening-report", default=str(DEFAULT_COARSENING_REPORT))
    parser.add_argument("--config-dir", default=str(DEFAULT_CANDIDATE_CONFIG_DIR))
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
