"""Generate V13.4.18 Dynamic Regime signal pipeline diagnosis.

This module only reads existing V13.4.13, V13.4.14, and V13.4.17 local
research reports. It does not run a backtest, change strategy rules, enter
Dry-run, call exchange APIs, read accounts, create orders, or auto trade.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from alphapilot.reports.dynamic_regime_pipeline_diagnosis_schema import (
    DynamicRegimePipelineDiagnosisReport,
)

REPORT_ID = "v13_4_18_dynamic_regime_pipeline_diagnosis_report"
DEFAULT_EXPANDED_REPORT = Path("reports/v13_4_17_dynamic_regime_expanded_report.json")
DEFAULT_EXPANDED_SUMMARY = Path("reports/v13_4_17_dynamic_regime_expanded_summary.md")
DEFAULT_PROBABILITY_TABLE = Path("reports/v13_4_14_probability_score_table.json")
DEFAULT_PROBABILITY_DATASET_REPORT = Path("reports/v13_4_14_probability_dataset_report.json")
DEFAULT_UNIVERSE_REPORT = Path("reports/v13_4_13_dynamic_universe_build_report.json")
DEFAULT_UNIVERSE_SUMMARY = Path("reports/v13_4_13_dynamic_universe_summary.md")
DEFAULT_OUTPUT_JSON = Path("reports/v13_4_18_dynamic_regime_pipeline_diagnosis_report.json")
DEFAULT_OUTPUT_SUMMARY = Path("reports/v13_4_18_dynamic_regime_pipeline_diagnosis_summary.md")

COMPONENT_FIELDS = [
    "regimeCandidate",
    "liquidityBucket",
    "volatilityBucket",
    "rsiBucket",
    "emaDistanceBucket",
    "bbPositionBucket",
    "btcState",
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _round(value: Any, digits: int = 4) -> float | None:
    try:
        if value is None:
            return None
        return round(float(value), digits)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _safe_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _pct(part: int | float, total: int | float) -> float:
    if not total:
        return 0.0
    return round(float(part) / float(total) * 100.0, 4)


def _read_json(path: Path, warnings: list[str]) -> Any:
    if not path.exists():
        warnings.append(f"Missing input file: {path.as_posix()}")
        return {} if path.suffix == ".json" else ""
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")


def _bucket_key(row: dict[str, Any]) -> str:
    return "_".join(str(row.get(field, "unknown")) for field in COMPONENT_FIELDS)


def _component_domains(score_rows: list[dict[str, Any]]) -> dict[str, list[str]]:
    domains: dict[str, set[str]] = {field: set() for field in COMPONENT_FIELDS}
    for row in score_rows:
        for field in COMPONENT_FIELDS:
            value = row.get(field)
            if value is not None:
                domains[field].add(str(value))
    return {
        field: sorted(values, key=lambda item: (-len(item), item))
        for field, values in domains.items()
    }


def _parse_bucket_key(bucket_id: str, domains: dict[str, list[str]]) -> dict[str, str] | None:
    parsed: dict[str, str] = {}

    def walk(position: int, field_index: int) -> bool:
        if field_index == len(COMPONENT_FIELDS):
            return position == len(bucket_id)
        field = COMPONENT_FIELDS[field_index]
        is_last = field_index == len(COMPONENT_FIELDS) - 1
        for value in domains.get(field, []):
            token = value if is_last else f"{value}_"
            if bucket_id.startswith(token, position):
                parsed[field] = value
                if walk(position + len(token), field_index + 1):
                    return True
                parsed.pop(field, None)
        return False

    return parsed if walk(0, 0) else None


def _score_table_stats(score_rows: list[dict[str, Any]]) -> dict[str, Any]:
    decision_counts = Counter(str(row.get("decision", "unknown")) for row in score_rows)
    sample_buckets = Counter()
    for row in score_rows:
        sample_count = _safe_int(row.get("sampleCount"))
        if sample_count < 10:
            sample_buckets["0_to_9"] += 1
        elif sample_count < 30:
            sample_buckets["10_to_29"] += 1
        elif sample_count < 50:
            sample_buckets["30_to_49"] += 1
        elif sample_count < 100:
            sample_buckets["50_to_99"] += 1
        else:
            sample_buckets["100_plus"] += 1

    sufficient = [
        row for row in score_rows if _safe_int(row.get("sampleCount")) >= 50
    ]
    current_gate_pass = [
        row
        for row in score_rows
        if _safe_int(row.get("sampleCount")) >= 50
        and (_safe_float(row.get("hitTpBeforeSlProbability")) or 0.0) >= 0.45
        and (_safe_float(row.get("profitFactor")) or 0.0) >= 1.2
        and (_safe_float(row.get("expectancy")) or 0.0) > 0.0
        and str(row.get("decision")) == "research_candidate"
    ]

    return {
        "totalBuckets": len(score_rows),
        "decisionCounts": dict(sorted(decision_counts.items())),
        "sampleCountBuckets": dict(sorted(sample_buckets.items())),
        "sufficientSampleBuckets": len(sufficient),
        "insufficientSampleBuckets": max(len(score_rows) - len(sufficient), 0),
        "researchCandidateBuckets": decision_counts.get("research_candidate", 0),
        "observeOnlyBuckets": decision_counts.get("observe_only", 0),
        "currentGatePassBuckets": len(current_gate_pass),
        "currentGateCriteria": {
            "sampleCountGte": 50,
            "hitTpBeforeSlProbabilityGte": 0.45,
            "profitFactorGte": 1.2,
            "expectancyGt": 0,
            "decision": "research_candidate",
        },
    }


def _weighted_gate_failure_reasons(
    bucket_performance: list[dict[str, Any]], score_by_key: dict[str, dict[str, Any]]
) -> dict[str, int]:
    reasons: Counter[str] = Counter()
    for bucket in bucket_performance:
        bucket_id = str(bucket.get("bucketId") or "unknown")
        rows = _safe_int(bucket.get("rows"))
        score_row = score_by_key.get(bucket_id)
        if score_row is None:
            reasons["bucket_not_found_in_probability_table"] += rows
            continue
        sample_count = _safe_int(score_row.get("sampleCount"))
        hit_probability = _safe_float(score_row.get("hitTpBeforeSlProbability")) or 0.0
        profit_factor = _safe_float(score_row.get("profitFactor")) or 0.0
        expectancy = _safe_float(score_row.get("expectancy")) or 0.0
        decision = str(score_row.get("decision"))
        if sample_count < 50:
            reasons["insufficient_sample"] += rows
        elif hit_probability < 0.45:
            reasons["hit_probability_too_low"] += rows
        elif profit_factor < 1.2:
            reasons["profit_factor_too_low"] += rows
        elif expectancy <= 0:
            reasons["expectancy_not_positive"] += rows
        elif decision != "research_candidate":
            reasons["decision_not_research_candidate"] += rows
        else:
            reasons["unknown_probability_gate_block"] += rows
    return dict(sorted(reasons.items(), key=lambda item: (-item[1], item[0])))


def _bucket_key_consistency(
    score_rows: list[dict[str, Any]], bucket_performance: list[dict[str, Any]]
) -> dict[str, Any]:
    score_keys = {str(row.get("bucketId")) for row in score_rows if row.get("bucketId")}
    rebuilt_mismatches = [
        {
            "bucketId": row.get("bucketId"),
            "rebuiltBucketId": _bucket_key(row),
        }
        for row in score_rows
        if row.get("bucketId") and str(row.get("bucketId")) != _bucket_key(row)
    ]
    domains = _component_domains(score_rows)
    checked = []
    format_mismatch_count = 0
    component_parseable_missing_count = 0
    lookup_hits = 0
    lookup_missing = 0

    for bucket in bucket_performance:
        bucket_id = str(bucket.get("bucketId") or "unknown")
        found = bucket_id in score_keys
        lookup_hits += 1 if found else 0
        lookup_missing += 0 if found else 1
        parsed = _parse_bucket_key(bucket_id, domains)
        if not found and parsed is None:
            format_mismatch_count += 1
        if not found and parsed is not None:
            component_parseable_missing_count += 1
        checked.append(
            {
                "bucketId": bucket_id,
                "rows": _safe_int(bucket.get("rows")),
                "foundInProbabilityTable": found,
                "parseableWithScoreTableDomains": parsed is not None,
                "parsedComponents": parsed,
            }
        )

    mismatch_suspected = bool(rebuilt_mismatches or format_mismatch_count)
    return {
        "scoreTableRows": len(score_rows),
        "scoreTableRebuildMismatchCount": len(rebuilt_mismatches),
        "scoreTableRebuildMismatchSamples": rebuilt_mismatches[:10],
        "expandedReportBucketsChecked": len(bucket_performance),
        "expandedReportLookupHitBuckets": lookup_hits,
        "expandedReportLookupMissingBuckets": lookup_missing,
        "expandedReportFormatMismatchCount": format_mismatch_count,
        "expandedReportParseableMissingBuckets": component_parseable_missing_count,
        "bucketKeyMismatchSuspected": mismatch_suspected,
        "checkedBucketSamples": checked[:20],
        "diagnosis": (
            "Bucket key format mismatch is suspected."
            if mismatch_suspected
            else "Bucket key format appears consistent; missing buckets are more consistent with probability table coverage gaps."
        ),
    }


def _probability_gate_diagnosis(
    expanded_report: dict[str, Any],
    dataset_report: dict[str, Any],
    score_rows: list[dict[str, Any]],
    bucket_consistency: dict[str, Any],
) -> dict[str, Any]:
    probability_summary = expanded_report.get("probabilityScoreSummary", {}) or {}
    bucket_performance = expanded_report.get("probabilityBucketPerformance", []) or []
    score_by_key = {
        str(row.get("bucketId")): row
        for row in score_rows
        if isinstance(row, dict) and row.get("bucketId")
    }
    score_stats = _score_table_stats(score_rows)
    dataset_gate_summary = dataset_report.get("probabilityGateSummary", {}) or {}
    rows_evaluated = _safe_int(probability_summary.get("rowsEvaluated"))
    available = _safe_int(probability_summary.get("available"))
    pass_count = _safe_int(probability_summary.get("pass"))
    fail_count = _safe_int(probability_summary.get("fail"))

    top_missing = [
        {
            "bucketId": row.get("bucketId"),
            "rows": _safe_int(row.get("rows")),
            "available": _safe_int(row.get("available")),
            "pass": _safe_int(row.get("pass")),
        }
        for row in sorted(
            bucket_performance,
            key=lambda item: _safe_int(item.get("rows")),
            reverse=True,
        )
        if _safe_int(row.get("available")) == 0
    ][:20]

    return {
        "rowsEvaluated": rows_evaluated,
        "lookupHits": available,
        "lookupMisses": max(rows_evaluated - available, 0),
        "lookupHitRatePercent": _pct(available, rows_evaluated),
        "probabilityScorePass": pass_count,
        "probabilityScoreFail": fail_count,
        "probabilityScorePassRatePercent": _pct(pass_count, rows_evaluated),
        "scoreTableCoverage": score_stats,
        "datasetGateSummary": dataset_gate_summary,
        "weightedTopBucketFailureReasons": _weighted_gate_failure_reasons(
            bucket_performance, score_by_key
        ),
        "topMissingBucketKeysFromExpandedReport": top_missing,
        "bucketKeyMismatchSuspected": bucket_consistency.get("bucketKeyMismatchSuspected", False),
        "diagnosis": (
            "The probability gate is the immediate blocker: lookup hits exist, but no rows pass the current score table decision gate."
            if available > 0 and pass_count == 0
            else "Probability gate diagnosis is inconclusive from the current report."
        ),
    }


def _signal_funnel(
    expanded_report: dict[str, Any],
    universe_report: dict[str, Any],
    score_table_stats: dict[str, Any],
) -> dict[str, Any]:
    probability_summary = expanded_report.get("probabilityScoreSummary", {}) or {}
    module_breakdown = expanded_report.get("moduleBreakdown", {}) or {}
    regime_breakdown = expanded_report.get("regimeBreakdown", {}) or {}
    liquidity_summary = expanded_report.get("liquidityGateSummary", {}) or {}
    raw_metrics = expanded_report.get("rawMetrics", {}) or {}
    dynamic_universe = expanded_report.get("dynamicUniverseSummary", {}) or {}
    skip_reasons = module_breakdown.get("skipReasons", {}) or {}

    rows_evaluated = _safe_int(probability_summary.get("rowsEvaluated"))
    data_missing = _safe_int(skip_reasons.get("data_missing"))
    trend_candidates = _safe_int(module_breakdown.get("trendModulePass"))
    mean_reversion_candidates = _safe_int(module_breakdown.get("meanReversionModulePass"))
    probability_pass = _safe_int(probability_summary.get("pass"))

    return {
        "historicalUniverseSnapshots": _safe_int(
            universe_report.get("snapshotCount")
            or dynamic_universe.get("snapshotCount")
        ),
        "expandedValidationPairs": _safe_int(dynamic_universe.get("pairUnionCount")),
        "rowsEvaluated": rows_evaluated,
        "rowsWithRequiredData": max(rows_evaluated - data_missing, 0),
        "dataMissingRows": data_missing,
        "regimeRows": dict(regime_breakdown),
        "trendModuleCandidates": trend_candidates,
        "meanReversionModuleCandidates": mean_reversion_candidates,
        "moduleCandidateRows": trend_candidates + mean_reversion_candidates,
        "probabilityLookupAttempts": rows_evaluated,
        "probabilityLookupHits": _safe_int(probability_summary.get("available")),
        "probabilityLookupMisses": max(rows_evaluated - _safe_int(probability_summary.get("available")), 0),
        "probabilityScorePass": probability_pass,
        "probabilityTableSufficientSampleBuckets": score_table_stats.get("sufficientSampleBuckets", 0),
        "liquidityGateRowsAudited": _safe_int(liquidity_summary.get("fallbackUsedRows")),
        "liquidityGateEffectiveRowsAfterProbability": probability_pass,
        "finalEntrySignals": _safe_int(module_breakdown.get("finalEntrySignals")),
        "actualTrades": _safe_int(raw_metrics.get("tradeCount")),
        "mainBlocker": "probability_score_gate",
        "dryRunApproved": False,
        "liveTradingApproved": False,
    }


def _regime_router_diagnosis(expanded_report: dict[str, Any]) -> dict[str, Any]:
    regime_breakdown = expanded_report.get("regimeBreakdown", {}) or {}
    total = sum(_safe_int(value) for value in regime_breakdown.values())
    trend = _safe_int(regime_breakdown.get("trend"))
    mean_reversion = _safe_int(regime_breakdown.get("mean_reversion"))
    avoid = _safe_int(regime_breakdown.get("avoid"))
    unknown = _safe_int(regime_breakdown.get("unknown"))
    eligible = trend + mean_reversion
    return {
        "totalRows": total,
        "trendRows": trend,
        "meanReversionRows": mean_reversion,
        "avoidRows": avoid,
        "unknownRows": unknown,
        "trendPercent": _pct(trend, total),
        "meanReversionPercent": _pct(mean_reversion, total),
        "avoidPercent": _pct(avoid, total),
        "unknownPercent": _pct(unknown, total),
        "eligibleRegimeRows": eligible,
        "eligibleRegimePercent": _pct(eligible, total),
        "regimeRouterTooStrictSuspected": eligible == 0,
        "diagnosis": (
            "Regime router produced eligible trend and mean-reversion rows, so it is not the immediate zero-signal blocker."
            if eligible > 0
            else "Regime router produced no eligible rows and should be inspected."
        ),
    }


def _module_candidate_diagnosis(expanded_report: dict[str, Any]) -> dict[str, Any]:
    module_breakdown = expanded_report.get("moduleBreakdown", {}) or {}
    regime_breakdown = expanded_report.get("regimeBreakdown", {}) or {}
    trend = _safe_int(regime_breakdown.get("trend"))
    mean_reversion = _safe_int(regime_breakdown.get("mean_reversion"))
    trend_pass = _safe_int(module_breakdown.get("trendModulePass"))
    mean_reversion_pass = _safe_int(module_breakdown.get("meanReversionModulePass"))
    final_entry = _safe_int(module_breakdown.get("finalEntrySignals"))
    return {
        "trendModuleCandidates": trend_pass,
        "meanReversionModuleCandidates": mean_reversion_pass,
        "moduleCandidateRows": trend_pass + mean_reversion_pass,
        "trendModuleCandidateRateWithinTrendPercent": _pct(trend_pass, trend),
        "meanReversionCandidateRateWithinMeanReversionPercent": _pct(
            mean_reversion_pass, mean_reversion
        ),
        "finalEntrySignals": final_entry,
        "skipReasons": module_breakdown.get("skipReasons", {}),
        "moduleRulesTooStrictSuspected": (trend_pass + mean_reversion_pass) == 0,
        "diagnosis": (
            "Module rules produced candidates, but downstream probability scoring reduced final entries to zero."
            if (trend_pass + mean_reversion_pass) > 0 and final_entry == 0
            else "Module candidate generation may need deeper inspection."
        ),
    }


def _liquidity_gate_diagnosis(expanded_report: dict[str, Any]) -> dict[str, Any]:
    liquidity_summary = expanded_report.get("liquidityGateSummary", {}) or {}
    probability_pass = _safe_int((expanded_report.get("probabilityScoreSummary", {}) or {}).get("pass"))
    fallback_rows = _safe_int(liquidity_summary.get("fallbackUsedRows"))
    available = bool(liquidity_summary.get("available"))
    return {
        "liquidityDataAvailable": available,
        "fallbackUsedRows": fallback_rows,
        "fallbackPolicy": liquidity_summary.get("fallbackPolicy"),
        "effectiveRowsAfterProbabilityGate": probability_pass,
        "liquidityGateBlockingSuspected": False if probability_pass == 0 else not available,
        "diagnosis": (
            "Liquidity gate is not the immediate blocker because no rows reached it after the probability gate."
            if probability_pass == 0
            else "Liquidity data should be inspected for rows that pass probability scoring."
        ),
    }


def _root_causes(
    probability_diagnosis: dict[str, Any],
    bucket_consistency: dict[str, Any],
    regime_diagnosis: dict[str, Any],
    module_diagnosis: dict[str, Any],
    liquidity_diagnosis: dict[str, Any],
    score_stats: dict[str, Any],
    universe_report: dict[str, Any],
) -> list[dict[str, Any]]:
    causes: list[dict[str, Any]] = []
    if bucket_consistency.get("bucketKeyMismatchSuspected"):
        causes.append(
            {
                "category": "bucket_key_mismatch",
                "likelihood": "high",
                "evidence": "Generated bucket keys do not consistently match score table bucket IDs.",
            }
        )

    if score_stats.get("researchCandidateBuckets", 0) == 0 or score_stats.get("currentGatePassBuckets", 0) == 0:
        causes.append(
            {
                "category": "probability_table_insufficient_coverage",
                "likelihood": "high",
                "evidence": (
                    f"Score table has {score_stats.get('currentGatePassBuckets', 0)} current-gate pass buckets "
                    f"and {score_stats.get('researchCandidateBuckets', 0)} research_candidate buckets."
                ),
            }
        )
        causes.append(
            {
                "category": "probability_gate_too_strict",
                "likelihood": "medium",
                "evidence": "V13.4.17 has lookup hits but probabilityScorePass remains zero.",
            }
        )

    if regime_diagnosis.get("regimeRouterTooStrictSuspected"):
        causes.append(
            {
                "category": "regime_router_too_strict",
                "likelihood": "medium",
                "evidence": "Regime router produced no eligible trend or mean-reversion rows.",
            }
        )

    if module_diagnosis.get("moduleRulesTooStrictSuspected"):
        causes.append(
            {
                "category": "module_rules_too_strict",
                "likelihood": "medium",
                "evidence": "No module candidates were generated before probability scoring.",
            }
        )

    if _safe_int(universe_report.get("snapshotCount")) == 0:
        causes.append(
            {
                "category": "dynamic_universe_too_narrow",
                "likelihood": "medium",
                "evidence": "Historical dynamic universe report has no snapshots.",
            }
        )

    if liquidity_diagnosis.get("liquidityGateBlockingSuspected"):
        causes.append(
            {
                "category": "liquidity_gate_blocking",
                "likelihood": "medium",
                "evidence": "Rows passed probability scoring but liquidity gate data was unavailable.",
            }
        )

    if not causes:
        causes.append(
            {
                "category": "unknown",
                "likelihood": "low",
                "evidence": "No dominant root cause was detected from existing reports.",
            }
        )
    return causes


def _recommended_next_step(root_causes: list[dict[str, Any]]) -> dict[str, Any]:
    categories = [cause.get("category") for cause in root_causes]
    if "bucket_key_mismatch" in categories:
        return {
            "version": "V13.4.19",
            "name": "Probability Bucket Key Normalization Hotfix",
            "reason": "Bucket key mismatch should be fixed before changing probability policy.",
        }
    if "probability_table_insufficient_coverage" in categories:
        return {
            "version": "V13.4.19",
            "name": "Probability Bucket Coarsening and Sample Coverage Expansion",
            "reason": "Current probability table coverage has no current-gate pass buckets.",
        }
    if "probability_gate_too_strict" in categories:
        return {
            "version": "V13.4.19",
            "name": "Probability Gate Calibration Candidate Design",
            "reason": "Probability pass rate is zero despite lookup hits.",
        }
    if "module_rules_too_strict" in categories or "regime_router_too_strict" in categories:
        return {
            "version": "V13.4.19",
            "name": "Regime Router / Module Candidate Logic Diagnosis",
            "reason": "No candidates are produced before probability scoring.",
        }
    if "dynamic_universe_too_narrow" in categories or "data_availability_issue" in categories:
        return {
            "version": "V13.4.19",
            "name": "Dynamic Universe Data Coverage Fix",
            "reason": "The data layer needs coverage repair before strategy tuning.",
        }
    if "liquidity_gate_blocking" in categories:
        return {
            "version": "V13.4.19",
            "name": "Liquidity Gate Calibration",
            "reason": "Liquidity filtering blocks candidates after probability scoring.",
        }
    return {
        "version": "V13.4.19",
        "name": "Manual Diagnosis Review",
        "reason": "No single automated root cause dominated the funnel.",
    }


def build_report(args: argparse.Namespace) -> DynamicRegimePipelineDiagnosisReport:
    warnings: list[str] = [
        "Diagnosis-only report. No backtest was run.",
        "No strategy rules, probability thresholds, bucket table, or execution settings were changed.",
        "Dry-run and live trading remain explicitly disabled.",
    ]
    expanded_report = _read_json(Path(args.expanded_report), warnings)
    dataset_report = _read_json(Path(args.probability_dataset_report), warnings)
    probability_table_raw = _read_json(Path(args.probability_table), warnings)
    universe_report = _read_json(Path(args.universe_report), warnings)

    score_rows = probability_table_raw if isinstance(probability_table_raw, list) else []
    bucket_performance = expanded_report.get("probabilityBucketPerformance", []) or []
    score_stats = _score_table_stats(score_rows)
    bucket_consistency = _bucket_key_consistency(score_rows, bucket_performance)
    probability_diagnosis = _probability_gate_diagnosis(
        expanded_report, dataset_report, score_rows, bucket_consistency
    )
    regime_diagnosis = _regime_router_diagnosis(expanded_report)
    module_diagnosis = _module_candidate_diagnosis(expanded_report)
    liquidity_diagnosis = _liquidity_gate_diagnosis(expanded_report)
    signal_funnel = _signal_funnel(expanded_report, universe_report, score_stats)
    root_causes = _root_causes(
        probability_diagnosis,
        bucket_consistency,
        regime_diagnosis,
        module_diagnosis,
        liquidity_diagnosis,
        score_stats,
        universe_report,
    )

    return DynamicRegimePipelineDiagnosisReport(
        reportId=REPORT_ID,
        sourceExpandedReport=str(Path(args.expanded_report)),
        sourceProbabilityTable=str(Path(args.probability_table)),
        currentStatus="diagnosis_only",
        dryRunApproved=False,
        liveTradingApproved=False,
        signalFunnel=signal_funnel,
        probabilityGateDiagnosis=probability_diagnosis,
        bucketKeyConsistency=bucket_consistency,
        regimeRouterDiagnosis=regime_diagnosis,
        moduleCandidateDiagnosis=module_diagnosis,
        liquidityGateDiagnosis=liquidity_diagnosis,
        rootCauseHypotheses=root_causes,
        recommendedNextStep=_recommended_next_step(root_causes),
        warnings=warnings,
        generatedAt=_utc_now(),
    )


def _summary(report: DynamicRegimePipelineDiagnosisReport) -> str:
    payload = report.to_dict()
    funnel = payload["signalFunnel"]
    probability = payload["probabilityGateDiagnosis"]
    consistency = payload["bucketKeyConsistency"]
    regime = payload["regimeRouterDiagnosis"]
    modules = payload["moduleCandidateDiagnosis"]
    liquidity = payload["liquidityGateDiagnosis"]
    root_causes = payload["rootCauseHypotheses"]
    next_step = payload["recommendedNextStep"]

    cause_lines = "\n".join(
        f"- {cause['category']}: {cause['likelihood']} - {cause['evidence']}"
        for cause in root_causes
    )
    missing_lines = "\n".join(
        f"- {row['bucketId']}: rows={row['rows']}"
        for row in probability.get("topMissingBucketKeysFromExpandedReport", [])[:10]
    )
    if not missing_lines:
        missing_lines = "- None from the expanded report top buckets."

    return f"""# AlphaPilot V13.4.18 Dynamic Regime Pipeline Diagnosis

Status: diagnosis only.

No backtest was run. No strategy rule, probability threshold, bucket table,
regime router, module rule, liquidity rule, Dry-run setting, API key, account
read, position read, order creation, or auto-trading path was changed.

## Signal Funnel

- Rows evaluated: {funnel['rowsEvaluated']}
- Rows with required data: {funnel['rowsWithRequiredData']}
- Trend module candidates: {funnel['trendModuleCandidates']}
- Mean-reversion module candidates: {funnel['meanReversionModuleCandidates']}
- Probability lookup hits: {funnel['probabilityLookupHits']}
- Probability lookup misses: {funnel['probabilityLookupMisses']}
- Probability score pass: {funnel['probabilityScorePass']}
- Final entry signals: {funnel['finalEntrySignals']}
- Actual trades: {funnel['actualTrades']}

## Probability Gate

- Lookup hit rate: {probability['lookupHitRatePercent']}%
- Probability pass rate: {probability['probabilityScorePassRatePercent']}%
- Score table buckets: {probability['scoreTableCoverage']['totalBuckets']}
- Sufficient sample buckets: {probability['scoreTableCoverage']['sufficientSampleBuckets']}
- Research candidate buckets: {probability['scoreTableCoverage']['researchCandidateBuckets']}
- Current-gate pass buckets: {probability['scoreTableCoverage']['currentGatePassBuckets']}

Top missing bucket keys from the expanded report:

{missing_lines}

## Bucket Key Consistency

- Score table rebuild mismatches: {consistency['scoreTableRebuildMismatchCount']}
- Expanded buckets checked: {consistency['expandedReportBucketsChecked']}
- Lookup hit buckets: {consistency['expandedReportLookupHitBuckets']}
- Lookup missing buckets: {consistency['expandedReportLookupMissingBuckets']}
- Format mismatch count: {consistency['expandedReportFormatMismatchCount']}
- Diagnosis: {consistency['diagnosis']}

## Regime Router

- Trend rows: {regime['trendRows']} ({regime['trendPercent']}%)
- Mean-reversion rows: {regime['meanReversionRows']} ({regime['meanReversionPercent']}%)
- Avoid rows: {regime['avoidRows']} ({regime['avoidPercent']}%)
- Unknown rows: {regime['unknownRows']} ({regime['unknownPercent']}%)
- Diagnosis: {regime['diagnosis']}

## Module Candidates

- Trend module candidate rate within trend: {modules['trendModuleCandidateRateWithinTrendPercent']}%
- Mean-reversion candidate rate within mean-reversion: {modules['meanReversionCandidateRateWithinMeanReversionPercent']}%
- Diagnosis: {modules['diagnosis']}

## Liquidity Gate

- Liquidity data available: {liquidity['liquidityDataAvailable']}
- Fallback used rows: {liquidity['fallbackUsedRows']}
- Effective rows after probability gate: {liquidity['effectiveRowsAfterProbabilityGate']}
- Diagnosis: {liquidity['diagnosis']}

## Root Cause Hypotheses

{cause_lines}

## Recommended Next Step

- Version: {next_step['version']}
- Name: {next_step['name']}
- Reason: {next_step['reason']}

## Safety Boundary

- dryRunApproved: false
- liveTradingApproved: false
- This report is research-only and must not be treated as a trading command.
"""


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expanded-report", default=str(DEFAULT_EXPANDED_REPORT))
    parser.add_argument("--expanded-summary", default=str(DEFAULT_EXPANDED_SUMMARY))
    parser.add_argument("--probability-table", default=str(DEFAULT_PROBABILITY_TABLE))
    parser.add_argument("--probability-dataset-report", default=str(DEFAULT_PROBABILITY_DATASET_REPORT))
    parser.add_argument("--universe-report", default=str(DEFAULT_UNIVERSE_REPORT))
    parser.add_argument("--universe-summary", default=str(DEFAULT_UNIVERSE_SUMMARY))
    parser.add_argument("--output-json", default=str(DEFAULT_OUTPUT_JSON))
    parser.add_argument("--output-summary", default=str(DEFAULT_OUTPUT_SUMMARY))
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    report = build_report(args)
    payload = report.to_dict()
    _write_json(Path(args.output_json), payload)
    _write_text(Path(args.output_summary), _summary(report))
    print(json.dumps({"report": args.output_json, "summary": args.output_summary}, indent=2))


if __name__ == "__main__":
    main()
