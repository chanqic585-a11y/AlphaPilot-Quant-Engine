"""Generate the auditable 5m through 1d candidate inventory."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

from alphapilot.data_foundation.checkpoint import write_json_atomic
from alphapilot.evolution.registry.hashing import stable_hash
from alphapilot.reports.cross_timeframe_candidate_inventory import (
    TIMEFRAMES,
    build_cross_timeframe_candidate_inventory,
    classify_event_prescreen_candidate,
    normalize_long_horizon_candidate,
)


DEFAULT_FIVE_MINUTE = Path("reports/v13_27_16_event_window_prescreen.json")
DEFAULT_FIFTEEN_MINUTE = Path(
    "reports/v13_27_17_event_window_factor_successor_prescreen.json"
)
DEFAULT_LONG_HORIZON = Path(
    "reports/v13_27_17_long_horizon_candidate_pack.json"
)
DEFAULT_OUTPUT = Path(
    "reports/v13_27_17_cross_timeframe_candidate_inventory.json"
)
DEFAULT_SUMMARY = Path(
    "reports/v13_27_17_cross_timeframe_candidate_inventory_summary.md"
)


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _event_rows(report: Mapping[str, Any], timeframe: str) -> list[dict[str, Any]]:
    return [
        classify_event_prescreen_candidate(item)
        for item in report.get("results", [])
        if item.get("timeframe") == timeframe
    ]


def render_summary(report: Mapping[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# AlphaPilot V13.27.17 Cross-Timeframe Candidate Inventory",
        "",
        "本报告只做研究筛选。每周期 5 条是候选库存，不代表 5 条全部通过。",
        "所有候选保持目标不低于 2R；锁定样本不参与选择，不创建 Demo/Live Release。",
        "",
        "## Summary",
        "",
        f"- candidateCount: {summary['candidateCount']}",
        f"- candidateCountByTimeframe: {summary['candidateCountByTimeframe']}",
        f"- researchEligibleCount: {summary['researchEligibleCount']}",
        f"- executableResearchEligibleCount: {summary['executableResearchEligibleCount']}",
        f"- shadowOnlyCount: {summary['shadowOnlyCount']}",
        f"- rejectedCount: {summary['rejectedCount']}",
        f"- researchEligibleByTimeframe: {summary['researchEligibleByTimeframe']}",
        "",
    ]
    for timeframe in TIMEFRAMES:
        lines.extend(
            [
                f"## {timeframe.upper()} Candidates",
                "",
                "| Candidate | Tier | PF floor | Expectancy floor | Trades | Failed checks |",
                "| --- | --- | ---: | ---: | ---: | --- |",
            ]
        )
        for item in report["candidatePacks"][timeframe]:
            metrics = item.get("metrics") or {}
            lines.append(
                "| {name} | {tier} | {pf} | {expectancy} | {trades} | {failed} |".format(
                    name=item["displayName"],
                    tier=item["selectionTier"],
                    pf=metrics.get("profitFactor", "--"),
                    expectancy=metrics.get("expectancyR", "--"),
                    trades=metrics.get("tradeCount", "--"),
                    failed=", ".join(item.get("failedSelectionChecks") or []) or "--",
                )
            )
        lines.append("")
    lines.extend(
        [
            "## Interpretation",
            "",
            "- research_eligible 只表示通过当前研究预筛，仍不是正式回测、本地前向或 Demo 晋级结论。",
            "- shadow_only 表示证据方向有价值但仍有明确缺项，只允许继续观察。",
            "- rejected 表示当前定义不应继续晋级；不能为了补足数量而强制放行。",
            "- 同家族参数变体可能高度相关，候选数量不能当作独立风险来源数量。",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--five-minute", default=DEFAULT_FIVE_MINUTE.as_posix())
    parser.add_argument(
        "--fifteen-minute", default=DEFAULT_FIFTEEN_MINUTE.as_posix()
    )
    parser.add_argument("--long-horizon", default=DEFAULT_LONG_HORIZON.as_posix())
    parser.add_argument("--output", default=DEFAULT_OUTPUT.as_posix())
    parser.add_argument("--summary", default=DEFAULT_SUMMARY.as_posix())
    args = parser.parse_args()

    rows = _event_rows(_load(Path(args.five_minute)), "5m")
    rows.extend(_event_rows(_load(Path(args.fifteen_minute)), "15m"))
    long_horizon = _load(Path(args.long_horizon))
    for timeframe in ("1h", "4h", "1d"):
        if timeframe == "1h":
            rows.extend(
                {
                    **dict(item),
                    "executableWorkflowAvailable": True,
                }
                for item in long_horizon["candidatePacks"][timeframe]
            )
        else:
            rows.extend(
                normalize_long_horizon_candidate(item)
                for item in long_horizon["candidatePacks"][timeframe]
            )

    report = build_cross_timeframe_candidate_inventory(rows)
    report["generatedAt"] = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    report["sourceArtifacts"] = {
        "5m": str(args.five_minute),
        "15m": str(args.fifteen_minute),
        "longHorizon": str(args.long_horizon),
    }
    report["reportHash"] = stable_hash(
        {
            key: value
            for key, value in report.items()
            if key not in {"generatedAt", "reportHash"}
        },
        prefix="cross-timeframe-candidate-inventory",
    )
    write_json_atomic(Path(args.output), report)
    summary_path = Path(args.summary)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(render_summary(report), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
