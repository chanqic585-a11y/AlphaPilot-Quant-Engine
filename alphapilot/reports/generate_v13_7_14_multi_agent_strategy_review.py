from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


REPORT_ID = "v13_7_14_multi_agent_strategy_review"
VERSION = "V13.7.14"
SOURCE = "alphapilot_multi_agent_strategy_review_v13_7_14"
ROOT = Path(__file__).resolve().parents[2]
REPORTS_DIR = ROOT / "reports"
DOCS_DIR = ROOT / "docs"
THIRD_PARTY_DIR = ROOT / "third_party" / "tradingagents"


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _metric(metrics: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = _safe_float(metrics.get(key))
        if value is not None:
            return value
    return None


def _data_quality_review(task: dict[str, Any]) -> dict[str, Any]:
    metrics = task.get("metrics") if isinstance(task.get("metrics"), dict) else {}
    sample_count = _metric(metrics, "sampleCount", "validLabelCount", "rowsGenerated", "tradeCount") or 0
    warnings = task.get("warnings") if isinstance(task.get("warnings"), list) else []
    if sample_count >= 100_000 and not warnings:
        verdict = "adequate_for_research"
        score = 82
        notes = ["样本规模足够支撑研究层审查。"]
    elif sample_count >= 1_000:
        verdict = "usable_with_limitations"
        score = 62
        notes = ["样本可用于方向性研究，但仍需要分市场状态和样本外验证。"]
    elif sample_count > 0:
        verdict = "thin_sample"
        score = 38
        notes = ["样本偏少，不能支持模拟盘观察。"]
    else:
        verdict = "not_applicable_or_missing"
        score = 25
        notes = ["没有可量化样本，当前只适合保留为研究资料。"]
    if warnings:
        notes.append(f"存在 {len(warnings)} 条数据警告，需要先消化。")
        score = min(score, 58)
    return {
        "reviewer": "data_quality_reviewer",
        "verdict": verdict,
        "score": score,
        "notes": notes,
    }


def _backtest_validity_review(task: dict[str, Any]) -> dict[str, Any]:
    executable = bool(task.get("executableStrategyBacktest"))
    approved = bool(task.get("paperOrShadowApproved"))
    result = str(task.get("result") or "")
    metrics = task.get("metrics") if isinstance(task.get("metrics"), dict) else {}
    trade_count = _metric(metrics, "tradeCount", "filledSignalCount") or 0
    profit_factor = _metric(metrics, "profitFactor")
    reward_risk = _metric(metrics, "rewardRiskRatio", "rr")
    total_return = _metric(metrics, "totalReturnPct", "totalReturn")
    if approved:
        verdict = "passed_research_gate"
        score = 85
        notes = ["已有观察层批准标记，可以进入人工复核队列。"]
    elif not executable:
        verdict = "research_data_only"
        score = 45
        notes = ["该对象不是完整入场/出场策略，不能按策略回测结论处理。"]
    elif trade_count < 50:
        verdict = "insufficient_trade_count"
        score = 35
        notes = ["交易样本不足，统计不稳定。"]
    elif (profit_factor is not None and profit_factor < 1.0) or (
        total_return is not None and total_return < 0
    ):
        verdict = "failed_performance_gate"
        score = 30
        notes = ["历史样本未通过收益/亏损质量门槛。"]
    elif result and "no" in result:
        verdict = "failed_research_gate"
        score = 36
        notes = ["补测结论明确未通过观察门槛。"]
    else:
        verdict = "needs_more_breakdown"
        score = 52
        notes = ["需要继续拆分市场状态、交易成本和样本外表现。"]
    if reward_risk is not None and reward_risk < 2.0:
        notes.append("2R 目标没有得到历史样本支持。")
        score = min(score, 42)
    return {
        "reviewer": "backtest_validity_reviewer",
        "verdict": verdict,
        "score": score,
        "notes": notes,
    }


def _risk_review(task: dict[str, Any]) -> dict[str, Any]:
    metrics = task.get("metrics") if isinstance(task.get("metrics"), dict) else {}
    max_drawdown = _metric(metrics, "maxDrawdownPct", "maxDrawdownPercent", "maxDD")
    profit_factor = _metric(metrics, "profitFactor")
    win_rate = _metric(metrics, "winRatePct", "winRate")
    notes: list[str] = [
        "保持研究态，不连接交易权限，不创建订单。",
        "任何候选必须先证明滑点、手续费和连续亏损压力测试可接受。",
    ]
    if max_drawdown is not None and max_drawdown > 25:
        verdict = "risk_too_high"
        score = 25
        notes.append("最大回撤过高，当前不能进入模拟盘观察。")
    elif profit_factor is not None and profit_factor < 1:
        verdict = "negative_expectancy_risk"
        score = 32
        notes.append("Profit factor 小于 1，风险收益结构不合格。")
    elif win_rate is not None and win_rate < 35:
        verdict = "low_winrate_fragility"
        score = 40
        notes.append("胜率过低，要求更强的盈亏比和执行稳定性。")
    else:
        verdict = "research_risk_watch"
        score = 58
        notes.append("风险暂未通过观察批准，但可继续研究。")
    return {
        "reviewer": "risk_reviewer",
        "verdict": verdict,
        "score": score,
        "notes": notes,
    }


def _skeptic_review(task: dict[str, Any]) -> dict[str, Any]:
    source_version = str(task.get("sourceVersion") or "")
    title = str(task.get("title") or task.get("taskId") or "")
    executable = bool(task.get("executableStrategyBacktest"))
    notes = [
        "反方审查默认不相信单次回测，要求样本外、跨交易所和市场状态拆分。",
        "不能因为某个指标在样本内看起来有效就进入执行链路。",
    ]
    if "factor" in title.lower() or "因子" in title:
        verdict = "factor_not_strategy"
        score = 34
        notes.append("因子资料还没有转化为可验证策略规则。")
    elif not executable:
        verdict = "not_a_strategy"
        score = 30
        notes.append("没有完整交易规则，因此不能视为策略候选。")
    elif "V13.5" in source_version:
        verdict = "ml_overfit_watch"
        score = 36
        notes.append("机器学习候选需要特别防止过拟合和标签泄漏。")
    else:
        verdict = "needs_independent_replay"
        score = 45
        notes.append("需要独立重放验证后才有资格观察。")
    return {
        "reviewer": "skeptic_reviewer",
        "verdict": verdict,
        "score": score,
        "notes": notes,
    }


def _committee_decision(reviews: list[dict[str, Any]], task: dict[str, Any]) -> dict[str, Any]:
    scores = [_safe_float(item.get("score")) or 0 for item in reviews]
    score = round(sum(scores) / len(scores), 2) if scores else 0
    approved = bool(task.get("paperOrShadowApproved"))
    executable = bool(task.get("executableStrategyBacktest"))
    if approved and score >= 70:
        status = "paper_observation_candidate"
        next_action = "进入人工复核后的纸面观察准备队列。"
    elif executable and score < 45:
        status = "reject_for_now"
        next_action = "暂时淘汰，不进入模拟盘；保留失败原因供后续重构。"
    elif executable:
        status = "needs_more_data"
        next_action = "继续做样本外、跨交易所、成本和极端行情验证。"
    else:
        status = "keep_researching"
        next_action = "保留为研究资料，先转化为明确规则再谈回测。"
    return {
        "reviewer": "research_committee",
        "researchStatus": status,
        "committeeScore": score,
        "paperObservationAllowed": status == "paper_observation_candidate",
        "exchangeDryRunApproved": False,
        "liveTradingApproved": False,
        "reason": "多角色审查完成；本报告只决定研究状态，不生成交易指令。",
        "nextAction": next_action,
    }


def _review_task(task: dict[str, Any]) -> dict[str, Any]:
    reviews = [
        _data_quality_review(task),
        _backtest_validity_review(task),
        _risk_review(task),
        _skeptic_review(task),
    ]
    committee = _committee_decision(reviews, task)
    return {
        "subjectId": task.get("taskId"),
        "title": task.get("title"),
        "sourceVersion": task.get("sourceVersion"),
        "completionStatus": task.get("completionStatus"),
        "executableStrategyBacktest": bool(task.get("executableStrategyBacktest")),
        "sourceFiles": task.get("evidenceFiles") if isinstance(task.get("evidenceFiles"), list) else [],
        "metrics": task.get("metrics") if isinstance(task.get("metrics"), dict) else {},
        "reviewerFindings": reviews,
        "committee": committee,
    }


def _load_tasks() -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    completion_path = REPORTS_DIR / "v13_7_13_backtest_task_completion_report.json"
    completion = _read_json(completion_path)
    if not completion:
        warnings.append(f"Missing input report: {completion_path}")
        return [], warnings
    tasks = completion.get("tasks") if isinstance(completion.get("tasks"), list) else []
    normalized = [task for task in tasks if isinstance(task, dict)]
    if len(normalized) != len(tasks):
        warnings.append("Some task rows were not JSON objects and were skipped.")
    return normalized, warnings


def build_report() -> dict[str, Any]:
    tasks, warnings = _load_tasks()
    reviews = [_review_task(task) for task in tasks]
    status_counts: dict[str, int] = {}
    for item in reviews:
        status = item.get("committee", {}).get("researchStatus", "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
    snapshot_note_path = THIRD_PARTY_DIR / "ALPHAPILOT_SNAPSHOT.md"
    snapshot_license_path = THIRD_PARTY_DIR / "LICENSE"
    report = {
        "reportId": REPORT_ID,
        "version": VERSION,
        "status": "completed" if reviews else "completed_with_no_reviews",
        "generatedAt": _now(),
        "source": SOURCE,
        "objective": (
            "Create a research-only multi-agent review layer inspired by TradingAgents, "
            "mapped into AlphaPilot safety boundaries."
        ),
        "externalReference": {
            "name": "TradingAgents",
            "upstream": "https://github.com/tauricresearch/tradingagents",
            "snapshotPath": str(THIRD_PARTY_DIR),
            "snapshotMetadataPath": str(snapshot_note_path),
            "licensePath": str(snapshot_license_path),
            "license": "Apache-2.0",
            "usageBoundary": "architecture_reference_only_not_execution_adapter",
        },
        "reviewProtocol": {
            "reviewers": [
                "data_quality_reviewer",
                "backtest_validity_reviewer",
                "risk_reviewer",
                "skeptic_reviewer",
                "research_committee",
            ],
            "allowedStatuses": [
                "keep_researching",
                "needs_more_data",
                "reject_for_now",
                "paper_observation_candidate",
            ],
            "forbiddenActions": [
                "no_trade_api",
                "no_withdraw_api",
                "no_api_key_storage",
                "no_real_account_reads",
                "no_real_position_reads",
                "no_order_creation",
                "no_dry_run_execution",
                "no_auto_trading",
            ],
        },
        "summary": {
            "reviewedSubjectCount": len(reviews),
            "statusCounts": status_counts,
            "paperObservationCandidateCount": status_counts.get("paper_observation_candidate", 0),
            "dryRunApproved": False,
            "liveTradingApproved": False,
            "recommendedNextStep": (
                "Keep failed candidates out of execution and use reviewer findings to design "
                "new lower-frequency or regime-aware hypotheses."
            ),
        },
        "reviews": reviews,
        "warnings": warnings,
        "safetyBoundary": {
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
        },
    }
    return report


def build_summary(report: dict[str, Any]) -> str:
    counts = report.get("summary", {}).get("statusCounts", {})
    lines = [
        "# V13.7.14 Multi-Agent Strategy Review",
        "",
        "This is a research-only strategy review layer inspired by TradingAgents architecture.",
        "It does not generate trading commands, connect exchange permissions, or approve dry-run/live trading.",
        "",
        "## Summary",
        "",
        f"- Reviewed subjects: {report.get('summary', {}).get('reviewedSubjectCount')}",
        f"- Paper observation candidates: {report.get('summary', {}).get('paperObservationCandidateCount')}",
        f"- Dry-run approved: {report.get('summary', {}).get('dryRunApproved')}",
        f"- Live trading approved: {report.get('summary', {}).get('liveTradingApproved')}",
        "",
        "## Research Status Counts",
        "",
    ]
    for key in ["paper_observation_candidate", "needs_more_data", "keep_researching", "reject_for_now"]:
        lines.append(f"- {key}: {counts.get(key, 0)}")
    lines.extend([
        "",
        "## Reviewed Subjects",
        "",
    ])
    for item in report.get("reviews", []):
        committee = item.get("committee", {})
        lines.extend([
            f"### {item.get('title') or item.get('subjectId')}",
            "",
            f"- Subject ID: `{item.get('subjectId')}`",
            f"- Research status: `{committee.get('researchStatus')}`",
            f"- Committee score: {committee.get('committeeScore')}",
            f"- Next action: {committee.get('nextAction')}",
            "",
        ])
    lines.extend([
        "## Safety Boundary",
        "",
        "- No Trade API.",
        "- No Withdraw API.",
        "- No exchange API key storage.",
        "- No real account or position reads.",
        "- No order creation.",
        "- No dry-run execution.",
        "- No auto trading.",
        "",
    ])
    return "\n".join(lines)


def main() -> None:
    report = build_report()
    report_path = REPORTS_DIR / f"{REPORT_ID}_report.json"
    summary_path = REPORTS_DIR / f"{REPORT_ID}_summary.md"
    doc_path = DOCS_DIR / "V13.7.14-multi-agent-strategy-review.md"
    _write_json(report_path, report)
    summary = build_summary(report)
    _write_text(summary_path, summary)
    _write_text(doc_path, summary)
    print(json.dumps({
        "status": report["status"],
        "reportPath": str(report_path),
        "summaryPath": str(summary_path),
        "docPath": str(doc_path),
        "reviewedSubjectCount": report["summary"]["reviewedSubjectCount"],
        "statusCounts": report["summary"]["statusCounts"],
        "dryRunApproved": report["summary"]["dryRunApproved"],
        "liveTradingApproved": report["summary"]["liveTradingApproved"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
