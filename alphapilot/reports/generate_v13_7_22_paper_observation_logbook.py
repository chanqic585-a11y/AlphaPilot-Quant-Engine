"""Generate V13.7.22 local paper-observation logbook baseline.

This report starts the observation journal for the five V13.7.21 task-pack
items. It is local research bookkeeping only. It does not call exchanges,
read accounts, create orders, run exchange Dry-run, or automate trading.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
REPORTS_DIR = ROOT / "reports"
DOCS_DIR = ROOT / "docs"

VERSION = "V13.7.22"
REPORT_ID = "v13_7_22_paper_observation_logbook"
SOURCE = "alphapilot_paper_observation_logbook_v13_7_22"
INPUT_REPORT = REPORTS_DIR / "v13_7_21_paper_observation_task_pack_report.json"
REPORT_PATH = REPORTS_DIR / "v13_7_22_paper_observation_logbook_report.json"
SUMMARY_PATH = REPORTS_DIR / "v13_7_22_paper_observation_logbook_summary.md"
DOC_PATH = DOCS_DIR / "V13.7.22-paper-observation-logbook.md"

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

LOG_TYPES = [
    {
        "logType": "no_signal",
        "label": "No Signal",
        "meaning": "The market was checked, but the rule did not show a usable paper-observation event.",
    },
    {
        "logType": "signal_seen",
        "label": "Signal Seen",
        "meaning": "A possible setup appeared, but it still needs rule confirmation.",
    },
    {
        "logType": "rule_matched",
        "label": "Rule Matched",
        "meaning": "The written research rule matched and should be tracked as a closed paper sample later.",
    },
    {
        "logType": "missed",
        "label": "Missed",
        "meaning": "A setup was discovered after the fact; record it without rewriting history.",
    },
    {
        "logType": "invalidated",
        "label": "Invalidated",
        "meaning": "The setup failed one of the rule, data-quality, liquidity, or regime conditions.",
    },
    {
        "logType": "risk_warning",
        "label": "Risk Warning",
        "meaning": "The setup raised a risk, liquidity, data, or discretionary-exception warning.",
    },
]

DAILY_FIELDS = [
    "date",
    "taskId",
    "candidateId",
    "pair",
    "timeframe",
    "logType",
    "signalObserved",
    "ruleMatched",
    "paperOutcomeR",
    "btcRegime",
    "invalidatedReason",
    "riskNote",
    "screenshotOrChartNote",
]


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _task_log_template(task: dict[str, Any]) -> dict[str, Any]:
    plan = task.get("observationPlan") if isinstance(task.get("observationPlan"), dict) else {}
    metrics = task.get("historicalMetrics") if isinstance(task.get("historicalMetrics"), dict) else {}
    return {
        "taskId": task.get("taskId"),
        "candidateId": task.get("candidateId"),
        "title": task.get("title"),
        "status": "ready_for_local_logging",
        "targetClosedSamples": plan.get("targetClosedSamples"),
        "observationDays": plan.get("observationDays"),
        "currentLogCount": 0,
        "ruleMatchedCount": 0,
        "closedPaperSampleCount": 0,
        "latestLogAt": None,
        "historicalReference": {
            "tradeCount": metrics.get("tradeCount"),
            "winRatePct": metrics.get("winRatePct"),
            "profitFactor": metrics.get("profitFactor"),
            "maxDrawdownPct": metrics.get("maxDrawdownPct"),
        },
        "dailyFields": DAILY_FIELDS,
        "allowedLogTypes": [item["logType"] for item in LOG_TYPES],
        "blockedActions": [
            "exchange_dry_run",
            "live_trading",
            "order_creation",
            "automatic_trading",
            "api_key_storage",
        ],
    }


def build_report() -> dict[str, Any]:
    source = _read_json(INPUT_REPORT)
    tasks = source.get("paperObservationTasks") if isinstance(source.get("paperObservationTasks"), list) else []
    templates = [_task_log_template(task) for task in tasks if isinstance(task, dict)]
    target_total = sum(int(item.get("targetClosedSamples") or 0) for item in templates)
    return {
        "reportId": REPORT_ID,
        "version": VERSION,
        "status": "completed" if templates else "blocked_no_task_pack",
        "generatedAt": _now(),
        "source": SOURCE,
        "objective": "Start a local daily paper-observation logbook for V13.7.21 tasks.",
        "inputReports": [str(INPUT_REPORT.relative_to(ROOT))],
        "summary": {
            "taskCount": len(templates),
            "readyForLoggingCount": len(templates),
            "currentLogCount": 0,
            "ruleMatchedCount": 0,
            "closedPaperSampleCount": 0,
            "targetClosedSamplesTotal": target_total,
            "dryRunApproved": False,
            "liveTradingApproved": False,
            "nextStep": "Record daily paper-observation logs in the desktop console before considering any stricter simulation stage.",
        },
        "allowedLogTypes": LOG_TYPES,
        "dailyFields": DAILY_FIELDS,
        "taskLogTemplates": templates,
        "dryRunApproved": False,
        "liveTradingApproved": False,
        "safetyBoundary": SAFETY_BOUNDARY,
    }


def render_summary(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# AlphaPilot V13.7.22 Paper Observation Logbook",
        "",
        "This report initializes the local paper-observation journal for the five V13.7.21 tasks.",
        "It is not exchange Dry-run, not live trading, not an order system, and not trading advice.",
        "",
        "## Summary",
        "",
        f"- status: {report['status']}",
        f"- taskCount: {summary['taskCount']}",
        f"- readyForLoggingCount: {summary['readyForLoggingCount']}",
        f"- currentLogCount: {summary['currentLogCount']}",
        f"- ruleMatchedCount: {summary['ruleMatchedCount']}",
        f"- closedPaperSampleCount: {summary['closedPaperSampleCount']}",
        f"- targetClosedSamplesTotal: {summary['targetClosedSamplesTotal']}",
        f"- dryRunApproved: {summary['dryRunApproved']}",
        f"- liveTradingApproved: {summary['liveTradingApproved']}",
        "",
        "## Log Types",
        "",
    ]
    for item in report["allowedLogTypes"]:
        lines.append(f"- `{item['logType']}`: {item['meaning']}")
    lines.extend([
        "",
        "## Task Log Templates",
        "",
        "| Task | Target Samples | Observation Days | Current Logs | Rule Matches |",
        "| --- | ---: | ---: | ---: | ---: |",
    ])
    for item in report["taskLogTemplates"]:
        lines.append(
            "| {title} | {target} | {days} | {logs} | {matches} |".format(
                title=item.get("title") or item.get("taskId"),
                target=item.get("targetClosedSamples"),
                days=item.get("observationDays"),
                logs=item.get("currentLogCount"),
                matches=item.get("ruleMatchedCount"),
            )
        )
    lines.extend(["", "## Safety Boundary", ""])
    for key, value in report["safetyBoundary"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Next Step", "", summary["nextStep"], ""])
    return "\n".join(lines)


def main() -> None:
    report = build_report()
    _write_json(REPORT_PATH, report)
    summary = render_summary(report)
    _write_text(SUMMARY_PATH, summary)
    _write_text(DOC_PATH, summary)
    print(json.dumps({
        "status": report["status"],
        "taskCount": report["summary"]["taskCount"],
        "targetClosedSamplesTotal": report["summary"]["targetClosedSamplesTotal"],
        "currentLogCount": report["summary"]["currentLogCount"],
        "dryRunApproved": report["summary"]["dryRunApproved"],
        "liveTradingApproved": report["summary"]["liveTradingApproved"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
