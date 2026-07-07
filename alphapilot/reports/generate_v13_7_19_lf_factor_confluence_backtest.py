"""Generate V13.7.19 deterministic LF factor-confluence backtest report.

The report is research-only. It reads local public OHLCV files and writes local
reports. It does not call exchange APIs, read accounts, create orders, enter
exchange Dry-run, or automate trading.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from alphapilot.low_frequency.factor_confluence_backtest import (
    FactorConfluenceBacktestConfig,
    run_factor_confluence_backtest,
)


REPORT_ID = "v13_7_19_lf_factor_confluence_backtest"
VERSION = "V13.7.19"
REPORT_PATH = Path("reports/v13_7_19_lf_factor_confluence_backtest_report.json")
SUMMARY_PATH = Path("reports/v13_7_19_lf_factor_confluence_backtest_summary.md")
DOC_PATH = Path("docs/V13.7.19-lf-factor-confluence-backtest.md")


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _render_metrics_table(rows: list[dict[str, Any]], key_name: str, max_rows: int = 30) -> list[str]:
    lines = [
        f"| {key_name} | Trades | Win % | PF | Return % | Max DD % | Total R | Max Losses |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows[:max_rows]:
        lines.append(
            "| {key} | {trades} | {win} | {pf} | {ret} | {dd} | {r} | {losses} |".format(
                key=row.get(key_name) or row.get("pair") or row.get("btcPrimaryRegime") or row.get("exitReason") or "--",
                trades=row.get("tradeCount"),
                win=row.get("winRatePct"),
                pf=row.get("profitFactor"),
                ret=row.get("totalReturnPct"),
                dd=row.get("maxDrawdownPct"),
                r=row.get("totalNetR"),
                losses=row.get("maxConsecutiveLosses"),
            )
        )
    return lines


def render_summary(report: dict[str, Any]) -> str:
    metrics = report["backtest"]["metrics"]
    gate = report["backtest"]["passGate"]
    baseline = report["backtest"]["baselineComparison"]
    lines = [
        "# AlphaPilot V13.7.19 LF Factor Confluence Backtest",
        "",
        "This is a deterministic research backtest for `lf_factor_confluence_regime_filter_4h_v0_1`.",
        "It is not exchange Dry-run, not live trading, not an order, and not trading advice.",
        "",
        "## Summary",
        "",
        f"- status: {report['status']}",
        f"- experimentId: {report['backtest']['experimentId']}",
        f"- strategyName: {report['backtest']['strategyName']}",
        f"- timerange: {report['backtest']['timerange']}",
        f"- timeframe: {report['backtest']['timeframe']}",
        f"- pairCount: {report['backtest']['pairCount']}",
        f"- tradeCount: {metrics['tradeCount']}",
        f"- winRatePct: {metrics['winRatePct']}",
        f"- profitFactor: {metrics['profitFactor']}",
        f"- targetRewardRiskRatio: {metrics['targetRewardRiskRatio']}",
        f"- realizedRewardRiskRatio: {metrics['realizedRewardRiskRatio']}",
        f"- totalReturnPct: {metrics['totalReturnPct']}",
        f"- maxDrawdownPct: {metrics['maxDrawdownPct']}",
        f"- maxConsecutiveLosses: {metrics['maxConsecutiveLosses']}",
        f"- passGatePassed: {gate['passed']}",
        f"- paperObservationApproved: {gate['paperObservationApproved']}",
        f"- exchangeDryRunApproved: {gate['exchangeDryRunApproved']}",
        f"- liveTradingApproved: {gate['liveTradingApproved']}",
        "",
        "## Gate Checks",
        "",
    ]
    for key, value in gate["checks"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(
        [
            "",
            "## Baseline Comparison",
            "",
            f"- beatsNoTrade: {baseline.get('beatsNoTrade')}",
            f"- beatsEqualWeight: {baseline.get('beatsEqualWeight')}",
            f"- equalWeightReturnPct: {baseline.get('equalWeightReturnPct')}",
            f"- strategyReturnPct: {baseline.get('strategyReturnPct')}",
            f"- equalWeightMaxDrawdownPct: {baseline.get('equalWeightMaxDrawdownPct')}",
            f"- strategyMaxDrawdownPct: {baseline.get('strategyMaxDrawdownPct')}",
            "",
            "## Walk Forward",
            "",
        ]
    )
    lines.extend(_render_metrics_table(report["backtest"]["walkForward"], "splitId"))
    lines.extend(["", "## Pair Breakdown", ""])
    lines.extend(_render_metrics_table(report["backtest"]["byPair"], "pair"))
    lines.extend(["", "## Regime Breakdown", ""])
    lines.extend(_render_metrics_table(report["backtest"]["byRegime"], "btcPrimaryRegime"))
    lines.extend(["", "## Exit Reason Breakdown", ""])
    lines.extend(_render_metrics_table(report["backtest"]["exitReasonBreakdown"], "exitReason"))
    lines.extend(
        [
            "",
            "## BTC Regime Source",
            "",
            f"- source: {report['backtest']['btcRegimeSource']['source']}",
            f"- labelCount: {report['backtest']['btcRegimeSource']['labelCount']}",
            f"- firstTimestamp: {report['backtest']['btcRegimeSource']['firstTimestamp']}",
            f"- lastTimestamp: {report['backtest']['btcRegimeSource']['lastTimestamp']}",
            f"- note: {report['backtest']['btcRegimeSource']['note']}",
            "",
            "## Safety Boundary",
            "",
        ]
    )
    for key, value in report["safetyBoundary"].items():
        lines.append(f"- {key}: {value}")
    if report["backtest"].get("warnings"):
        lines.extend(["", "## Warnings", ""])
        for warning in report["backtest"]["warnings"]:
            lines.append(f"- {warning}")
    lines.extend(
        [
            "",
            "## Next Step",
            "",
            report["nextStep"],
            "",
        ]
    )
    return "\n".join(lines)


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    config = FactorConfluenceBacktestConfig(
        data_path=Path(args.data_path),
        timerange=args.timerange,
        timeframe=args.timeframe,
    )
    backtest = run_factor_confluence_backtest(config, baseline_report_path=Path(args.baseline_report))
    gate = backtest.get("passGate", {})
    next_step = (
        "Move this candidate into local paper observation review only; exchange Dry-run remains blocked."
        if gate.get("paperObservationApproved")
        else "Keep this candidate in research. Adjust the rule only with new evidence; do not weaken the 2R target."
    )
    safety = {
        "realTradingEnabled": False,
        "exchangeDryRunApproved": False,
        "liveTradingApproved": False,
        "tradeApiEnabled": False,
        "withdrawApiEnabled": False,
        "apiKeyStorage": False,
        "realAccountReads": False,
        "realPositionReads": False,
        "orderCreation": False,
        "autoTrading": False,
    }
    return {
        "reportId": REPORT_ID,
        "version": VERSION,
        "status": backtest.get("status", "unknown"),
        "generatedAt": _now(),
        "source": "alphapilot_lf_factor_confluence_backtest_v13_7_19",
        "objective": "Implement and replay the first deterministic research backtest requested by V13.7.18.",
        "inputReports": [
            "reports/v13_7_17_regime_filtered_experiment_specs_report.json",
            "reports/v13_7_18_paper_observation_rereview_report.json",
            args.baseline_report,
        ],
        "backtest": backtest,
        "summary": {
            "experimentId": backtest.get("experimentId"),
            "tradeCount": backtest.get("metrics", {}).get("tradeCount"),
            "winRatePct": backtest.get("metrics", {}).get("winRatePct"),
            "profitFactor": backtest.get("metrics", {}).get("profitFactor"),
            "targetRewardRiskRatio": backtest.get("metrics", {}).get("targetRewardRiskRatio"),
            "maxDrawdownPct": backtest.get("metrics", {}).get("maxDrawdownPct"),
            "passGatePassed": gate.get("passed", False),
            "paperObservationApproved": gate.get("paperObservationApproved", False),
            "dryRunApproved": False,
            "liveTradingApproved": False,
            "nextStep": next_step,
        },
        "nextStep": next_step,
        "safetyBoundary": safety,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate V13.7.19 LF factor-confluence deterministic backtest report.")
    parser.add_argument("--data-path", default="user_data/data/okx/futures")
    parser.add_argument("--timerange", default="20200101-")
    parser.add_argument("--timeframe", default="4h")
    parser.add_argument("--baseline-report", default="reports/v13_4_32_low_frequency_baseline_report.json")
    parser.add_argument("--output-report", default=REPORT_PATH.as_posix())
    parser.add_argument("--output-summary", default=SUMMARY_PATH.as_posix())
    parser.add_argument("--output-doc", default=DOC_PATH.as_posix())
    args = parser.parse_args()
    report = build_report(args)
    _write_json(Path(args.output_report), report)
    summary = render_summary(report)
    _write_text(Path(args.output_summary), summary)
    _write_text(Path(args.output_doc), summary)
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
