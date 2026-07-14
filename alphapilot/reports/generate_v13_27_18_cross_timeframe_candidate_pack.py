"""Generate the V13.27.18 executable five-timeframe research pack."""

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
)
from alphapilot.reports.v13_27_18_cross_timeframe_candidate_pack import (
    build_v13_27_18_candidate_rows,
)
from alphapilot.short_cycle.event_window_candidates import (
    cross_timeframe_workflow_candidate_pool,
)


DEFAULT_SOURCE = Path("reports/v13_27_17_cross_timeframe_candidate_inventory.json")
DEFAULT_OUTPUT = Path("reports/v13_27_18_cross_timeframe_candidate_pack.json")
DEFAULT_SUMMARY = Path("reports/v13_27_18_cross_timeframe_candidate_pack_summary.md")


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _source_rows(report: Mapping[str, Any]) -> list[dict[str, Any]]:
    packs = dict(report.get("candidatePacks") or {})
    return [dict(item) for timeframe in TIMEFRAMES for item in packs.get(timeframe, [])]


def render_summary(report: Mapping[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# AlphaPilot V13.27.18 Cross-Timeframe Executable Candidate Pack",
        "",
        "本报告把既有开发筛选证据绑定到当前可执行定义。每周期 5 条是研究库存，",
        "不代表全部通过正式回测；影子候选不得冒充正式通过。",
        "",
        "## Summary",
        "",
        f"- candidateCount: {summary['candidateCount']}",
        f"- candidateCountByTimeframe: {summary['candidateCountByTimeframe']}",
        f"- researchEligibleCount: {summary['researchEligibleCount']}",
        f"- shadowOnlyCount: {summary['shadowOnlyCount']}",
        f"- rejectedCount: {summary['rejectedCount']}",
        f"- executableResearchEligibleCount: {summary['executableResearchEligibleCount']}",
        f"- researchEligibleByTimeframe: {summary['researchEligibleByTimeframe']}",
        "",
    ]
    for timeframe in TIMEFRAMES:
        lines.extend(
            [
                f"## {timeframe.upper()}",
                "",
                "| Candidate | Tier | Trades | PF | Expectancy R | Formal data plan |",
                "| --- | --- | ---: | ---: | ---: | --- |",
            ]
        )
        for item in report["candidatePacks"][timeframe]:
            metrics = dict(item.get("metrics") or {})
            plan = dict(item["formalDataPlan"])
            lines.append(
                "| {name} | {tier} | {trades} | {pf} | {expectancy} | {signal}/{execution}/{fallback} |".format(
                    name=item["displayName"],
                    tier=item["selectionTier"],
                    trades=metrics.get("tradeCount", "--"),
                    pf=metrics.get("profitFactor", "--"),
                    expectancy=metrics.get("expectancyR", "--"),
                    signal=plan["signal"],
                    execution=plan["execution"],
                    fallback=plan["fallback"] or "--",
                )
            )
        lines.append("")
    lines.extend(
        [
            "## Boundaries",
            "",
            "- targetR 固定不低于 2R；手续费、滑点和压力测试保持不变。",
            "- 选择只使用开发、时间验证和符号留出证据；锁定样本不参与选择。",
            "- 4H 正式数据计划复用 15m/1h，1D 复用 1h/4h，避免重复下载。",
            "- 正式候选池只包含 OKX instCategory=1 加密 USDT 永续，并按 24H 报价成交额排序。",
            "- 当前 Top50 是采集时点快照，不是历史逐时点成分；幸存者与上市偏差仍需单独稳健性验证。",
            "- 研究筛选不会创建 Demo 或 Live Release，也不会调用交易接口。",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default=DEFAULT_SOURCE.as_posix())
    parser.add_argument("--output", default=DEFAULT_OUTPUT.as_posix())
    parser.add_argument("--summary", default=DEFAULT_SUMMARY.as_posix())
    args = parser.parse_args()

    source = _load(Path(args.source))
    rows = build_v13_27_18_candidate_rows(
        cross_timeframe_workflow_candidate_pool(),
        _source_rows(source),
    )
    report = build_cross_timeframe_candidate_inventory(rows)
    report.update(
        {
            "schemaVersion": "cross_timeframe_candidate_inventory_v13_27_18",
            "generatedAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "sourceArtifacts": {"candidateEvidence": str(args.source)},
            "implementationStatus": {
                "formalSignalAdapter": "available_5m_15m_1h_4h_1d",
                "fourHourSharedDataPlan": "4h_signal_15m_execution_1h_fallback",
                "oneDaySharedDataPlan": "1d_signal_1h_execution_4h_fallback",
                "universeRanking": "okx_public_24h_quote_notional_v1",
                "universeInstrumentCategory": "1",
                "historicalPointInTimeUniverse": False,
                "universeLimitation": (
                    "collection_time_snapshot_survivorship_and_listing_bias"
                ),
            },
        }
    )
    report["reportHash"] = stable_hash(
        {
            key: value
            for key, value in report.items()
            if key not in {"generatedAt", "reportHash"}
        },
        prefix="v13_27_18_cross_timeframe_candidate_pack",
    )
    write_json_atomic(Path(args.output), report)
    summary_path = Path(args.summary)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(render_summary(report), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
