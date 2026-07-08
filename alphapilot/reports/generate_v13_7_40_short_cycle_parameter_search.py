"""Generate V13.7.40 short-cycle parameter search report.

This is a research-only offline scan. It reads local public OHLCV data and
simulates fixed 2R exits. It does not call exchange APIs, use API keys, read
real accounts or positions, create orders, run exchange dry-run, or automate
trading.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from alphapilot.short_cycle.parameter_search import SearchConfig, run_short_cycle_parameter_search


REPORT_ID = "v13_7_40_short_cycle_parameter_search"
REPORT_PATH = Path("reports/v13_7_40_short_cycle_parameter_search_report.json")
SUMMARY_PATH = Path("reports/v13_7_40_short_cycle_parameter_search_summary.md")
DOC_PATH = Path("docs/V13.7.40-short-cycle-parameter-search.md")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _fmt(value: Any) -> str:
    if value is None:
        return "--"
    if isinstance(value, float):
        return str(round(value, 4))
    return str(value)


def _candidate_table(candidates: list[dict[str, Any]]) -> list[str]:
    lines = [
        "| Candidate | TF | Family | Direction | Tier | Asset Filter | Strict | Observation | Trades | Pairs | Win % | PF | Exp R | Test PF | Test Exp R | DD R | Failed Checks | Observation Checks |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for item in candidates:
        metrics = item.get("metrics", {})
        test = item.get("splitMetrics", {}).get("test", {})
        failed = item.get("failedChecks") or []
        observation_failed = item.get("observationFailedChecks") or []
        asset_filter = item.get("assetFilter") or {}
        asset_filter_label = (
            f"Top{asset_filter.get('selectedPairCount')}"
            if asset_filter.get("enabled")
            else "--"
        )
        lines.append(
            "| {name} | {tf} | {family} | {direction} | {tier} | {asset_filter} | {approved} | {observation} | {trades} | {pairs} | {win} | {pf} | {exp} | {test_pf} | {test_exp} | {dd} | {failed} | {observation_failed} |".format(
                name=item.get("displayName"),
                tf=item.get("timeframe"),
                family=item.get("family"),
                direction=item.get("direction"),
                tier=item.get("approvalTier"),
                asset_filter=asset_filter_label,
                approved=item.get("approved"),
                observation=item.get("observationCandidate"),
                trades=_fmt(metrics.get("tradeCount")),
                pairs=_fmt(metrics.get("pairCount")),
                win=_fmt(metrics.get("winRatePct")),
                pf=_fmt(metrics.get("profitFactor")),
                exp=_fmt(metrics.get("expectancyR")),
                test_pf=_fmt(test.get("profitFactor")),
                test_exp=_fmt(test.get("expectancyR")),
                dd=_fmt(metrics.get("maxDrawdownR")),
                failed=", ".join(failed) if failed else "--",
                observation_failed=", ".join(observation_failed) if observation_failed else "--",
            )
        )
    return lines


def _split_table(candidate: dict[str, Any]) -> list[str]:
    lines = [
        "| Split | Trades | Pairs | Win % | PF | Exp R | Total R | DD R |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for split_name in ("train", "validation", "test"):
        metrics = candidate.get("splitMetrics", {}).get(split_name, {})
        lines.append(
            "| {split} | {trades} | {pairs} | {win} | {pf} | {exp} | {total} | {dd} |".format(
                split=split_name,
                trades=_fmt(metrics.get("tradeCount")),
                pairs=_fmt(metrics.get("pairCount")),
                win=_fmt(metrics.get("winRatePct")),
                pf=_fmt(metrics.get("profitFactor")),
                exp=_fmt(metrics.get("expectancyR")),
                total=_fmt(metrics.get("totalR")),
                dd=_fmt(metrics.get("maxDrawdownR")),
            )
        )
    return lines


def render_summary(report: dict[str, Any]) -> str:
    selected = report.get("selectedCandidates", [])
    approved_selected = [item for item in selected if item.get("approved")]
    observation_selected = [item for item in selected if item.get("observationCandidate") and not item.get("approved")]
    lines = [
        "# AlphaPilot V13.7.40 Short-Cycle Parameter Search",
        "",
        "This report searches short-cycle public-OHLCV research candidates with fixed 2R exits.",
        "It is not exchange dry-run, not live trading, not an order, and not trading advice.",
        "",
        "## Summary",
        "",
        f"- status: {report.get('status')}",
        f"- candidateCount: {report.get('candidateCount')}",
        f"- approvedCount: {report.get('approvedCount')}",
        f"- observationCandidateCount: {report.get('observationCandidateCount')}",
        f"- selectedCount: {report.get('selectedCount')}",
        f"- approvedSelectedCount: {len(approved_selected)}",
        f"- observationSelectedCount: {len(observation_selected)}",
        f"- targetR: {report.get('config', {}).get('targetR')}",
        f"- feeRate: {report.get('config', {}).get('feeRate')}",
        f"- slippageRate: {report.get('config', {}).get('slippageRate')}",
        f"- timerange: {report.get('config', {}).get('timerange')}",
        "",
        "## Data Coverage",
        "",
    ]
    for timeframe, row in report.get("dataCoverage", {}).items():
        lines.append(f"- {timeframe}: {row.get('pairCount')} pairs")

    lines.extend(["", "## Selected Candidates", ""])
    lines.extend(_candidate_table(selected))

    for item in selected:
        lines.extend(["", f"### {item.get('displayName')}", ""])
        lines.append(f"- candidateId: `{item.get('candidateId')}`")
        lines.append(f"- approved: {item.get('approved')}")
        lines.append(f"- observationCandidate: {item.get('observationCandidate')}")
        lines.append(f"- approvalTier: {item.get('approvalTier')}")
        lines.append(f"- params: `{json.dumps(item.get('params'), ensure_ascii=False)}`")
        asset_filter = item.get("assetFilter") or {}
        if asset_filter.get("enabled"):
            lines.append(f"- assetFilter: `{json.dumps(asset_filter, ensure_ascii=False)}`")
        lines.extend(["", "#### Walk-Forward", ""])
        lines.extend(_split_table(item))
        pair_rows = item.get("pairBreakdown", [])[:8]
        if pair_rows:
            lines.extend(["", "#### Top Pair Breakdown", ""])
            lines.append("| Pair | Trades | Win % | PF | Exp R | Total R |")
            lines.append("| --- | ---: | ---: | ---: | ---: | ---: |")
            for row in pair_rows:
                lines.append(
                    "| {pair} | {trades} | {win} | {pf} | {exp} | {total} |".format(
                        pair=row.get("pair"),
                        trades=_fmt(row.get("tradeCount")),
                        win=_fmt(row.get("winRatePct")),
                        pf=_fmt(row.get("profitFactor")),
                        exp=_fmt(row.get("expectancyR")),
                        total=_fmt(row.get("totalR")),
                    )
                )

    lines.extend(["", "## Top 25 Candidates", ""])
    lines.extend(_candidate_table(report.get("topCandidates", [])[:25]))

    lines.extend(["", "## Safety Boundary", ""])
    for key, value in report.get("safetyBoundary", {}).items():
        lines.append(f"- {key}: {value}")

    if report.get("warnings"):
        lines.extend(["", "## Warnings", ""])
        for warning in report["warnings"][:80]:
            lines.append(f"- {warning}")

    lines.extend(
        [
            "",
            "## Next Step",
            "",
            "Only approved selected candidates may enter local sandbox / paper-observation review.",
            "Exchange dry-run and live trading remain blocked until real forward samples are available.",
            "",
        ]
    )
    return "\n".join(lines)


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    config = SearchConfig(
        dataPath=Path(args.data_path),
        timerange=args.timerange,
        timeframes=tuple(item.strip() for item in args.timeframes.split(",") if item.strip()),
        maxSelected=args.max_selected,
        maxPairsPerTimeframe=args.max_pairs_per_timeframe,
    )
    report = run_short_cycle_parameter_search(config)
    report["reportId"] = REPORT_ID
    report["summary"] = {
        "candidateCount": report.get("candidateCount"),
        "approvedCount": report.get("approvedCount"),
        "observationCandidateCount": report.get("observationCandidateCount"),
        "selectedCount": report.get("selectedCount"),
        "approvedSelectedCount": len([item for item in report.get("selectedCandidates", []) if item.get("approved")]),
        "observationSelectedCount": len(
            [
                item
                for item in report.get("selectedCandidates", [])
                if item.get("observationCandidate") and not item.get("approved")
            ]
        ),
        "dryRunApproved": False,
        "liveTradingApproved": False,
        "nextStep": "local_sandbox_or_paper_observation_only",
    }
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate V13.7.40 short-cycle parameter search report.")
    parser.add_argument("--data-path", default="user_data/data/okx/futures")
    parser.add_argument("--timerange", default="20260101-")
    parser.add_argument("--timeframes", default="15m,30m,1h")
    parser.add_argument("--max-selected", type=int, default=5)
    parser.add_argument("--max-pairs-per-timeframe", type=int, default=None)
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
