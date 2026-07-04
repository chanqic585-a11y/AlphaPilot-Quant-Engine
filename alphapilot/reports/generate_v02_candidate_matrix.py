"""Generate V13.4.3 V0.2 strategy candidate matrix.

The generator reads local V13.4.1 and V13.4.2 reports only. It does not modify
strategy parameters, run backtests, enter dry-run, call exchange APIs, or place
orders.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from alphapilot.strategy_candidates.candidate_schema import CandidateMatrixReport
from alphapilot.strategy_candidates.volume_rebound_v02_candidates import (
    build_volume_rebound_v02_candidates,
    do_not_change_yet,
    recommended_comparison_plan,
)

DEFAULT_DIAGNOSIS = Path("reports/v13_4_1_diagnosis_report.json")
DEFAULT_SIGNAL_AUDIT = Path("reports/v13_4_2_signal_audit_report.json")
DEFAULT_OUTPUT_JSON = Path("reports/v13_4_3_v02_candidate_matrix.json")
DEFAULT_OUTPUT_SUMMARY = Path("reports/v13_4_3_v02_candidate_summary.md")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_get(mapping: dict[str, Any] | None, key: str, default: Any = "unavailable") -> Any:
    if not isinstance(mapping, dict):
        return default
    value = mapping.get(key, default)
    return default if value is None else value


def _find_by_key(rows: list[dict[str, Any]] | None, key: str, value: str) -> dict[str, Any]:
    if not isinstance(rows, list):
        return {}
    for row in rows:
        if isinstance(row, dict) and row.get(key) == value:
            return row
    return {}


def _max_by(rows: list[dict[str, Any]] | None, key: str, *, reverse: bool = False) -> dict[str, Any]:
    if not isinstance(rows, list) or not rows:
        return {}
    clean = [row for row in rows if isinstance(row, dict) and isinstance(row.get(key), (int, float))]
    if not clean:
        return {}
    return max(clean, key=lambda row: row[key]) if reverse else min(clean, key=lambda row: row[key])


def _extract_evidence(diagnosis: dict[str, Any], signal_audit: dict[str, Any]) -> dict[str, Any]:
    overall = diagnosis.get("overall", {})
    audit_overall = signal_audit.get("overall", {})
    sol_pair = _find_by_key(diagnosis.get("pairBreakdown"), "pair", "SOL/USDT:USDT")
    sol_audit = _find_by_key(signal_audit.get("pairBreakdown"), "pair", "SOL/USDT:USDT")
    stop_loss = _find_by_key(diagnosis.get("exitReasonBreakdown"), "exitReason", "stop_loss")
    macd_weak = _find_by_key(
        diagnosis.get("exitReasonBreakdown"),
        "exitReason",
        "macd_histogram_two_candle_weakness",
    )
    weakest_holding = _max_by(diagnosis.get("holdingTimeBreakdown"), "netProfit", reverse=False)
    top_skip = _max_by(
        [row for row in signal_audit.get("skipReasonCounts", []) if row.get("skipReason") != "entry_signal_passed"],
        "count",
        reverse=True,
    )
    volume_filter = _find_by_key(signal_audit.get("filterStats"), "filterId", "volume_filter")
    no_chase = _find_by_key(signal_audit.get("filterStats"), "filterId", "no_chase_filter")
    trend_filter = _find_by_key(signal_audit.get("filterStats"), "filterId", "4h_trend_filter")
    cost = diagnosis.get("costAnalysis", {})

    return {
        "totalTrades": _safe_get(overall, "totalTrades"),
        "winRate": _safe_get(overall, "winRate"),
        "totalReturnPct": _safe_get(overall, "totalReturnPct"),
        "maxDrawdownPct": _safe_get(overall, "maxDrawdownPct"),
        "profitFactor": _safe_get(overall, "profitFactor"),
        "maxConsecutiveLosses": _safe_get(overall, "maxConsecutiveLosses"),
        "averageHoldingMinutes": _safe_get(overall, "averageHoldingMinutes"),
        "finalEntryCount": _safe_get(audit_overall, "finalEntryCount"),
        "actualTradeCount": _safe_get(audit_overall, "actualTradeCount"),
        "filterEffectivenessAvailable": _safe_get(audit_overall, "filterEffectivenessAvailable"),
        "topSkipReason": {
            "skipReason": _safe_get(top_skip, "skipReason"),
            "count": _safe_get(top_skip, "count"),
            "percentage": _safe_get(top_skip, "percentage"),
        },
        "trendPrimaryBlocks": _safe_get(trend_filter, "blockedAsPrimaryReason"),
        "volumePrimaryBlocks": _safe_get(volume_filter, "blockedAsPrimaryReason"),
        "noChasePrimaryBlocks": _safe_get(no_chase, "blockedAsPrimaryReason"),
        "largestPairLoss": {
            "pair": _safe_get(sol_pair, "pair"),
            "totalProfit": _safe_get(sol_pair, "totalProfit"),
            "profitFactor": _safe_get(sol_pair, "profitFactor"),
            "tradeCount": _safe_get(sol_pair, "tradeCount"),
        },
        "solSignalTradeCounts": {
            "finalEntryCount": _safe_get(sol_audit, "finalEntryCount"),
            "actualTradeCount": _safe_get(sol_audit, "actualTradeCount"),
        },
        "solProfitFactor": _safe_get(sol_pair, "profitFactor"),
        "stopLossNetProfit": _safe_get(stop_loss, "netProfit"),
        "stopLossTradeCount": _safe_get(stop_loss, "tradeCount"),
        "macdWeakExitNetProfit": _safe_get(macd_weak, "netProfit"),
        "macdWeakExitTradeCount": _safe_get(macd_weak, "tradeCount"),
        "weakestHoldingBucket": {
            "bucket": _safe_get(weakest_holding, "bucket"),
            "netProfit": _safe_get(weakest_holding, "netProfit"),
            "tradeCount": _safe_get(weakest_holding, "tradeCount"),
        },
        "estimatedFeesPaid": _safe_get(cost, "estimatedFeesPaidFromOrders"),
        "slippageApplied": _safe_get(cost, "slippageApplied"),
    }


def _validate_inputs(diagnosis: dict[str, Any], signal_audit: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    if diagnosis.get("isMock") is not False:
        warnings.append("Diagnosis report is not marked isMock=false.")
    if signal_audit.get("isMock") is not False:
        warnings.append("Signal audit report is not marked isMock=false.")
    if signal_audit.get("overall", {}).get("filterEffectivenessAvailable") is not True:
        warnings.append("Signal audit filter effectiveness is unavailable.")
    required_diagnosis = ["overall", "pairBreakdown", "exitReasonBreakdown", "holdingTimeBreakdown", "costAnalysis"]
    required_audit = ["overall", "filterStats", "skipReasonCounts", "pairBreakdown"]
    for key in required_diagnosis:
        if key not in diagnosis:
            warnings.append(f"Diagnosis report missing field: {key}")
    for key in required_audit:
        if key not in signal_audit:
            warnings.append(f"Signal audit report missing field: {key}")
    return warnings


def build_candidate_matrix(diagnosis_path: Path, signal_audit_path: Path) -> CandidateMatrixReport:
    diagnosis = _read_json(diagnosis_path)
    signal_audit = _read_json(signal_audit_path)
    warnings = _validate_inputs(diagnosis, signal_audit)
    evidence = _extract_evidence(diagnosis, signal_audit)
    candidates = build_volume_rebound_v02_candidates(evidence)

    return CandidateMatrixReport(
        reportId="v13_4_3_v02_candidate_matrix",
        sourceDiagnosis=str(diagnosis_path),
        sourceSignalAudit=str(signal_audit_path),
        strategyId=str(diagnosis.get("strategyId") or signal_audit.get("strategyId") or "alpha_volume_rebound_v01"),
        currentStatus={
            "dryRunApproved": False,
            "liveTradingApproved": False,
            "reason": "V0.1 smoke backtest is negative and requires V0.2 comparative testing.",
            "baseline": {
                "totalReturnPct": evidence.get("totalReturnPct"),
                "maxDrawdownPct": evidence.get("maxDrawdownPct"),
                "profitFactor": evidence.get("profitFactor"),
                "maxConsecutiveLosses": evidence.get("maxConsecutiveLosses"),
            },
        },
        evidenceSummary=evidence,
        candidates=candidates,
        recommendedComparisonPlan=recommended_comparison_plan(),
        doNotChangeYet=do_not_change_yet(),
        warnings=warnings,
        generatedAt=_utc_now(),
    )


def _write_summary(report: dict[str, Any], path: Path) -> None:
    evidence = report["evidenceSummary"]
    lines = [
        "# V13.4.3 V0.2 Candidate Summary",
        "",
        "## Current V0.1 Conclusion",
        "",
        "V0.1 is not approved for Dry-run or live trading.",
        "",
        "Baseline evidence:",
        "",
        f"- Total return: {evidence.get('totalReturnPct')}",
        f"- Max drawdown: {evidence.get('maxDrawdownPct')}",
        f"- Profit factor: {evidence.get('profitFactor')}",
        f"- Max consecutive losses: {evidence.get('maxConsecutiveLosses')}",
        f"- Final entries / actual trades: {evidence.get('finalEntryCount')} / {evidence.get('actualTradeCount')}",
        "",
        "## Why Dry-run Is Blocked",
        "",
        "- V13.4 smoke backtest is negative.",
        "- Profit factor is below 1.",
        "- Drawdown and loss streak are too high for a controlled execution path.",
        "- V13.4.3 only creates candidate designs for V13.4.4 comparison.",
        "",
        "## Evidence Summary",
        "",
        f"- Top skip reason: {evidence.get('topSkipReason')}",
        f"- SOL pair evidence: {evidence.get('largestPairLoss')}",
        f"- SOL signal/trade count: {evidence.get('solSignalTradeCounts')}",
        f"- Stop-loss net profit: {evidence.get('stopLossNetProfit')}",
        f"- MACD weakness exit net profit: {evidence.get('macdWeakExitNetProfit')}",
        f"- Weakest holding bucket: {evidence.get('weakestHoldingBucket')}",
        f"- Estimated fees paid: {evidence.get('estimatedFeesPaid')}",
        f"- Slippage applied in V13.4: {evidence.get('slippageApplied')}",
        "",
        "## Candidate Matrix",
        "",
    ]
    for candidate in report["candidates"]:
        lines.extend(
            [
                f"### {candidate['name']}",
                "",
                candidate["description"],
                "",
                "Proposed changes:",
                "",
            ]
        )
        lines.extend(f"- {item}" for item in candidate["proposedChanges"])
        lines.extend(["", "Expected impact:", ""])
        lines.extend(f"- {item}" for item in candidate["expectedImpact"])
        lines.extend(["", "Risks:", ""])
        lines.extend(f"- {item}" for item in candidate["risks"])
        lines.extend(["", "What to test:", ""])
        lines.extend(f"- {item}" for item in candidate["whatToTest"])
        lines.append("")

    lines.extend(["## V13.4.4 Comparison Plan", ""])
    for item in report["recommendedComparisonPlan"]:
        lines.append(f"- Step {item['step']}: {item['variant']} - {item['purpose']}")
    lines.extend(["", "Comparison must include return, drawdown, profit factor, trade count, win rate, loss streak, pair/month performance, exit reason losses, fees, and slippage-adjusted net return.", ""])
    lines.extend(["## Do Not Change Yet", ""])
    lines.extend(f"- {item}" for item in report["doNotChangeYet"])
    lines.extend(
        [
            "",
            "## Safety",
            "",
            "V13.4.3 does not modify V0.1 strategy logic, change config defaults, run Dry-run, call Trade API or Withdraw API, save API keys, read accounts, create orders, or auto trade.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def export_candidate_matrix(
    diagnosis_path: Path,
    signal_audit_path: Path,
    output_json: Path,
    output_summary: Path,
) -> tuple[Path, Path]:
    report = build_candidate_matrix(diagnosis_path, signal_audit_path).to_dict()
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_summary(report, output_summary)
    return output_json, output_summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate AlphaPilot V13.4.3 V0.2 candidate matrix.")
    parser.add_argument("--diagnosis", type=Path, default=DEFAULT_DIAGNOSIS)
    parser.add_argument("--signal-audit", type=Path, default=DEFAULT_SIGNAL_AUDIT)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-summary", type=Path, default=DEFAULT_OUTPUT_SUMMARY)
    args = parser.parse_args()

    output_json, output_summary = export_candidate_matrix(
        args.diagnosis,
        args.signal_audit,
        args.output_json,
        args.output_summary,
    )
    print(f"Exported V0.2 candidate matrix: {output_json}")
    print(f"Exported V0.2 candidate summary: {output_summary}")


if __name__ == "__main__":
    main()
