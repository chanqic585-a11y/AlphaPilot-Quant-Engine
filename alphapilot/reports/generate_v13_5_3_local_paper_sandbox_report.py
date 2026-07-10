"""Generate V13.5.3 local paper sandbox ledger report.

This command starts the first local simulated observation ledger for the V13.5.2
approved candidate. It uses local JSON reports only. It does not run Freqtrade
dry-run, does not use exchange APIs, does not read accounts or positions, and
does not create orders.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from alphapilot.paper_sandbox.local_paper_ledger import (
    LocalPaperSandboxConfig,
    simulate_local_paper_ledger,
)
from alphapilot.reports.generate_v13_5_derivatives_ml_strategy_report import write_json, write_text


REPORT_ID = "v13_5_3_local_paper_sandbox_ledger_report"
VERSION = "V13.5.3"
DEFAULT_DECISION_PATH = Path("reports/v13_5_2_forward_confirmation_report.json")
DEFAULT_SIGNAL_LOG_PATH = Path("reports/v13_5_2_forward_confirmation_signal_log.json")
DEFAULT_OUTPUT_LEDGER = Path("reports/v13_5_3_local_paper_sandbox_ledger.json")
DEFAULT_OUTPUT_REPORT = Path("reports/v13_5_3_local_paper_sandbox_report.json")
DEFAULT_OUTPUT_SUMMARY = Path("reports/v13_5_3_local_paper_sandbox_summary.md")


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _paper_monitoring_decision(metrics: dict[str, Any]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if (metrics.get("tradeCount") or 0) < 40:
        reasons.append("filled_trade_count_below_40")
    if (metrics.get("winRatePct") or 0) < 55:
        reasons.append("paper_win_rate_below_55")
    if (metrics.get("rewardRiskRatio") or 0) < 1.5:
        reasons.append("paper_reward_risk_below_1_5")
    if (metrics.get("profitFactor") or 0) < 1.35:
        reasons.append("paper_profit_factor_below_1_35")
    if (metrics.get("maxDrawdownPct") or 999) > 20:
        reasons.append("paper_drawdown_above_20")
    if (metrics.get("totalReturnPct") or 0) <= 0:
        reasons.append("paper_total_return_not_positive")
    return len(reasons) == 0, reasons


def run_local_paper_sandbox(
    decision_path: Path = DEFAULT_DECISION_PATH,
    signal_log_path: Path = DEFAULT_SIGNAL_LOG_PATH,
    initial_equity: float = 10_000.0,
    risk_per_signal_pct: float = 1.0,
    max_concurrent_positions: int = 8,
    max_notional_per_signal_pct: float = 35.0,
) -> dict[str, Any]:
    decision_report = _read_json(decision_path)
    signal_rows = _read_json(signal_log_path)
    approved_candidate_ids = decision_report.get("decision", {}).get("localPaperSandboxCandidateIds") or []
    best = decision_report.get("bestCandidate") or {}
    barrier_config = best.get("barrierConfig") or {}
    config = LocalPaperSandboxConfig(
        initial_equity=initial_equity,
        risk_per_signal_pct=risk_per_signal_pct,
        max_concurrent_positions=max_concurrent_positions,
        max_notional_per_signal_pct=max_notional_per_signal_pct,
        stop_loss_pct=float(barrier_config.get("stop_loss_pct", 0.045)),
    )
    ledger = simulate_local_paper_ledger(signal_rows, approved_candidate_ids, config)
    monitoring_ready, fail_reasons = _paper_monitoring_decision(ledger["metrics"])
    sensitivity_results = []
    for sensitivity_max_positions in [3, 5, 8, 12, 999]:
        sensitivity_config = LocalPaperSandboxConfig(
            initial_equity=initial_equity,
            risk_per_signal_pct=risk_per_signal_pct,
            max_concurrent_positions=sensitivity_max_positions,
            max_notional_per_signal_pct=max_notional_per_signal_pct,
            stop_loss_pct=float(barrier_config.get("stop_loss_pct", 0.045)),
        )
        sensitivity_ledger = simulate_local_paper_ledger(signal_rows, approved_candidate_ids, sensitivity_config)
        sensitivity_ready, sensitivity_fail_reasons = _paper_monitoring_decision(sensitivity_ledger["metrics"])
        sensitivity_results.append(
            {
                "maxConcurrentPositions": sensitivity_max_positions,
                "paperMonitoringReady": sensitivity_ready,
                "paperMonitoringFailReasons": sensitivity_fail_reasons,
                "metrics": sensitivity_ledger["metrics"],
            }
        )
    return {
        "reportId": REPORT_ID,
        "version": VERSION,
        "status": "completed",
        "isMock": False,
        "generatedAt": utc_now(),
        "evidenceClass": "legacy_synthetic",
        "excludedFromFormalTraining": True,
        "formalPromotionEligible": False,
        "inputReports": {
            "decisionReport": str(decision_path),
            "signalLog": str(signal_log_path),
        },
        "approvedCandidateIds": approved_candidate_ids,
        "ledgerConfig": ledger["config"],
        "metrics": ledger["metrics"],
        "sensitivityResults": sensitivity_results,
        "decision": {
            "localPaperSandboxStarted": bool(approved_candidate_ids),
            "paperMonitoringReady": monitoring_ready,
            "paperMonitoringFailReasons": fail_reasons,
            "exchangeDryRunApproved": False,
            "liveTradingApproved": False,
            "reason": (
                "local_paper_sandbox_ledger_ready"
                if monitoring_ready
                else "local_paper_sandbox_ledger_created_but_monitoring_gate_not_clean"
            ),
        },
        "ledgerPath": str(DEFAULT_OUTPUT_LEDGER),
        "nextStep": (
            "Monitor future local signal logs with the same ledger rules before exchange Dry-run review."
            if monitoring_ready
            else "Inspect skipped signals and paper ledger drawdown before expanding monitoring."
        ),
        "safetyBoundary": {
            "localSimulationOnly": True,
            "usesApiKey": False,
            "tradeApiUsed": False,
            "withdrawApiUsed": False,
            "readsRealAccount": False,
            "readsRealPositions": False,
            "createsOrders": False,
            "autoTrading": False,
            "freqtradeDryRunApproved": False,
            "exchangeDryRunApproved": False,
            "liveTradingApproved": False,
        },
        "_ledger": ledger,
    }


def write_summary(report: dict[str, Any], path: Path) -> None:
    metrics = report["metrics"]
    decision = report["decision"]
    lines = [
        "# V13.5.3 Local Paper Sandbox Ledger Report",
        "",
        "This report is local simulation only. It does not run exchange Dry-run, use API keys, read accounts, create orders, or auto trade.",
        "",
        "## Decision",
        "",
        f"- Local paper sandbox started: `{decision['localPaperSandboxStarted']}`",
        f"- Paper monitoring ready: `{decision['paperMonitoringReady']}`",
        f"- Exchange Dry-run approved: `{decision['exchangeDryRunApproved']}`",
        f"- Live trading approved: `{decision['liveTradingApproved']}`",
        f"- Reason: `{decision['reason']}`",
        f"- Fail reasons: `{', '.join(decision['paperMonitoringFailReasons']) or 'none'}`",
        "",
        "## Ledger Metrics",
        "",
        f"- Initial equity: `{metrics.get('initialEquity')}`",
        f"- Final equity: `{metrics.get('finalEquity')}`",
        f"- Total return: `{metrics.get('totalReturnPct')}`",
        f"- Max drawdown: `{metrics.get('maxDrawdownPct')}`",
        f"- Filled trades: `{metrics.get('filledSignalCount')}`",
        f"- Skipped signals: `{metrics.get('skippedSignalCount')}`",
        f"- Win rate: `{metrics.get('winRatePct')}`",
        f"- Reward/risk: `{metrics.get('rewardRiskRatio')}`",
        f"- Profit factor: `{metrics.get('profitFactor')}`",
        f"- Max concurrent positions: `{metrics.get('maxConcurrentPositions')}`",
        "",
        "## Concurrency Sensitivity",
        "",
    ]
    for row in report.get("sensitivityResults", []):
        row_metrics = row.get("metrics") or {}
        lines.extend(
            [
                f"- Max positions `{row.get('maxConcurrentPositions')}`: ready=`{row.get('paperMonitoringReady')}`, "
                f"trades=`{row_metrics.get('tradeCount')}`, return=`{row_metrics.get('totalReturnPct')}`, "
                f"drawdown=`{row_metrics.get('maxDrawdownPct')}`, winRate=`{row_metrics.get('winRatePct')}`, "
                f"reward/risk=`{row_metrics.get('rewardRiskRatio')}`, PF=`{row_metrics.get('profitFactor')}`",
            ]
        )
    lines.extend(
        [
        "",
        "## Approved Candidates",
        "",
        *[f"- `{candidate_id}`" for candidate_id in report.get("approvedCandidateIds", [])],
        "",
        "## Outputs",
        "",
        f"- Ledger: `{report['ledgerPath']}`",
        "",
        "## Safety Boundary",
        "",
        "- Local simulated capital only.",
        "- No Trade API.",
        "- No Withdraw API.",
        "- No API key storage.",
        "- No real account reads.",
        "- No real position reads.",
        "- No real orders.",
        "- No automatic trading.",
        "- Exchange Dry-run remains disabled.",
        "",
        ]
    )
    write_text(path, "\n".join(lines))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--decision-report", default=str(DEFAULT_DECISION_PATH))
    parser.add_argument("--signal-log", default=str(DEFAULT_SIGNAL_LOG_PATH))
    parser.add_argument("--initial-equity", type=float, default=10_000.0)
    parser.add_argument("--risk-per-signal-pct", type=float, default=1.0)
    parser.add_argument("--max-concurrent-positions", type=int, default=8)
    parser.add_argument("--max-notional-per-signal-pct", type=float, default=35.0)
    parser.add_argument("--output-ledger", default=str(DEFAULT_OUTPUT_LEDGER))
    parser.add_argument("--output-report", default=str(DEFAULT_OUTPUT_REPORT))
    parser.add_argument("--output-summary", default=str(DEFAULT_OUTPUT_SUMMARY))
    args = parser.parse_args()

    report = run_local_paper_sandbox(
        decision_path=Path(args.decision_report),
        signal_log_path=Path(args.signal_log),
        initial_equity=args.initial_equity,
        risk_per_signal_pct=args.risk_per_signal_pct,
        max_concurrent_positions=args.max_concurrent_positions,
        max_notional_per_signal_pct=args.max_notional_per_signal_pct,
    )
    ledger = report.pop("_ledger")
    output_ledger = Path(args.output_ledger)
    output_report = Path(args.output_report)
    output_summary = Path(args.output_summary)
    write_json(output_ledger, ledger)
    report["ledgerPath"] = str(output_ledger)
    write_json(output_report, report)
    write_summary(report, output_summary)
    print(f"Wrote {output_ledger}")
    print(f"Wrote {output_report}")
    print(f"Wrote {output_summary}")
    print(f"decision={report['decision']}")
    print(f"metrics={report['metrics']}")


if __name__ == "__main__":
    main()
