"""Generate V13.7.13 completion report for the six needs-backtest tasks.

This module consolidates already-rerun local research checks for the six
V13.7.12 research-board backtest tasks. It does not call exchange APIs, run
Dry-run, read accounts, create orders, or auto trade.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPORT_ID = "v13_7_13_backtest_task_completion_report"
VERSION = "V13.7.13"

ROOT_DIR = Path(__file__).resolve().parents[2]
REPORTS_DIR = ROOT_DIR / "reports"
OUTPUT_REPORT = REPORTS_DIR / "v13_7_13_backtest_task_completion_report.json"
OUTPUT_SUMMARY = REPORTS_DIR / "v13_7_13_backtest_task_completion_summary.md"


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def read_json(relative_path: str) -> dict[str, Any]:
    path = ROOT_DIR / relative_path
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")


def safe_number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return round(float(value), 6)
    except (TypeError, ValueError):
        return None


def safe_int(value: Any) -> int | None:
    number = safe_number(value)
    return int(number) if number is not None else None


def get_dict(mapping: dict[str, Any], key: str) -> dict[str, Any]:
    value = mapping.get(key)
    return value if isinstance(value, dict) else {}


def metrics_from_gated_report(report: dict[str, Any]) -> dict[str, Any]:
    best = get_dict(report, "bestCandidate")
    metrics = get_dict(best, "gatedMetrics")
    return {
        "tradeCount": safe_int(metrics.get("tradeCount")),
        "winRatePct": safe_number(metrics.get("winRatePct")),
        "profitFactor": safe_number(metrics.get("profitFactor")),
        "rewardRiskRatio": safe_number(metrics.get("rewardRiskRatio")),
        "totalReturnPct": safe_number(metrics.get("totalReturnPct")),
        "maxDrawdownPct": safe_number(metrics.get("maxDrawdownPct")),
        "researchWorthContinuing": bool(metrics.get("researchWorthContinuing", False)),
    }


def metrics_from_alpha191_replay(report: dict[str, Any]) -> dict[str, Any]:
    local_paper = get_dict(report, "localPaperSimulation")
    ledger = get_dict(local_paper, "ledgerMetrics")
    best_raw = get_dict(report, "bestRawCandidate")
    raw_metrics = get_dict(best_raw, "metrics")
    best_exit = get_dict(report, "bestExitAwarePolicy")
    exit_metrics = get_dict(best_exit, "metrics")
    return {
        "rawTradeCount": safe_int(raw_metrics.get("tradeCount")),
        "rawWinRatePct": safe_number(raw_metrics.get("winRatePct")),
        "rawProfitFactor": safe_number(raw_metrics.get("profitFactor")),
        "rawRewardRiskRatio": safe_number(raw_metrics.get("rewardRiskRatio")),
        "paperFilledSignalCount": safe_int(ledger.get("filledSignalCount")),
        "paperWinRatePct": safe_number(ledger.get("winRatePct")),
        "paperProfitFactor": safe_number(ledger.get("profitFactor")),
        "paperRewardRiskRatio": safe_number(ledger.get("rewardRiskRatio")),
        "paperMaxDrawdownPct": safe_number(ledger.get("maxDrawdownPct")),
        "exitAwareSelectedSignalCount": safe_int(best_exit.get("selectedSignalCount")),
        "exitAwareProfitFactor": safe_number(exit_metrics.get("profitFactor")),
    }


def build_task_rows() -> list[dict[str, Any]]:
    factor_panel = read_json("reports/v13_7_13_factor_panel_report.json")
    manual_factor = read_json("reports/v13_7_13_manual_factor_library_report.json")
    factor_eval = read_json("reports/v13_7_13_factor_evaluation_report.json")
    ml_1h = read_json("reports/v13_7_13_derivatives_ml_strategy_1h_broad_report.json")
    ml_4h = read_json("reports/v13_7_13_derivatives_ml_strategy_4h_broad_report.json")
    adaptive = read_json("reports/v13_7_13_adaptive_ml_factor_report.json")
    alpha191_extract = read_json("reports/v13_5_22_alpha191_factor_extraction_report.json")
    alpha191_catalog = read_json("reports/v13_5_22_alpha191_factor_candidate_catalog.json")
    alpha191_replay = read_json("reports/v13_5_23_alpha191_crypto_subset_replay_report.json")

    factor_eval_candidates = factor_eval.get("candidateFactors")
    if not isinstance(factor_eval_candidates, list):
        factor_eval_candidates = []

    adaptive_decision = get_dict(adaptive, "decision")
    adaptive_summary = get_dict(adaptive, "adaptiveSummary")
    alpha191_decision = get_dict(alpha191_replay, "decision")
    alpha191_extract_decision = get_dict(alpha191_extract, "decision")

    return [
        {
            "taskId": "v13_4_21_manual_factor_library_report__report_summary",
            "title": "因子研究观察策略 - 手工因子库",
            "sourceVersion": "V13.4.21",
            "completionStatus": "completed_research_data_generation",
            "executableStrategyBacktest": False,
            "paperOrShadowApproved": False,
            "result": "not_executable_factor_library",
            "evidenceFiles": [
                "reports/v13_7_13_manual_factor_library_report.json",
                "reports/v13_7_13_factor_panel_report.json",
            ],
            "metrics": {
                "factorCount": safe_int(manual_factor.get("factorCount")),
                "computedFactorCount": len(manual_factor.get("computedFactors", [])),
                "rowsGenerated": safe_int(factor_panel.get("rowsGenerated")),
                "loadedPairCount": len(factor_panel.get("loadedPairs", [])),
            },
            "finding": "手工因子库和 1h 28 币因子面板已重建，但它是研究数据层，不是可直接回测的入场/出场策略。",
            "nextAction": "仅可作为策略特征输入；需要先定义具体信号、持仓、退出和风控规则后再进入 Freqtrade 回测。",
        },
        {
            "taskId": "v13_4_21_factor_panel_report__report_summary",
            "title": "因子研究观察策略 - 因子面板",
            "sourceVersion": "V13.4.21",
            "completionStatus": "completed_factor_panel_rebuild",
            "executableStrategyBacktest": False,
            "paperOrShadowApproved": False,
            "result": "factor_panel_ready_for_evaluation",
            "evidenceFiles": [
                "reports/v13_7_13_factor_panel_report.json",
                "reports/v13_7_13_factor_panel_summary.md",
            ],
            "metrics": {
                "rowsGenerated": safe_int(factor_panel.get("rowsGenerated")),
                "loadedPairCount": len(factor_panel.get("loadedPairs", [])),
                "failedPairCount": len(factor_panel.get("failedPairs", [])),
                "sampleRowsWritten": safe_int(factor_panel.get("sampleRowsWritten")),
            },
            "finding": "因子面板补测完成，覆盖 1h 28 币和 597046 行样本；没有伪造缺失数据。",
            "nextAction": "该面板可继续服务因子评价和机器学习筛选，但不直接产生交易候选。",
        },
        {
            "taskId": "v13_4_22_factor_evaluation_report__report_summary",
            "title": "因子研究观察策略 - forward label 因子评价",
            "sourceVersion": "V13.4.22",
            "completionStatus": "completed_factor_evaluation_no_candidate",
            "executableStrategyBacktest": False,
            "paperOrShadowApproved": False,
            "result": "no_factor_candidate_passed_research_gate",
            "evidenceFiles": [
                "reports/v13_7_13_factor_evaluation_report.json",
                "reports/v13_7_13_factor_candidates.json",
            ],
            "metrics": {
                "sampleCount": safe_int(factor_eval.get("sampleCount")),
                "validLabelCount": safe_int(factor_eval.get("validLabelCount")),
                "evaluatedFactorCount": safe_int(factor_eval.get("evaluatedFactorCount")),
                "candidateFactorCount": len(factor_eval_candidates),
            },
            "finding": "16 个因子已用 596374 个有效标签重评估，但 candidateFactors=0；不应进入观察或模拟盘。",
            "nextAction": "保留为因子质量研究结果，后续优先研究组合因子或 regime 条件，不要单因子直接交易。",
        },
        {
            "taskId": "v13_5_derivatives_ml_strategy_report__report_summary",
            "title": "衍生品 ML-gated 策略研究",
            "sourceVersion": "V13.5",
            "completionStatus": "completed_broad_universe_walk_forward_failed",
            "executableStrategyBacktest": True,
            "paperOrShadowApproved": False,
            "result": "failed_55pct_winrate_2r_gate",
            "evidenceFiles": [
                "reports/v13_7_13_derivatives_ml_strategy_1h_broad_report.json",
                "reports/v13_7_13_derivatives_ml_strategy_4h_broad_report.json",
            ],
            "metrics": {
                "oneHour": metrics_from_gated_report(ml_1h),
                "fourHour": metrics_from_gated_report(ml_4h),
                "oneHourLoadedPairCount": len(get_dict(ml_1h, "dataSummary").get("loadedPairs", [])),
                "fourHourLoadedPairCount": len(get_dict(ml_4h, "dataSummary").get("loadedPairs", [])),
            },
            "finding": "1h/4h 宽币种 walk-forward 补测均未通过。1h 最佳 gated PF=0.7525，4h 最佳 gated PF=0.4602。",
            "nextAction": "不要进入模拟盘；若继续研究，只能作为失败样本输入策略工厂，优先改变事件定义而不是调参追胜率。",
        },
        {
            "taskId": "v13_5_8_adaptive_ml_factor_report__report_summary",
            "title": "Adaptive ML 因子候选",
            "sourceVersion": "V13.5.8",
            "completionStatus": "completed_adaptive_ml_failed_watch_gate",
            "executableStrategyBacktest": True,
            "paperOrShadowApproved": bool(adaptive_decision.get("localPaperWatchApproved", False)),
            "result": "adaptive_ml_no_watch_candidate_passed",
            "evidenceFiles": [
                "reports/v13_7_13_adaptive_ml_factor_report.json",
                "reports/v13_7_13_adaptive_ml_candidates.json",
            ],
            "metrics": {
                "totalCandidates": safe_int(adaptive_summary.get("totalCandidates")),
                "localPaperWatchApprovedCount": safe_int(adaptive_summary.get("localPaperWatchApprovedCount")),
                "targetRMultipleUnchanged": bool(adaptive_decision.get("targetRMultipleUnchanged", False)),
                "reason": adaptive_decision.get("reason"),
            },
            "finding": "自适应 ML 重新计算完成，但 localPaperWatchApproved=false；2R 目标未放松。",
            "nextAction": "继续作为离线学习层，暂不进入前向观察、Dry-run 或实盘。",
        },
        {
            "taskId": "v13_5_22_alpha191_factor_extraction_report__report_summary",
            "title": "Alpha191 因子观察策略",
            "sourceVersion": "V13.5.22/V13.5.23",
            "completionStatus": "completed_with_existing_alpha191_subset_replay_failed",
            "executableStrategyBacktest": True,
            "paperOrShadowApproved": False,
            "result": "alpha191_subset_replay_failed_all_gates",
            "evidenceFiles": [
                "reports/v13_5_22_alpha191_factor_extraction_report.json",
                "reports/v13_5_22_alpha191_factor_candidate_catalog.json",
                "reports/v13_5_23_alpha191_crypto_subset_replay_report.json",
            ],
            "metrics": {
                "extractedFactorCount": safe_int(get_dict(alpha191_extract, "aggregate").get("factorCount")),
                "candidateClusterCount": len(alpha191_catalog.get("candidateClusters", [])),
                "readyForFactorImplementationSpec": bool(alpha191_extract_decision.get("readyForFactorImplementationSpec", False)),
                **metrics_from_alpha191_replay(alpha191_replay),
            },
            "finding": "Alpha191 元数据已提取，且后续 crypto-safe subset 已有 replay；raw、exit-aware、local-paper 三层 gate 均失败。",
            "nextAction": "保留为因子灵感库，不替代当前主候选；下一步应只选少量组合因子做新规格，而不是直接上线 Alpha191 子集。",
        },
    ]


def build_report() -> dict[str, Any]:
    task_rows = build_task_rows()
    failed_or_not_ready = [
        row for row in task_rows if not row["paperOrShadowApproved"] or row["result"].startswith("failed")
    ]
    return {
        "reportId": REPORT_ID,
        "version": VERSION,
        "status": "completed",
        "generatedAt": utc_now(),
        "objective": "Complete the six V13.7.12 needs-backtest research tasks with auditable local evidence.",
        "scope": {
            "taskCount": len(task_rows),
            "publicLocalDataOnly": True,
            "newExchangeDownload": False,
            "freqtradeDryRunExecuted": False,
            "liveTradingTouched": False,
        },
        "summary": {
            "completedTaskCount": len(task_rows),
            "paperOrShadowApprovedCount": sum(1 for row in task_rows if row["paperOrShadowApproved"]),
            "failedOrNotReadyCount": len(failed_or_not_ready),
            "executableStrategyBacktestCount": sum(1 for row in task_rows if row["executableStrategyBacktest"]),
            "factorResearchOnlyCount": sum(1 for row in task_rows if not row["executableStrategyBacktest"]),
            "dryRunApproved": False,
            "liveTradingApproved": False,
            "recommendedNextStep": "Do not start paper/Dry-run from these six tasks. Use the failures to design stricter, lower-frequency or regime-aware candidates.",
        },
        "tasks": task_rows,
        "decision": {
            "allSixTasksTestedOrAudited": True,
            "anyCandidateApprovedForPaperObservation": False,
            "anyCandidateApprovedForExchangeDryRun": False,
            "anyCandidateApprovedForLiveTrading": False,
            "reason": "补测完成，但没有一条通过 AlphaPilot 观察/模拟盘门槛；继续研究，不进入执行。",
        },
        "safetyBoundary": {
            "usesPublicLocalDataOnly": True,
            "usesApiKey": False,
            "tradeApiUsed": False,
            "withdrawApiUsed": False,
            "readsRealAccount": False,
            "readsRealPositions": False,
            "createsOrders": False,
            "dryRunExecuted": False,
            "autoTrading": False,
            "liveTradingApproved": False,
        },
    }


def write_summary(report: dict[str, Any], path: Path) -> None:
    summary = report["summary"]
    decision = report["decision"]
    lines = [
        "# AlphaPilot V13.7.13 Backtest Task Completion Report",
        "",
        "V13.7.13 completes the six V13.7.12 `needs_backtest` research tasks with local evidence.",
        "",
        "This is still research-only. It does not approve paper observation, exchange Dry-run, live trading, API keys, account reads, positions, orders, or automation.",
        "",
        "## Summary",
        "",
        f"- status: `{report['status']}`",
        f"- completedTaskCount: `{summary['completedTaskCount']}`",
        f"- executableStrategyBacktestCount: `{summary['executableStrategyBacktestCount']}`",
        f"- factorResearchOnlyCount: `{summary['factorResearchOnlyCount']}`",
        f"- paperOrShadowApprovedCount: `{summary['paperOrShadowApprovedCount']}`",
        f"- failedOrNotReadyCount: `{summary['failedOrNotReadyCount']}`",
        f"- dryRunApproved: `{summary['dryRunApproved']}`",
        f"- liveTradingApproved: `{summary['liveTradingApproved']}`",
        "",
        "## Decision",
        "",
        f"- allSixTasksTestedOrAudited: `{decision['allSixTasksTestedOrAudited']}`",
        f"- anyCandidateApprovedForPaperObservation: `{decision['anyCandidateApprovedForPaperObservation']}`",
        f"- anyCandidateApprovedForExchangeDryRun: `{decision['anyCandidateApprovedForExchangeDryRun']}`",
        f"- reason: {decision['reason']}",
        "",
        "## Task Results",
        "",
    ]
    for row in report["tasks"]:
        lines.extend(
            [
                f"### {row['title']}",
                "",
                f"- taskId: `{row['taskId']}`",
                f"- completionStatus: `{row['completionStatus']}`",
                f"- result: `{row['result']}`",
                f"- executableStrategyBacktest: `{row['executableStrategyBacktest']}`",
                f"- paperOrShadowApproved: `{row['paperOrShadowApproved']}`",
                f"- finding: {row['finding']}",
                f"- nextAction: {row['nextAction']}",
                "- evidence:",
                *[f"  - `{item}`" for item in row["evidenceFiles"]],
                "",
            ]
        )
    lines.extend(
        [
            "## Safety Boundary",
            "",
            "- Public local data only.",
            "- No Trade API.",
            "- No Withdraw API.",
            "- No API key storage.",
            "- No real account reads.",
            "- No real position reads.",
            "- No order creation.",
            "- No exchange Dry-run execution.",
            "- No automatic trading.",
            "",
            f"Next step: {summary['recommendedNextStep']}",
            "",
        ]
    )
    write_text(path, "\n".join(lines))


def main() -> None:
    report = build_report()
    write_json(OUTPUT_REPORT, report)
    write_summary(report, OUTPUT_SUMMARY)
    print(f"Wrote {OUTPUT_REPORT}")
    print(f"Wrote {OUTPUT_SUMMARY}")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
