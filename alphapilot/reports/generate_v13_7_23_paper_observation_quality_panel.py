"""Generate V13.7.23 paper-observation quality panel baseline.

This report defines how the desktop console should score the five V13.7.21
paper-observation tasks while they accumulate local observation logs.

It is a research bookkeeping layer only. It does not call exchanges, read
accounts, create orders, run exchange Dry-run, or automate trading.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
REPORTS_DIR = ROOT / "reports"
DOCS_DIR = ROOT / "docs"

VERSION = "V13.7.23"
REPORT_ID = "v13_7_23_paper_observation_quality_panel"
SOURCE = "alphapilot_paper_observation_quality_panel_v13_7_23"
TASK_PACK_PATH = REPORTS_DIR / "v13_7_21_paper_observation_task_pack_report.json"
LOGBOOK_PATH = REPORTS_DIR / "v13_7_22_paper_observation_logbook_report.json"
REPORT_PATH = REPORTS_DIR / "v13_7_23_paper_observation_quality_panel_report.json"
SUMMARY_PATH = REPORTS_DIR / "v13_7_23_paper_observation_quality_panel_summary.md"
DOC_PATH = DOCS_DIR / "V13.7.23-paper-observation-quality-panel.md"

SAFETY_BOUNDARY = {
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

QUALITY_RULES = {
    "scoreMax": 100,
    "components": [
        {
            "component": "logCoverage",
            "weight": 30,
            "meaning": "How much of the target paper-observation sample has been logged.",
        },
        {
            "component": "ruleMatchCoverage",
            "weight": 25,
            "meaning": "Whether rule-matched observations are appearing often enough to be useful.",
        },
        {
            "component": "closedSampleCoverage",
            "weight": 25,
            "meaning": "How many observations have closed paper outcomes.",
        },
        {
            "component": "recency",
            "weight": 10,
            "meaning": "Whether the task has recent local observation activity.",
        },
        {
            "component": "riskHygiene",
            "weight": 10,
            "meaning": "Whether invalidation and risk-warning logs are still manageable.",
        },
    ],
    "labels": [
        {
            "qualityLabel": "not_started",
            "consoleLabel": "未开始",
            "condition": "No local observation logs yet.",
            "nextAction": "Record no-signal days, signal-seen events, rule matches, and invalidations.",
        },
        {
            "qualityLabel": "needs_more_logs",
            "consoleLabel": "需要补日志",
            "condition": "Some logs exist, but log coverage is still thin.",
            "nextAction": "Continue daily observation before judging strategy quality.",
        },
        {
            "qualityLabel": "continue_observing",
            "consoleLabel": "继续观察",
            "condition": "Logs and rule matches are developing, but closed samples are not enough yet.",
            "nextAction": "Keep tracking until the target closed sample count is reached.",
        },
        {
            "qualityLabel": "priority_watch",
            "consoleLabel": "优先观察",
            "condition": "Good log coverage, rule matches, and low risk-warning pressure.",
            "nextAction": "Review this task first during daily observation.",
        },
        {
            "qualityLabel": "needs_risk_review",
            "consoleLabel": "需要风险复核",
            "condition": "Invalidation or risk-warning logs are becoming material.",
            "nextAction": "Review weak pairs, regime drift, liquidity, and data-quality notes.",
        },
        {
            "qualityLabel": "pause_candidate",
            "consoleLabel": "暂停候选",
            "condition": "Enough observation exists to show poor signal availability or risk pressure.",
            "nextAction": "Pause or redesign after human review; do not delete the record.",
        },
    ],
    "promotionGate": {
        "minimumClosedSamplesPerTask": "Use each task's targetClosedSamples.",
        "minimumRuleMatchedSignals": "Use each task's minimumRuleMatchedSignals.",
        "forbiddenShortcut": "Never promote because of one attractive event or one backtest metric.",
    },
}


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def metric_number(task: dict[str, Any], key: str, default: float = 0.0) -> float:
    metrics = task.get("historicalMetrics") if isinstance(task.get("historicalMetrics"), dict) else {}
    value = metrics.get(key, default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def baseline_priority_score(task: dict[str, Any]) -> float:
    """Rank initial observation priority from historical context only."""

    profit_factor = metric_number(task, "profitFactor")
    trade_count = metric_number(task, "tradeCount")
    win_rate = metric_number(task, "winRatePct")
    max_drawdown = metric_number(task, "maxDrawdownPct")
    weak_points = task.get("weakPoints") if isinstance(task.get("weakPoints"), list) else []
    plan = task.get("observationPlan") if isinstance(task.get("observationPlan"), dict) else {}
    confidence_bonus = 8 if plan.get("confidenceTier") == "standard" else 0

    score = 0.0
    score += min(profit_factor / 2.0, 1.0) * 35
    score += min(trade_count / 250, 1.0) * 20
    score += min(win_rate / 55, 1.0) * 15
    score += max(0.0, 1.0 - max_drawdown / 30) * 15
    score += confidence_bonus
    score -= min(len(weak_points) * 3, 12)
    return round(max(0.0, min(score, 100.0)), 2)


def initial_quality_row(task: dict[str, Any]) -> dict[str, Any]:
    plan = task.get("observationPlan") if isinstance(task.get("observationPlan"), dict) else {}
    target_samples = int(plan.get("targetClosedSamples") or 25)
    minimum_rule_matches = int(plan.get("minimumRuleMatchedSignals") or max(5, round(target_samples * 0.4)))
    baseline_score = baseline_priority_score(task)
    baseline_rank_hint = (
        "priority_watch_seed"
        if baseline_score >= 70
        else "continue_observing_seed"
        if baseline_score >= 55
        else "cautious_seed"
    )
    return {
        "taskId": task.get("taskId"),
        "strategyId": task.get("strategyId"),
        "candidateId": task.get("candidateId"),
        "title": task.get("title"),
        "family": task.get("family"),
        "timeframe": task.get("timeframe"),
        "targetClosedSamples": target_samples,
        "minimumRuleMatchedSignals": minimum_rule_matches,
        "baselinePriorityScore": baseline_score,
        "baselineRankHint": baseline_rank_hint,
        "qualityLabel": "not_started",
        "qualityScore": 0,
        "localLogCount": 0,
        "ruleMatchedCount": 0,
        "closedPaperSampleCount": 0,
        "riskWarningCount": 0,
        "invalidatedCount": 0,
        "nextAction": "Start local paper-observation logging in the desktop console.",
    }


def markdown_summary(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# AlphaPilot V13.7.23 - Paper Observation Quality Panel",
        "",
        "V13.7.23 adds a report-only scoring model for the five V13.7.21 local paper-observation tasks.",
        "The desktop console can combine these rules with local logs to show which strategies deserve attention first.",
        "",
        "## Summary",
        "",
        f"- Task count: {summary['taskCount']}",
        f"- Not started count: {summary['notStartedCount']}",
        f"- Target closed samples total: {summary['targetClosedSamplesTotal']}",
        f"- Dry-run approved: {summary['dryRunApproved']}",
        f"- Live trading approved: {summary['liveTradingApproved']}",
        "",
        "## Quality Labels",
        "",
    ]
    for item in QUALITY_RULES["labels"]:
        lines.append(f"- `{item['qualityLabel']}`: {item['consoleLabel']} - {item['condition']}")
    lines.extend([
        "",
        "## Safety Boundary",
        "",
        "- No Trade API.",
        "- No Withdraw API.",
        "- No API key storage.",
        "- No real account or position reads.",
        "- No order creation.",
        "- No exchange Dry-run.",
        "- No live or automatic trading.",
        "",
    ])
    return "\n".join(lines)


def build_report() -> dict[str, Any]:
    task_pack = read_json(TASK_PACK_PATH)
    logbook = read_json(LOGBOOK_PATH)
    tasks = task_pack.get("paperObservationTasks") if isinstance(task_pack.get("paperObservationTasks"), list) else []
    quality_rows = [initial_quality_row(task) for task in tasks if isinstance(task, dict)]
    summary = task_pack.get("summary") if isinstance(task_pack.get("summary"), dict) else {}
    target_total = int(summary.get("targetClosedSamplesTotal") or sum(row["targetClosedSamples"] for row in quality_rows))
    generated_at = now_iso()
    return {
        "reportId": REPORT_ID,
        "version": VERSION,
        "status": "completed" if quality_rows else "no_tasks",
        "generatedAt": generated_at,
        "source": SOURCE,
        "objective": "Define local paper-observation quality scoring for the five V13.7.21 task-pack candidates.",
        "inputReports": [
            str(TASK_PACK_PATH.relative_to(ROOT)),
            str(LOGBOOK_PATH.relative_to(ROOT)),
        ],
        "summary": {
            "taskCount": len(quality_rows),
            "notStartedCount": len(quality_rows),
            "prioritySeedCount": sum(1 for row in quality_rows if row["baselineRankHint"] == "priority_watch_seed"),
            "targetClosedSamplesTotal": target_total,
            "qualityScoreMax": QUALITY_RULES["scoreMax"],
            "dryRunApproved": False,
            "liveTradingApproved": False,
            "nextStep": "Use the desktop console quality panel to decide which local observation task to review first.",
        },
        "qualityRules": QUALITY_RULES,
        "qualityRows": quality_rows,
        "paperObservationLogbookSummary": logbook.get("summary") if isinstance(logbook.get("summary"), dict) else {},
        "dryRunApproved": False,
        "liveTradingApproved": False,
        "safetyBoundary": SAFETY_BOUNDARY,
    }


def main() -> None:
    report = build_report()
    write_json(REPORT_PATH, report)
    SUMMARY_PATH.write_text(markdown_summary(report), encoding="utf-8")
    DOC_PATH.write_text(markdown_summary(report), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
