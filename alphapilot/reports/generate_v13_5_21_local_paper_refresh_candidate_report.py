"""Generate V13.5.21 local paper refresh candidate report.

This report packages the V13.5.20 selected signals into the existing local
paper sandbox ledger. It validates local simulation mechanics only. It does not
connect to exchanges, use API keys, create orders, or auto trade.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from alphapilot.paper_sandbox.local_paper_ledger import LocalPaperSandboxConfig, simulate_local_paper_ledger
from alphapilot.reports.generate_v13_5_derivatives_ml_strategy_report import _json_ready, write_json, write_text


VERSION = "V13.5.21"
REPORT_ID = "v13_5_21_local_paper_refresh_candidate_report"
DEFAULT_DECISION_REPORT = Path("reports/v13_5_20_exit_aware_loss_cooldown_report.json")
DEFAULT_SELECTED_SIGNALS = Path("reports/v13_5_20_best_exit_aware_policy_selected_signals.json")
DEFAULT_OUTPUT_REPORT = Path("reports/v13_5_21_local_paper_refresh_candidate_report.json")
DEFAULT_OUTPUT_SUMMARY = Path("reports/v13_5_21_local_paper_refresh_candidate_summary.md")
DEFAULT_OUTPUT_LEDGER = Path("reports/v13_5_21_local_paper_refresh_candidate_ledger.json")
DEFAULT_OUTPUT_PACKAGE = Path("reports/v13_5_21_local_paper_refresh_candidate_package.json")


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _parse_stop_loss_from_candidate(candidate_id: str, fallback: float = 0.06) -> float:
    for part in candidate_id.split(":"):
        if part.startswith("sl"):
            try:
                return float(part[2:])
            except ValueError:
                return fallback
    return fallback


def _gate(metrics: dict[str, Any]) -> dict[str, Any]:
    skipped = metrics.get("skippedSignalCount") or 0
    filled = metrics.get("filledSignalCount") or 0
    total = skipped + filled
    skipped_rate = (skipped / total * 100) if total else 100
    checks = {
        "minFilledSignals300": filled >= 300,
        "maxSkippedRate5Pct": skipped_rate <= 5,
        "minProfitFactor1_5": (metrics.get("profitFactor") or 0) >= 1.5,
        "minRewardRisk1_8": (metrics.get("rewardRiskRatio") or 0) >= 1.8,
        "maxDrawdown20Pct": (metrics.get("maxDrawdownPct") or 999) <= 20,
        "positiveTotalReturn": (metrics.get("totalReturnPct") or 0) > 0,
    }
    return {
        "checks": checks,
        "passed": all(checks.values()),
        "skippedRatePct": round(skipped_rate, 6),
        "meaning": "Local paper refresh mechanics gate only, not exchange Dry-run approval.",
    }


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _candidate_ids(signals: list[dict[str, Any]]) -> list[str]:
    return sorted({str(row.get("candidateId")) for row in signals if row.get("candidateId")})


def _simulate(
    signals: list[dict[str, Any]],
    approved_candidate_ids: list[str],
    stop_loss_pct: float,
    max_concurrent_positions: int,
    source: str,
) -> dict[str, Any]:
    config = LocalPaperSandboxConfig(
        initial_equity=10_000.0,
        risk_per_signal_pct=1.0,
        max_concurrent_positions=max_concurrent_positions,
        max_notional_per_signal_pct=35.0,
        stop_loss_pct=stop_loss_pct,
        source=source,
    )
    return simulate_local_paper_ledger(signals, approved_candidate_ids, config)


def _sensitivity(
    signals: list[dict[str, Any]],
    approved_candidate_ids: list[str],
    stop_loss_pct: float,
) -> list[dict[str, Any]]:
    rows = []
    for cap in [3, 5, 8, 12, 999]:
        ledger = _simulate(
            signals,
            approved_candidate_ids,
            stop_loss_pct,
            cap,
            source=f"local_paper_refresh_candidate_v13_5_21_cap_{cap}",
        )
        metrics = ledger["metrics"]
        rows.append(
            {
                "maxConcurrentPositions": cap,
                "gate": _gate(metrics),
                "metrics": metrics,
            }
        )
    return rows


def _summary_markdown(report: dict[str, Any]) -> str:
    metrics = report["ledgerMetrics"]
    decision = report["decision"]
    lines = [
        "# AlphaPilot V13.5.21 Local Paper Refresh Candidate",
        "",
        "This report packages V13.5.20 selected signals into the local paper sandbox ledger.",
        "It is local simulation only and does not create exchange orders.",
        "",
        "## Candidate",
        "",
        f"- candidateId: {report['candidatePackage']['candidateId']}",
        f"- selectedPolicyId: {report['candidatePackage']['selectedPolicyId']}",
        f"- stopLossPct: {report['candidatePackage']['stopLossPct']}",
        f"- targetRMultiple: {report['candidatePackage']['targetRMultiple']}",
        f"- maxConcurrentPositions: {report['ledgerConfig']['max_concurrent_positions']}",
        "",
        "## Ledger Metrics",
        "",
        f"- filledSignalCount: {metrics.get('filledSignalCount')}",
        f"- skippedSignalCount: {metrics.get('skippedSignalCount')}",
        f"- winRatePct: {metrics.get('winRatePct')}",
        f"- profitFactor: {metrics.get('profitFactor')}",
        f"- rewardRiskRatio: {metrics.get('rewardRiskRatio')}",
        f"- totalReturnPct: {metrics.get('totalReturnPct')}",
        f"- maxDrawdownPct: {metrics.get('maxDrawdownPct')}",
        f"- finalEquity: {metrics.get('finalEquity')}",
        "",
        "## Concurrency Sensitivity",
        "",
    ]
    for row in report["sensitivityResults"]:
        metric = row["metrics"]
        lines.append(
            f"- cap={row['maxConcurrentPositions']}: filled={metric.get('filledSignalCount')}, "
            f"skipped={metric.get('skippedSignalCount')}, pf={metric.get('profitFactor')}, "
            f"rr={metric.get('rewardRiskRatio')}, dd={metric.get('maxDrawdownPct')}, "
            f"passed={row['gate']['passed']}"
        )
    lines.extend(
        [
            "",
            "## Decision",
            "",
            f"- localPaperRefreshCandidateReady: {decision['localPaperRefreshCandidateReady']}",
            f"- localPaperMechanicsPassed: {decision['localPaperMechanicsPassed']}",
            f"- readyForExchangeDryRunReview: {decision['readyForExchangeDryRunReview']}",
            f"- nextAction: {decision['nextAction']}",
            "",
            "## Safety Boundary",
            "",
            "- Local simulated capital only.",
            "- No Trade API.",
            "- No Withdraw API.",
            "- No API key storage.",
            "- No real account reads.",
            "- No real position reads.",
            "- No order creation.",
            "- No automatic trading.",
            "- No exchange Dry-run approval.",
            "- No live-trading approval.",
        ]
    )
    return "\n".join(lines) + "\n"


def generate_report(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    decision_report = _read_json(args.decision_report)
    selected_signals = _read_json(args.selected_signals)
    approved_candidate_ids = _candidate_ids(selected_signals)
    candidate_id = approved_candidate_ids[0] if approved_candidate_ids else "unknown"
    stop_loss_pct = _parse_stop_loss_from_candidate(candidate_id)
    selected_policy_id = decision_report.get("bestPolicy", {}).get("policyId")
    ledger = _simulate(
        selected_signals,
        approved_candidate_ids,
        stop_loss_pct,
        args.max_concurrent_positions,
        source="local_paper_refresh_candidate_v13_5_21",
    )
    metrics = ledger["metrics"]
    gate = _gate(metrics)
    sensitivity_results = _sensitivity(selected_signals, approved_candidate_ids, stop_loss_pct)
    package = {
        "version": VERSION,
        "packageId": "v13_5_21_local_paper_refresh_candidate_package",
        "generatedAt": utc_now(),
        "candidateId": candidate_id,
        "selectedPolicyId": selected_policy_id,
        "sourceSelectedSignals": str(args.selected_signals),
        "sourceDecisionReport": str(args.decision_report),
        "selectedSignalCount": len(selected_signals),
        "stopLossPct": stop_loss_pct,
        "targetRMultiple": decision_report.get("targetRMultipleUnchanged", 2.0),
        "maxConcurrentPositions": args.max_concurrent_positions,
        "riskPerSignalPct": ledger["config"]["risk_per_signal_pct"],
        "maxNotionalPerSignalPct": ledger["config"]["max_notional_per_signal_pct"],
        "localSimulationOnly": True,
        "exchangeDryRunApproved": False,
        "liveTradingApproved": False,
    }
    report = {
        "version": VERSION,
        "reportId": REPORT_ID,
        "generatedAt": utc_now(),
        "status": "completed",
        "inputReports": {
            "decisionReport": str(args.decision_report),
            "selectedSignals": str(args.selected_signals),
        },
        "candidatePackage": package,
        "ledgerConfig": ledger["config"],
        "ledgerMetrics": metrics,
        "gate": gate,
        "sensitivityResults": sensitivity_results,
        "ledgerPath": str(args.output_ledger),
        "candidatePackagePath": str(args.output_package),
        "decision": {
            "localPaperRefreshCandidateReady": bool(gate["passed"]),
            "localPaperMechanicsPassed": bool(gate["passed"]),
            "readyForExchangeDryRunReview": False,
            "exchangeDryRunApproved": False,
            "liveTradingApproved": False,
            "reason": (
                "local_paper_refresh_candidate_packaged_and_mechanics_passed"
                if gate["passed"]
                else "local_paper_refresh_candidate_packaged_but_mechanics_gate_failed"
            ),
            "nextAction": (
                "run_forward_readiness_when_new_closed_samples_are_available"
                if gate["passed"]
                else "review_candidate_package_and_concurrency_sensitivity"
            ),
        },
        "safetyBoundary": {
            "localSimulationOnly": True,
            "usesApiKey": False,
            "tradeApiUsed": False,
            "withdrawApiUsed": False,
            "readsRealAccount": False,
            "readsRealPositions": False,
            "createsOrders": False,
            "autoTrading": False,
            "exchangeDryRunApproved": False,
            "liveTradingApproved": False,
        },
    }
    return _json_ready(report), _json_ready(ledger), _json_ready(package)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate V13.5.21 local paper refresh candidate report.")
    parser.add_argument("--decision-report", type=Path, default=DEFAULT_DECISION_REPORT)
    parser.add_argument("--selected-signals", type=Path, default=DEFAULT_SELECTED_SIGNALS)
    parser.add_argument("--max-concurrent-positions", type=int, default=8)
    parser.add_argument("--output-report", type=Path, default=DEFAULT_OUTPUT_REPORT)
    parser.add_argument("--output-summary", type=Path, default=DEFAULT_OUTPUT_SUMMARY)
    parser.add_argument("--output-ledger", type=Path, default=DEFAULT_OUTPUT_LEDGER)
    parser.add_argument("--output-package", type=Path, default=DEFAULT_OUTPUT_PACKAGE)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report, ledger, package = generate_report(args)
    write_json(args.output_report, report)
    write_text(args.output_summary, _summary_markdown(report))
    write_json(args.output_ledger, ledger)
    write_json(args.output_package, package)
    print(f"Wrote {args.output_report}")
    print(f"Wrote {args.output_summary}")
    print(f"Wrote {args.output_ledger}")
    print(f"Wrote {args.output_package}")
    print(
        "localPaperRefreshCandidateReady="
        f"{report['decision']['localPaperRefreshCandidateReady']} "
        f"filledSignalCount={report['ledgerMetrics'].get('filledSignalCount')} "
        f"skippedSignalCount={report['ledgerMetrics'].get('skippedSignalCount')}"
    )


if __name__ == "__main__":
    main()
