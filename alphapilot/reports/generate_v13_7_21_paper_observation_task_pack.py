"""Generate V13.7.21 paper-observation task pack for the five strategy candidates.

This report converts V13.7.20 research candidates into local observation tasks.
It is research-only. It does not call exchanges, read accounts, create orders,
run exchange Dry-run, or automate trading.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
REPORTS_DIR = ROOT / "reports"
DOCS_DIR = ROOT / "docs"

VERSION = "V13.7.21"
REPORT_ID = "v13_7_21_paper_observation_task_pack"
SOURCE = "alphapilot_paper_observation_task_pack_v13_7_21"
INPUT_REPORT = REPORTS_DIR / "v13_7_20_five_strategy_candidate_factory_report.json"
REPORT_PATH = REPORTS_DIR / "v13_7_21_paper_observation_task_pack_report.json"
SUMMARY_PATH = REPORTS_DIR / "v13_7_21_paper_observation_task_pack_summary.md"
DOC_PATH = DOCS_DIR / "V13.7.21-paper-observation-task-pack.md"

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


def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _family_label(family: str, display_name: str) -> str:
    display = display_name.lower()
    if family == "breakout":
        return "趋势突破确认"
    if family == "mean_reversion":
        return "横盘超卖修复"
    if family == "squeeze_breakout" and "broad" in display:
        return "广谱低波突破"
    if family == "squeeze_breakout":
        return "趋势低波突破"
    labels = {
        "trend_pullback": "趋势回撤确认",
        "continuation": "趋势延续确认",
        "recovery_reclaim": "修复重回均线",
        "low_vol_trend": "低波趋势跟随",
    }
    return labels.get(family, display_name or "低频候选")


def _candidate_title(candidate: dict[str, Any]) -> str:
    spec = candidate.get("spec") if isinstance(candidate.get("spec"), dict) else {}
    timeframe = str(spec.get("timeframe") or "").upper()
    family = str(spec.get("family") or "")
    atr = spec.get("atrMultiplier")
    label = _family_label(family, str(candidate.get("displayName") or ""))
    return f"{timeframe} {label} ATR{atr}" if atr is not None else f"{timeframe} {label}"


def _weak_points(candidate: dict[str, Any]) -> list[str]:
    weak: list[str] = []
    for row in candidate.get("walkForward", []):
        if not isinstance(row, dict):
            continue
        split = str(row.get("splitId") or "unknown")
        trades = int(row.get("tradeCount") or 0)
        profit_factor = _as_float(row.get("profitFactor"))
        total_return = _as_float(row.get("totalReturnPct"))
        if trades < 10:
            weak.append(f"{split} sample is thin: {trades} trades.")
        if profit_factor is not None and profit_factor < 1.1:
            weak.append(f"{split} profit factor is close to break-even: {profit_factor}.")
        if total_return is not None and total_return < 1:
            weak.append(f"{split} return is thin: {total_return}%.")
    metrics = candidate.get("metrics") if isinstance(candidate.get("metrics"), dict) else {}
    if int(metrics.get("maxConsecutiveLosses") or 0) >= 10:
        weak.append(f"Historical max consecutive losses reached {metrics.get('maxConsecutiveLosses')}.")
    if not weak:
        weak.append("No major split-level weakness detected, but forward observation is still required.")
    return weak[:8]


def _observation_profile(candidate: dict[str, Any]) -> dict[str, Any]:
    weak = _weak_points(candidate)
    has_thin_sample = any("sample is thin" in item for item in weak)
    has_break_even_split = any("break-even" in item or "return is thin" in item for item in weak)
    if has_thin_sample and has_break_even_split:
        confidence = "cautious"
        observation_days = 120
        target_closed_samples = 30
    elif has_thin_sample or has_break_even_split:
        confidence = "medium_caution"
        observation_days = 90
        target_closed_samples = 25
    else:
        confidence = "standard"
        observation_days = 60
        target_closed_samples = 25
    return {
        "confidenceTier": confidence,
        "observationDays": observation_days,
        "targetClosedSamples": target_closed_samples,
        "weakPoints": weak,
    }


def _top_pairs(candidate: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [row for row in candidate.get("byPair", []) if isinstance(row, dict)]
    positive = [
        row for row in rows
        if float(row.get("totalReturnPct") or 0) > 0 and int(row.get("tradeCount") or 0) >= 3
    ]
    positive.sort(
        key=lambda row: (
            float(row.get("profitFactor") or 0),
            float(row.get("totalReturnPct") or 0),
            int(row.get("tradeCount") or 0),
        ),
        reverse=True,
    )
    return [
        {
            "pair": row.get("pair"),
            "tradeCount": row.get("tradeCount"),
            "winRatePct": row.get("winRatePct"),
            "profitFactor": row.get("profitFactor"),
            "totalReturnPct": row.get("totalReturnPct"),
            "maxDrawdownPct": row.get("maxDrawdownPct"),
        }
        for row in positive[:8]
    ]


def _avoid_pairs(candidate: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [row for row in candidate.get("byPair", []) if isinstance(row, dict)]
    negative = [
        row for row in rows
        if int(row.get("tradeCount") or 0) >= 3 and float(row.get("totalReturnPct") or 0) < 0
    ]
    negative.sort(key=lambda row: float(row.get("totalReturnPct") or 0))
    return [
        {
            "pair": row.get("pair"),
            "tradeCount": row.get("tradeCount"),
            "profitFactor": row.get("profitFactor"),
            "totalReturnPct": row.get("totalReturnPct"),
        }
        for row in negative[:8]
    ]


def _task_from_candidate(candidate: dict[str, Any], rank: int) -> dict[str, Any]:
    candidate_id = str(candidate.get("candidateId") or f"candidate_{rank}")
    spec = candidate.get("spec") if isinstance(candidate.get("spec"), dict) else {}
    metrics = candidate.get("metrics") if isinstance(candidate.get("metrics"), dict) else {}
    approval = candidate.get("approval") if isinstance(candidate.get("approval"), dict) else {}
    profile = _observation_profile(candidate)
    title = _candidate_title(candidate)
    target_closed_samples = profile["targetClosedSamples"]
    return {
        "taskId": f"v13_7_21_observe_{candidate_id}",
        "strategyId": f"v13_7_20_{candidate_id}",
        "candidateId": candidate_id,
        "title": title,
        "displaySubtitle": "固定 2R · 本地纸面观察 · 不自动交易",
        "status": "planned_paper_observation",
        "rank": rank,
        "sourceReport": str(INPUT_REPORT.relative_to(ROOT)),
        "timeframe": spec.get("timeframe"),
        "family": spec.get("family"),
        "btcRegimes": spec.get("btcRegimes") if isinstance(spec.get("btcRegimes"), list) else [],
        "targetRewardRiskRatio": metrics.get("targetRewardRiskRatio") or spec.get("targetRewardRiskRatio"),
        "historicalMetrics": {
            "tradeCount": metrics.get("tradeCount"),
            "winRatePct": metrics.get("winRatePct"),
            "profitFactor": metrics.get("profitFactor"),
            "totalReturnPct": metrics.get("totalReturnPct"),
            "maxDrawdownPct": metrics.get("maxDrawdownPct"),
            "maxConsecutiveLosses": metrics.get("maxConsecutiveLosses"),
        },
        "observationPlan": {
            "confidenceTier": profile["confidenceTier"],
            "observationDays": profile["observationDays"],
            "targetClosedSamples": target_closed_samples,
            "minimumRuleMatchedSignals": max(10, target_closed_samples // 2),
            "recordNoSignalDays": True,
            "recordInvalidatedSetups": True,
            "recordMissedSignals": True,
            "recordPairLevelDrift": True,
        },
        "recommendedPairs": _top_pairs(candidate),
        "avoidUntilReviewedPairs": _avoid_pairs(candidate),
        "weakPoints": profile["weakPoints"],
        "dailyLogFields": [
            "date",
            "pair",
            "timeframe",
            "signalObserved",
            "ruleMatched",
            "entryContext",
            "btcRegime",
            "paperOutcomeR",
            "invalidatedReason",
            "riskNote",
            "screenshotOrChartNote",
        ],
        "promotionCriteria": [
            f"Collect at least {target_closed_samples} closed local paper-observation samples.",
            "Forward paper-observation profit factor must remain above 1.20.",
            "Forward paper-observation average R must remain positive.",
            "Max drawdown must stay within the historical drawdown plus a documented tolerance.",
            "No unreviewed regime drift, liquidity issue, or data-quality issue may remain open.",
        ],
        "rejectionCriteria": [
            "Reject or redesign if forward paper-observation PF is below 1.0 after the target sample count.",
            "Reject or redesign if three or more severe data-quality or liquidity warnings appear.",
            "Reject or redesign if observed signals concentrate in pairs that were historically weak.",
            "Reject or redesign if the rule requires discretionary exceptions to look acceptable.",
        ],
        "allowedNextAction": "local_paper_observation_only",
        "blockedActions": [
            "exchange_dry_run",
            "live_trading",
            "order_creation",
            "automatic_trading",
            "api_key_storage",
        ],
        "approval": {
            "paperObservationApproved": bool(approval.get("paperObservationApproved")),
            "dryRunApproved": False,
            "liveTradingApproved": False,
        },
    }


def build_report() -> dict[str, Any]:
    source = _read_json(INPUT_REPORT)
    factory = source.get("factory") if isinstance(source.get("factory"), dict) else {}
    candidates = factory.get("approvedCandidates") if isinstance(factory.get("approvedCandidates"), list) else []
    tasks = [_task_from_candidate(candidate, index) for index, candidate in enumerate(candidates, start=1)]
    cautious_count = sum(1 for task in tasks if task["observationPlan"]["confidenceTier"] != "standard")
    report = {
        "reportId": REPORT_ID,
        "version": VERSION,
        "status": "completed" if tasks else "blocked_no_candidates",
        "generatedAt": _now(),
        "source": SOURCE,
        "objective": "Convert V13.7.20 approved research candidates into local paper-observation tasks.",
        "inputReports": [str(INPUT_REPORT.relative_to(ROOT))],
        "summary": {
            "taskCount": len(tasks),
            "plannedPaperObservationCount": len(tasks),
            "standardConfidenceCount": sum(1 for task in tasks if task["observationPlan"]["confidenceTier"] == "standard"),
            "cautiousObservationCount": cautious_count,
            "targetClosedSamplesTotal": sum(int(task["observationPlan"]["targetClosedSamples"]) for task in tasks),
            "dryRunApproved": False,
            "liveTradingApproved": False,
            "nextStep": "Use the desktop console to track these local paper-observation tasks; do not move to exchange Dry-run.",
        },
        "paperObservationTasks": tasks,
        "dryRunApproved": False,
        "liveTradingApproved": False,
        "safetyBoundary": SAFETY_BOUNDARY,
    }
    return report


def render_summary(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# AlphaPilot V13.7.21 Paper Observation Task Pack",
        "",
        "This report turns V13.7.20 research candidates into local paper-observation tasks.",
        "It is not exchange Dry-run, not live trading, not an order system, and not trading advice.",
        "",
        "## Summary",
        "",
        f"- status: {report['status']}",
        f"- taskCount: {summary['taskCount']}",
        f"- plannedPaperObservationCount: {summary['plannedPaperObservationCount']}",
        f"- standardConfidenceCount: {summary['standardConfidenceCount']}",
        f"- cautiousObservationCount: {summary['cautiousObservationCount']}",
        f"- targetClosedSamplesTotal: {summary['targetClosedSamplesTotal']}",
        f"- dryRunApproved: {summary['dryRunApproved']}",
        f"- liveTradingApproved: {summary['liveTradingApproved']}",
        "",
        "## Observation Tasks",
        "",
        "| Rank | Task | Tier | Days | Target Samples | Historical Trades | PF | Win % | DD % |",
        "| ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for task in report["paperObservationTasks"]:
        metrics = task["historicalMetrics"]
        plan = task["observationPlan"]
        lines.append(
            "| {rank} | {title} | {tier} | {days} | {samples} | {trades} | {pf} | {win} | {dd} |".format(
                rank=task["rank"],
                title=task["title"],
                tier=plan["confidenceTier"],
                days=plan["observationDays"],
                samples=plan["targetClosedSamples"],
                trades=metrics.get("tradeCount"),
                pf=metrics.get("profitFactor"),
                win=metrics.get("winRatePct"),
                dd=metrics.get("maxDrawdownPct"),
            )
        )
    for task in report["paperObservationTasks"]:
        lines.extend(["", f"### {task['title']}", ""])
        lines.append("Weak points:")
        for item in task["weakPoints"]:
            lines.append(f"- {item}")
        lines.append("")
        lines.append("Promotion criteria:")
        for item in task["promotionCriteria"]:
            lines.append(f"- {item}")
        lines.append("")
        lines.append("Rejection criteria:")
        for item in task["rejectionCriteria"]:
            lines.append(f"- {item}")

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
        "dryRunApproved": report["summary"]["dryRunApproved"],
        "liveTradingApproved": report["summary"]["liveTradingApproved"],
        "nextStep": report["summary"]["nextStep"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
