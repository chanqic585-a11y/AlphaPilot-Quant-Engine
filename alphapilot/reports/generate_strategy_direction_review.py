"""Generate V13.4.6 strategy direction review and V03 redesign artifacts.

This module reads local report files and writes research artifacts only. It
does not modify strategy code, run backtests, enter Dry-run, call exchange APIs,
read accounts, create orders, or auto trade.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from alphapilot.strategy_candidates.volume_rebound_v03_directions import (
    build_do_not_proceed_items,
    build_lessons_learned,
    build_v03_candidate_directions,
    build_v03_quality_gate,
)
from alphapilot.strategy_registry.strategy_status import write_strategy_status_archive

DEFAULT_REPORTS = {
    "expandedValidation": Path("reports/v13_4_5_expanded_validation_report.json"),
    "expandedSummary": Path("reports/v13_4_5_expanded_validation_summary.md"),
    "comparativeBacktest": Path("reports/v13_4_4_comparative_backtest_report.json"),
    "candidateMatrix": Path("reports/v13_4_3_v02_candidate_matrix.json"),
    "signalAudit": Path("reports/v13_4_2_signal_audit_report.json"),
    "diagnosis": Path("reports/v13_4_1_diagnosis_report.json"),
}
DEFAULT_OUTPUT_JSON = Path("reports/v13_4_6_strategy_direction_review.json")
DEFAULT_OUTPUT_SUMMARY = Path("reports/v13_4_6_strategy_direction_summary.md")
DEFAULT_STATUS_ARCHIVE = Path("reports/v13_4_6_strategy_status_archive.json")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path, warnings: list[str]) -> dict[str, Any]:
    if not path.exists():
        warnings.append(f"Missing input report: {path}")
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        warnings.append(f"Unable to parse JSON report {path}: {exc}")
        return {}


def _read_text(path: Path, warnings: list[str]) -> str:
    if not path.exists():
        warnings.append(f"Missing input summary: {path}")
        return "unavailable"
    return path.read_text(encoding="utf-8")


def _source_reports(report_map: dict[str, Path], data: dict[str, Any], summary_available: bool) -> list[dict[str, Any]]:
    rows = []
    for key, path in report_map.items():
        if key == "expandedSummary":
            rows.append(
                {
                    "key": key,
                    "path": str(path),
                    "exists": path.exists(),
                    "reportId": "markdown_summary" if summary_available else "unavailable",
                }
            )
            continue
        payload = data.get(key, {})
        rows.append(
            {
                "key": key,
                "path": str(path),
                "exists": path.exists(),
                "reportId": payload.get("reportId", "unavailable") if isinstance(payload, dict) else "unavailable",
            }
        )
    return rows


def _find_row(rows: list[dict[str, Any]] | None, strategy: str) -> dict[str, Any]:
    if not isinstance(rows, list):
        return {}
    for row in rows:
        if isinstance(row, dict) and row.get("strategy") == strategy:
            return row
    return {}


def _find_by_key(rows: list[dict[str, Any]] | None, key: str, value: str) -> dict[str, Any]:
    if not isinstance(rows, list):
        return {}
    for row in rows:
        if isinstance(row, dict) and row.get(key) == value:
            return row
    return {}


def _safe(value: Any) -> Any:
    return "unavailable" if value is None else value


def _build_failure_summary(
    expanded: dict[str, Any],
    comparative: dict[str, Any],
    signal_audit: dict[str, Any],
    diagnosis: dict[str, Any],
) -> dict[str, Any]:
    raw_rows = expanded.get("rawComparisonTable", [])
    adjusted_rows = expanded.get("slippageAdjustedComparisonTable", [])
    comparison_rows = comparative.get("comparisonTable", [])
    diagnosis_overall = diagnosis.get("overall", {})
    signal_overall = signal_audit.get("overall", {})
    top_skips = signal_audit.get("skipReasonCounts", [])
    weak_4h = _find_by_key(top_skips, "skipReason", "weak_4h_trend")
    sol_pair = _find_by_key(diagnosis.get("pairBreakdown"), "pair", "SOL/USDT:USDT")
    stop_loss = _find_by_key(diagnosis.get("exitReasonBreakdown"), "exitReason", "stop_loss")
    macd_weak = _find_by_key(
        diagnosis.get("exitReasonBreakdown"),
        "exitReason",
        "macd_histogram_two_candle_weakness",
    )

    return {
        "decision": {
            "strategyFamilyStatus": "rejected_for_dry_run",
            "dryRunApproved": False,
            "liveTradingApproved": False,
            "reason": "Expanded validation and slippage-adjusted metrics remain deeply negative across V0.1/V0.2.",
        },
        "expandedValidation": {
            "rawComparisonTable": raw_rows,
            "slippageAdjustedComparisonTable": adjusted_rows,
            "bestRawCandidate": expanded.get("bestRawCandidate", "unavailable"),
            "bestSlippageAdjustedCandidate": expanded.get("bestSlippageAdjustedCandidate", "unavailable"),
            "supportedPairs": expanded.get("supportedPairs", []),
            "excludedPairs": expanded.get("excludedPairs", []),
        },
        "smokeComparisonContext": {
            "comparisonTable": comparison_rows,
            "dryRunApproved": comparative.get("dryRunApproved", "unavailable"),
            "bestCandidate": comparative.get("bestCandidate", "unavailable"),
            "interpretation": "A/B/C/E improved relatively in smoke comparison, but every candidate remained negative.",
        },
        "tradeFrequencyProblem": {
            "top30SixMonthTradeCounts": {
                row.get("strategy", "unknown"): row.get("tradeCount", "unavailable")
                for row in raw_rows
                if isinstance(row, dict)
            },
            "analysis": [
                "V01, C, and E each produced roughly 2,500-2,700 trades on Top30 six-month validation.",
                "B reduced trades to 1,515 but remained deeply negative after slippage.",
                "15m signal density appears noisy and likely amplifies fee/slippage drag.",
                "V03 should prefer fewer, higher-quality signals.",
            ],
        },
        "costProblem": {
            "feesPaidRaw": {
                row.get("strategy", "unknown"): _safe(row.get("feesPaid"))
                for row in raw_rows
                if isinstance(row, dict)
            },
            "slippageCost": {
                row.get("strategy", "unknown"): _safe(row.get("totalSlippageCost"))
                for row in adjusted_rows
                if isinstance(row, dict)
            },
            "analysis": [
                "Every candidate became worse after slippage post-processing.",
                "The strategy family is cost-sensitive because trade count is high and edge per trade is weak.",
                "V03 must either reduce trade frequency, increase target expectancy, or both.",
            ],
        },
        "payoffProblem": {
            "currentStopLoss": "-3%",
            "currentTakeProfit": "+3%",
            "diagnosisWinRate": diagnosis_overall.get("winRate", "unavailable"),
            "expandedWinRates": {
                row.get("strategy", "unknown"): row.get("winRate", row.get("slippageAdjustedWinRate", "unavailable"))
                for row in raw_rows
                if isinstance(row, dict)
            },
            "analysis": [
                "A roughly 1:1 payoff structure is not enough with win rate near the low-40% range.",
                "After fees and slippage, the strategy needs materially higher win rate or higher reward/risk.",
                "V03 should test at least 1.5R or 2R concepts before any controlled execution discussion.",
            ],
        },
        "entryQualityProblem": {
            "signalAuditOverall": signal_overall,
            "analysis": [
                "The volumeRatio, RSI, MACD, EMA20 reclaim, and broad 4h trend combination did not identify positive-expectancy entries.",
                "The expanded results suggest the failure is structural, not a single threshold issue.",
                "V03 should require stronger structure confirmation before entry.",
            ],
        },
        "trendFilterProblem": {
            "weak4hTrendSkipReason": weak_4h or "unavailable",
            "analysis": [
                "The 4h trend filter blocks many weak contexts and is useful as a guardrail.",
                "Passing the current 4h filter is not sufficient; trades that passed still lost overall.",
                "V03 should not rely on 4h EMA filtering alone.",
            ],
        },
        "pairRiskProblem": {
            "solSmokeDiagnosis": sol_pair or "unavailable",
            "analysis": [
                "SOL contributed heavily to the smoke-sample loss, showing pair-level risk can drag the portfolio.",
                "A single smoke result is not enough to permanently exclude SOL.",
                "V03 should add pair-level exposure caps, signal caps, and risk watchlists.",
            ],
        },
        "exitLossContext": {
            "stopLoss": stop_loss or "unavailable",
            "macdWeakness": macd_weak or "unavailable",
            "analysis": [
                "Stop-loss and MACD weakness exits were major smoke-sample loss buckets.",
                "The expanded failure shows exit cleanup alone is not enough to fix the strategy family.",
            ],
        },
    }


def build_strategy_direction_review(report_paths: dict[str, Path]) -> dict[str, Any]:
    warnings: list[str] = []
    expanded_summary_text = _read_text(report_paths["expandedSummary"], warnings)
    input_data = {
        "expandedValidation": _read_json(report_paths["expandedValidation"], warnings),
        "comparativeBacktest": _read_json(report_paths["comparativeBacktest"], warnings),
        "candidateMatrix": _read_json(report_paths["candidateMatrix"], warnings),
        "signalAudit": _read_json(report_paths["signalAudit"], warnings),
        "diagnosis": _read_json(report_paths["diagnosis"], warnings),
    }
    timestamp = _utc_now()
    failure_summary = _build_failure_summary(
        input_data["expandedValidation"],
        input_data["comparativeBacktest"],
        input_data["signalAudit"],
        input_data["diagnosis"],
    )
    if "All candidates remain negative after slippage" not in expanded_summary_text:
        warnings.append("Expanded validation summary did not include the expected all-negative slippage conclusion text.")

    return {
        "reportId": "v13_4_6_strategy_direction_review",
        "sourceReports": _source_reports(report_paths, input_data, expanded_summary_text != "unavailable"),
        "currentStrategyFamily": "alpha_volume_rebound_v01_v02",
        "dryRunApproved": False,
        "liveTradingApproved": False,
        "strategyFamilyStatus": "rejected_for_dry_run",
        "researchStatus": "failed_research_current_sample",
        "failureSummary": failure_summary,
        "lessonsLearned": build_lessons_learned(),
        "v03CandidateDirections": build_v03_candidate_directions(),
        "v03QualityGate": build_v03_quality_gate(),
        "doNotProceed": build_do_not_proceed_items(),
        "requiredConclusions": [
            "Volume Rebound V0.1/V0.2 current series must not enter Dry-run.",
            "B/C/E improved relatively in some comparisons but remain unusable after expanded validation and slippage.",
            "The failure is not a single-parameter issue.",
            "Continuing minor edits inside the current framework has high overfitting risk.",
            "V03 should redesign entry quality, trade frequency, payoff structure, and risk controls.",
        ],
        "nextStepRecommendation": "V13.4.7 - V03 Candidate Selection and Specification",
        "warnings": warnings,
        "generatedAt": timestamp,
        "source": "alphapilot_v13_4_6_strategy_direction_review",
    }


def _write_summary(report: dict[str, Any], path: Path) -> None:
    failure = report["failureSummary"]
    expanded = failure["expandedValidation"]
    lines = [
        "# V13.4.6 Strategy Direction Summary",
        "",
        "## Decision",
        "",
        "- Volume Rebound V0.1/V0.2 current series is rejected for Dry-run.",
        f"- dryRunApproved: {report['dryRunApproved']}",
        f"- strategyFamilyStatus: {report['strategyFamilyStatus']}",
        "- This is a strategy direction review only. It does not run backtests, enter Dry-run, or modify strategy code.",
        "",
        "## Current V0.1/V0.2 Summary",
        "",
        f"- Best raw candidate in V13.4.5: {expanded.get('bestRawCandidate')}",
        f"- Best slippage-adjusted candidate in V13.4.5: {expanded.get('bestSlippageAdjustedCandidate')}",
        "- B/C/E were relative improvements in limited contexts, but absolute performance remains deeply negative.",
        "- D was eliminated in V13.4.4 comparison and was not part of expanded validation.",
        "",
        "### Raw Expanded Validation",
        "",
        "| Strategy | Return % | Drawdown % | Profit Factor | Trades | Win Rate % |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in expanded.get("rawComparisonTable", []):
        lines.append(
            f"| {row.get('strategy')} | {row.get('totalReturnPct')} | {row.get('maxDrawdownPct')} | "
            f"{row.get('profitFactor')} | {row.get('tradeCount')} | {row.get('winRate')} |"
        )
    lines.extend(
        [
            "",
            "### Slippage-Adjusted Expanded Validation",
            "",
            "| Strategy | Adj Return % | Adj DD % | Adj PF | Trades | Slippage Cost | Gate |",
            "|---|---:|---:|---:|---:|---:|---|",
        ]
    )
    for row in expanded.get("slippageAdjustedComparisonTable", []):
        lines.append(
            f"| {row.get('strategy')} | {row.get('slippageAdjustedTotalReturnPct')} | "
            f"{row.get('maxDrawdownPct')} | {row.get('slippageAdjustedProfitFactor')} | "
            f"{row.get('tradeCount')} | {row.get('totalSlippageCost')} | {row.get('passedExpandedGate')} |"
        )
    lines.extend(
        [
            "",
            "## Why Minor Tuning Should Stop",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in report["lessonsLearned"])
    lines.extend(
        [
            "",
            "## Core Failure Reasons",
            "",
            "### Trade Frequency",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in failure["tradeFrequencyProblem"]["analysis"])
    lines.extend(["", "### Cost Sensitivity", ""])
    lines.extend(f"- {item}" for item in failure["costProblem"]["analysis"])
    lines.extend(["", "### Payoff Structure", ""])
    lines.extend(f"- {item}" for item in failure["payoffProblem"]["analysis"])
    lines.extend(["", "### Entry Quality", ""])
    lines.extend(f"- {item}" for item in failure["entryQualityProblem"]["analysis"])
    lines.extend(["", "### Trend Filter", ""])
    lines.extend(f"- {item}" for item in failure["trendFilterProblem"]["analysis"])
    lines.extend(["", "### SOL / Pair Risk", ""])
    lines.extend(f"- {item}" for item in failure["pairRiskProblem"]["analysis"])
    lines.extend(["", "## V03 Candidate Directions", ""])
    for candidate in report["v03CandidateDirections"]:
        lines.extend(
            [
                f"### {candidate['name']}",
                "",
                f"- Positioning: {candidate['positioning']}",
                f"- Core idea: {candidate['coreIdea']}",
                "- Rule direction:",
            ]
        )
        lines.extend(f"  - {item}" for item in candidate["ruleDirection"])
        lines.append("- Risks:")
        lines.extend(f"  - {item}" for item in candidate["risks"])
        lines.append("")
    lines.extend(
        [
            "## V03 Quality Gate",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in report["v03QualityGate"]["minimumRequirements"])
    lines.extend(["", "## Do Not Proceed", ""])
    lines.extend(f"- {item}" for item in report["doNotProceed"])
    lines.extend(
        [
            "",
            "## Next Step",
            "",
            report["nextStepRecommendation"],
            "",
            "## Safety",
            "",
            "V13.4.6 reads local reports and writes research artifacts only. It does not modify V0.1/V0.2 strategy code, run backtests, enter Dry-run, use API keys, call Trade API or Withdraw API, read accounts, create orders, or auto trade.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def export_strategy_direction_review(
    report_paths: dict[str, Path],
    output_json: Path,
    output_summary: Path,
    status_archive: Path,
) -> tuple[Path, Path, Path]:
    report = build_strategy_direction_review(report_paths)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_summary(report, output_summary)
    write_strategy_status_archive(status_archive, report["generatedAt"])
    return output_json, output_summary, status_archive


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate V13.4.6 strategy direction review.")
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-summary", type=Path, default=DEFAULT_OUTPUT_SUMMARY)
    parser.add_argument("--status-archive", type=Path, default=DEFAULT_STATUS_ARCHIVE)
    args = parser.parse_args()

    output_json, output_summary, status_archive = export_strategy_direction_review(
        DEFAULT_REPORTS,
        args.output_json,
        args.output_summary,
        args.status_archive,
    )
    print(f"Exported strategy direction review: {output_json}")
    print(f"Exported strategy direction summary: {output_summary}")
    print(f"Exported strategy status archive: {status_archive}")


if __name__ == "__main__":
    main()
