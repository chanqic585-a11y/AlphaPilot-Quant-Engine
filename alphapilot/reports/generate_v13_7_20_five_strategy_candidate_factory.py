"""Generate V13.7.20 five-strategy candidate factory report.

The report is research-only. It reads local public OHLCV and deterministic
candidate replay results. It does not call exchange APIs, read accounts, create
orders, run exchange Dry-run, or automate trading.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from alphapilot.low_frequency.strategy_candidate_factory import run_strategy_candidate_factory


REPORT_ID = "v13_7_20_five_strategy_candidate_factory"
VERSION = "V13.7.20"
REPORT_PATH = Path("reports/v13_7_20_five_strategy_candidate_factory_report.json")
SUMMARY_PATH = Path("reports/v13_7_20_five_strategy_candidate_factory_summary.md")
DOC_PATH = Path("docs/V13.7.20-five-strategy-candidate-factory.md")


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _candidate_table(candidates: list[dict[str, Any]], *, include_failed: bool = True) -> list[str]:
    lines = [
        "| Candidate | TF | Family | Approved | Trades | Win % | PF | Return % | DD % | Failed Checks |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for item in candidates:
        failed = []
        if include_failed:
            failed = [key for key, value in item.get("approval", {}).get("checks", {}).items() if not value]
        else:
            failed = item.get("failedChecks", [])
        spec = item.get("spec", item)
        metrics = item.get("metrics", item)
        lines.append(
            "| {name} | {tf} | {family} | {approved} | {trades} | {win} | {pf} | {ret} | {dd} | {failed} |".format(
                name=item.get("displayName") or item.get("candidateId"),
                tf=spec.get("timeframe"),
                family=spec.get("family"),
                approved=item.get("approval", {}).get("passed", item.get("approved")),
                trades=metrics.get("tradeCount"),
                win=metrics.get("winRatePct"),
                pf=metrics.get("profitFactor"),
                ret=metrics.get("totalReturnPct"),
                dd=metrics.get("maxDrawdownPct"),
                failed=", ".join(failed) if failed else "--",
            )
        )
    return lines


def _walk_forward_table(candidate: dict[str, Any]) -> list[str]:
    lines = [
        "| Split | Trades | Win % | PF | Return % | DD % |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in candidate.get("walkForward", []):
        lines.append(
            "| {split} | {trades} | {win} | {pf} | {ret} | {dd} |".format(
                split=row.get("splitId"),
                trades=row.get("tradeCount"),
                win=row.get("winRatePct"),
                pf=row.get("profitFactor"),
                ret=row.get("totalReturnPct"),
                dd=row.get("maxDrawdownPct"),
            )
        )
    return lines


def render_summary(report: dict[str, Any]) -> str:
    factory = report["factory"]
    lines = [
        "# AlphaPilot V13.7.20 Five Strategy Candidate Factory",
        "",
        "This report searches deterministic low-frequency strategy candidates with a fixed 2R target.",
        "It is research-only, not exchange Dry-run, not live trading, not an order, and not trading advice.",
        "",
        "## Summary",
        "",
        f"- status: {report['status']}",
        f"- candidateCount: {factory['candidateCount']}",
        f"- approvedCount: {factory['approvedCount']}",
        f"- targetApprovedCount: {factory['targetApprovedCount']}",
        f"- availableTimeframes: {', '.join(factory['availableTimeframes'])}",
        f"- timerange: {factory['timerange']}",
        f"- paperObservationApprovedCount: {report['summary']['paperObservationApprovedCount']}",
        f"- dryRunApproved: {report['summary']['dryRunApproved']}",
        f"- liveTradingApproved: {report['summary']['liveTradingApproved']}",
        "",
        "## Approved Candidates",
        "",
    ]
    approved = factory.get("approvedCandidates", [])
    if approved:
        lines.extend(_candidate_table(approved))
        for item in approved:
            lines.extend(["", f"### {item['displayName']}", ""])
            lines.extend(_walk_forward_table(item))
    else:
        lines.append("No candidate passed the full research gate in this run.")

    lines.extend(["", "## Top Watchlist Candidates", ""])
    lines.extend(_candidate_table(factory.get("topWatchlistCandidates", [])[:20]))

    lines.extend(["", "## Safety Boundary", ""])
    for key, value in report["safetyBoundary"].items():
        lines.append(f"- {key}: {value}")

    if factory.get("warnings"):
        lines.extend(["", "## Warnings", ""])
        for warning in factory["warnings"][:50]:
            lines.append(f"- {warning}")

    lines.extend(["", "## Next Step", "", report["nextStep"], ""])
    return "\n".join(lines)


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    factory = run_strategy_candidate_factory(
        data_path=Path(args.data_path),
        timerange=args.timerange,
        max_approved=args.max_approved,
    )
    approved = factory.get("approvedCandidates", [])
    next_step = (
        "Move approved candidates into local paper-observation review only; exchange Dry-run remains blocked."
        if approved
        else "Expand public OHLCV coverage and redesign failed checks; do not weaken the fixed 2R target."
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
        "status": factory.get("status", "unknown"),
        "generatedAt": _now(),
        "source": "alphapilot_five_strategy_candidate_factory_v13_7_20",
        "objective": "Search for up to five deterministic 2R research-usable strategy candidates.",
        "inputReports": [
            "reports/v13_7_19_lf_factor_confluence_backtest_report.json",
            "reports/v13_4_32_low_frequency_baseline_report.json",
        ],
        "factory": factory,
        "summary": {
            "candidateCount": factory.get("candidateCount", 0),
            "approvedCount": factory.get("approvedCount", 0),
            "targetApprovedCount": factory.get("targetApprovedCount", args.max_approved),
            "paperObservationApprovedCount": len(approved),
            "dryRunApproved": False,
            "liveTradingApproved": False,
            "nextStep": next_step,
        },
        "nextStep": next_step,
        "safetyBoundary": safety,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate V13.7.20 five-strategy candidate factory report.")
    parser.add_argument("--data-path", default="user_data/data/okx/futures")
    parser.add_argument("--timerange", default="20200101-")
    parser.add_argument("--max-approved", type=int, default=5)
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

