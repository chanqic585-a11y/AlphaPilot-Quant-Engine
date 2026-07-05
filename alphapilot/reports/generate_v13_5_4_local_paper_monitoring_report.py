"""Generate V13.5.4 local paper monitoring report.

V13.5.4 turns the V13.5.3 one-shot local paper sandbox ledger into a monitoring
report with rolling windows, freshness checks, skipped-signal analysis, and
decay warnings. It reads local JSON reports only and never runs exchange
Dry-run, uses API keys, reads real accounts, creates orders, or auto trades.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from alphapilot.paper_sandbox.paper_monitoring import (
    freshness_summary,
    metrics_from_fills,
    monthly_fill_breakdown,
    monitoring_decision,
    pair_breakdown,
    rolling_trade_windows,
    skip_reason_breakdown,
)
from alphapilot.reports.generate_v13_5_derivatives_ml_strategy_report import write_json, write_text


REPORT_ID = "v13_5_4_local_paper_monitoring_report"
VERSION = "V13.5.4"
DEFAULT_SIGNAL_LOG = Path("reports/v13_5_2_forward_confirmation_signal_log.json")
DEFAULT_LEDGER = Path("reports/v13_5_3_local_paper_sandbox_ledger.json")
DEFAULT_LEDGER_REPORT = Path("reports/v13_5_3_local_paper_sandbox_report.json")
DEFAULT_OUTPUT_REPORT = Path("reports/v13_5_4_local_paper_monitoring_report.json")
DEFAULT_OUTPUT_SUMMARY = Path("reports/v13_5_4_local_paper_monitoring_summary.md")
DEFAULT_OUTPUT_EVENTS = Path("reports/v13_5_4_local_paper_monitoring_events.json")


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _event_rows(report: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for window in report.get("rollingWindows", []):
        metrics = window.get("metrics") or {}
        rows.append(
            {
                "eventType": "rolling_window",
                "windowTradeCount": window.get("windowTradeCount"),
                "availableTradeCount": window.get("availableTradeCount"),
                "winRatePct": metrics.get("winRatePct"),
                "rewardRiskRatio": metrics.get("rewardRiskRatio"),
                "profitFactor": metrics.get("profitFactor"),
                "totalReturnPct": metrics.get("totalReturnPct"),
                "maxDrawdownPct": metrics.get("maxDrawdownPct"),
                "source": REPORT_ID,
            }
        )
    decision = report.get("decision") or {}
    rows.append(
        {
            "eventType": "monitoring_decision",
            "monitoringHealth": decision.get("monitoringHealth"),
            "localPaperMonitoringActive": decision.get("localPaperMonitoringActive"),
            "continueLocalPaperMonitoring": decision.get("continueLocalPaperMonitoring"),
            "exchangeDryRunReviewReady": decision.get("exchangeDryRunReviewReady"),
            "warningReasons": decision.get("warningReasons"),
            "failReasons": decision.get("failReasons"),
            "source": REPORT_ID,
        }
    )
    return rows


def build_monitoring_report(
    signal_log_path: Path = DEFAULT_SIGNAL_LOG,
    ledger_path: Path = DEFAULT_LEDGER,
    ledger_report_path: Path = DEFAULT_LEDGER_REPORT,
) -> dict[str, Any]:
    signal_rows = _read_json(signal_log_path)
    ledger = _read_json(ledger_path)
    ledger_report = _read_json(ledger_report_path)
    fills = ledger.get("fills") or []
    skipped = ledger.get("skippedSignals") or []
    generated_at = utc_now()
    full_metrics = metrics_from_fills(
        fills,
        initial_equity=float((ledger.get("config") or {}).get("initial_equity") or 10_000.0),
    )
    rolling_windows = rolling_trade_windows(fills)
    freshness = freshness_summary(signal_rows, fills, generated_at=generated_at)
    skipped_breakdown = skip_reason_breakdown(skipped)
    decision = monitoring_decision(full_metrics, rolling_windows, freshness, skipped_breakdown)
    return {
        "reportId": REPORT_ID,
        "version": VERSION,
        "status": "completed",
        "isMock": False,
        "generatedAt": generated_at,
        "objective": {
            "mode": "local_paper_monitoring_and_fresh_evidence_refresh",
            "description": "Monitor V13.5.3 local paper sandbox performance with rolling windows and freshness checks.",
            "paperDefinition": "Local paper monitoring is local simulated observation only; it is not exchange Dry-run.",
        },
        "inputReports": {
            "signalLog": str(signal_log_path),
            "ledger": str(ledger_path),
            "ledgerReport": str(ledger_report_path),
        },
        "approvedCandidateIds": ledger_report.get("approvedCandidateIds") or [],
        "ledgerConfig": ledger.get("config") or {},
        "fullMetrics": full_metrics,
        "ledgerReportedMetrics": ledger.get("metrics") or {},
        "rollingWindows": rolling_windows,
        "monthlyBreakdown": monthly_fill_breakdown(fills),
        "pairBreakdown": pair_breakdown(fills),
        "skippedSignalBreakdown": skipped_breakdown,
        "freshness": freshness,
        "decision": decision,
        "nextStep": (
            "Continue local paper monitoring and collect more fresh evidence before exchange Dry-run review."
            if decision.get("continueLocalPaperMonitoring")
            else "Do not continue toward exchange Dry-run; inspect monitoring fail reasons first."
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
    }


def write_summary(report: dict[str, Any], path: Path) -> None:
    decision = report["decision"]
    full = report["fullMetrics"]
    freshness = report["freshness"]
    lines = [
        "# V13.5.4 Local Paper Monitoring Report",
        "",
        "This report is local simulation monitoring only. It does not run exchange Dry-run, use API keys, read accounts, create orders, or auto trade.",
        "",
        "## Decision",
        "",
        f"- Local paper monitoring active: `{decision['localPaperMonitoringActive']}`",
        f"- Monitoring health: `{decision['monitoringHealth']}`",
        f"- Continue local paper monitoring: `{decision['continueLocalPaperMonitoring']}`",
        f"- Exchange Dry-run review ready: `{decision['exchangeDryRunReviewReady']}`",
        f"- Live trading approved: `{decision['liveTradingApproved']}`",
        f"- Reason: `{decision['reason']}`",
        f"- Warning reasons: `{', '.join(decision['warningReasons']) or 'none'}`",
        f"- Fail reasons: `{', '.join(decision['failReasons']) or 'none'}`",
        "",
        "## Full Ledger Metrics",
        "",
        f"- Trades: `{full.get('tradeCount')}`",
        f"- Win rate: `{full.get('winRatePct')}`",
        f"- Reward/risk: `{full.get('rewardRiskRatio')}`",
        f"- Profit factor: `{full.get('profitFactor')}`",
        f"- Total return: `{full.get('totalReturnPct')}`",
        f"- Max drawdown: `{full.get('maxDrawdownPct')}`",
        f"- Max consecutive losses: `{full.get('maxConsecutiveLosses')}`",
        "",
        "## Freshness",
        "",
        f"- Latest signal: `{freshness.get('latestSignalAt')}`",
        f"- Latest closed fill: `{freshness.get('latestClosedFillAt')}`",
        f"- Signal age days: `{freshness.get('signalAgeDays')}`",
        f"- Closed fill age days: `{freshness.get('closedFillAgeDays')}`",
        f"- Signal to closed-fill lag days: `{freshness.get('signalToClosedFillLagDays')}`",
        f"- Signal fresh: `{freshness.get('signalFresh')}`",
        f"- Closed fill fresh: `{freshness.get('closedFillFresh')}`",
        "",
        "## Rolling Windows",
        "",
    ]
    for window in report.get("rollingWindows", []):
        metrics = window.get("metrics") or {}
        lines.append(
            f"- Last `{window.get('availableTradeCount')}` of target `{window.get('windowTradeCount')}` trades: "
            f"winRate=`{metrics.get('winRatePct')}`, "
            f"reward/risk=`{metrics.get('rewardRiskRatio')}`, "
            f"PF=`{metrics.get('profitFactor')}`, "
            f"return=`{metrics.get('totalReturnPct')}`, "
            f"maxDD=`{metrics.get('maxDrawdownPct')}`"
        )
    lines.extend(
        [
            "",
            "## Skipped Signals",
            "",
        ]
    )
    for row in report.get("skippedSignalBreakdown", []):
        lines.append(f"- `{row.get('reason')}`: `{row.get('count')}`")
    lines.extend(
        [
            "",
            "## Pair Breakdown",
            "",
        ]
    )
    for row in report.get("pairBreakdown", [])[:10]:
        lines.append(
            f"- `{row.get('pair')}`: trades=`{row.get('tradeCount')}`, "
            f"winRate=`{row.get('winRatePct')}`, PF=`{row.get('profitFactor')}`, "
            f"return=`{row.get('totalReturnPct')}`"
        )
    lines.extend(
        [
            "",
            "## Next Step",
            "",
            f"- {report.get('nextStep')}",
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
    parser.add_argument("--signal-log", default=str(DEFAULT_SIGNAL_LOG))
    parser.add_argument("--ledger", default=str(DEFAULT_LEDGER))
    parser.add_argument("--ledger-report", default=str(DEFAULT_LEDGER_REPORT))
    parser.add_argument("--output-report", default=str(DEFAULT_OUTPUT_REPORT))
    parser.add_argument("--output-summary", default=str(DEFAULT_OUTPUT_SUMMARY))
    parser.add_argument("--output-events", default=str(DEFAULT_OUTPUT_EVENTS))
    args = parser.parse_args()

    report = build_monitoring_report(
        signal_log_path=Path(args.signal_log),
        ledger_path=Path(args.ledger),
        ledger_report_path=Path(args.ledger_report),
    )
    output_report = Path(args.output_report)
    output_summary = Path(args.output_summary)
    output_events = Path(args.output_events)
    write_json(output_report, report)
    write_summary(report, output_summary)
    write_json(output_events, _event_rows(report))
    print(f"Wrote {output_report}")
    print(f"Wrote {output_summary}")
    print(f"Wrote {output_events}")
    print(f"decision={report['decision']}")
    print(f"fullMetrics={report['fullMetrics']}")


if __name__ == "__main__":
    main()
