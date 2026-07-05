"""Generate V13.4.33 low-frequency candidate specification report.

This generator reads V13.4.32 reports and writes research-only candidate specs.
It does not implement strategies, run Freqtrade backtests, download data, enter
Dry-run, use API keys, call private exchange APIs, create orders, or auto trade.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from alphapilot.low_frequency.low_frequency_candidate_specs import build_low_frequency_candidate_spec_package
from alphapilot.low_frequency.low_frequency_candidate_schema import LowFrequencyCandidateSpecReport


REPORT_ID = "v13_4_33_low_frequency_candidate_specs"
VERSION = "V13.4.33"
BASELINE_REPORT_PATH = Path("reports/v13_4_32_low_frequency_baseline_report.json")
DATA_REPORT_PATH = Path("reports/v13_4_32_low_frequency_data_report.json")
BASELINE_SUMMARY_PATH = Path("reports/v13_4_32_low_frequency_baseline_summary.md")
RESEARCH_PLAN_PATH = Path("reports/v13_4_31_low_frequency_research_plan.json")
OUTPUT_JSON = Path("reports/v13_4_33_low_frequency_candidate_spec_report.json")
OUTPUT_SUMMARY = Path("reports/v13_4_33_low_frequency_candidate_spec_summary.md")


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")


def _required_report_summary(path: Path, warnings: list[str]) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Required input report missing: {path.as_posix()}")
    data = _read_json(path)
    summary = {
        "path": path.as_posix(),
        "reportId": data.get("reportId"),
        "status": data.get("status") or data.get("currentStatus"),
        "generatedAt": data.get("generatedAt"),
    }
    if summary["status"] not in {"completed", "valid", "completed_with_warnings"}:
        warnings.append(f"Input report status requires review: {path.as_posix()} status={summary['status']}")
    return summary


def build_report() -> LowFrequencyCandidateSpecReport:
    warnings: list[str] = []
    baseline_report = _read_json(BASELINE_REPORT_PATH)
    data_report_summary = _required_report_summary(DATA_REPORT_PATH, warnings)
    baseline_report_summary = _required_report_summary(BASELINE_REPORT_PATH, warnings)
    if not BASELINE_SUMMARY_PATH.exists():
        warnings.append(f"Baseline summary missing: {BASELINE_SUMMARY_PATH.as_posix()}")
    if not RESEARCH_PLAN_PATH.exists():
        warnings.append(f"Research plan missing: {RESEARCH_PLAN_PATH.as_posix()}")

    spec_package = build_low_frequency_candidate_spec_package(baseline_report)
    pairs = list(baseline_report.get("pairs") or [])
    timeframes = list(baseline_report.get("timeframes") or [])
    return LowFrequencyCandidateSpecReport(
        reportId=REPORT_ID,
        version=VERSION,
        sourceBaselineReport=BASELINE_REPORT_PATH.as_posix(),
        sourceDataReport=DATA_REPORT_PATH.as_posix(),
        sourceResearchPlan=RESEARCH_PLAN_PATH.as_posix(),
        currentStatus="spec_only",
        dryRunApproved=False,
        liveTradingApproved=False,
        scope={
            "pairs": pairs,
            "primaryTimeframes": timeframes,
            "optionalTimeframes": ["1h"],
            "sourceBaselineStatus": baseline_report_summary,
            "sourceDataStatus": data_report_summary,
            "strategyCodeImplemented": False,
            "backtestExecuted": False,
        },
        baselineHurdles=spec_package["baselineHurdles"],
        candidates=spec_package["candidates"],
        directionalScoreFramework=spec_package["directionalScoreFramework"],
        v13_4_34Plan=spec_package["v13_4_34Plan"],
        safetyBoundary={
            "strategyImplemented": False,
            "backtestExecuted": False,
            "dataDownloaded": False,
            "dryRunApproved": False,
            "liveTradingApproved": False,
            "tradeApiUsed": False,
            "withdrawApiUsed": False,
            "apiKeyStored": False,
            "accountRead": False,
            "positionRead": False,
            "orderCreated": False,
            "autoTradingUsed": False,
            "mobileAppModified": False,
        },
        generatedAt=utc_now(),
        warnings=warnings,
        notes=[
            "V13.4.33 is spec-only and report-only.",
            "Candidate specs are research artifacts, not trading systems.",
            "Passing a spec does not approve Dry-run or live trading.",
            "Future V13.4.34 implementation must compare against NoTrade, pair BuyHold, and EqualWeight baselines.",
        ],
    )


def render_summary(report: LowFrequencyCandidateSpecReport) -> str:
    payload = report.to_dict()
    lines = [
        "# AlphaPilot V13.4.33 Low-Frequency Candidate Specification",
        "",
        "V13.4.33 converts the V13.4.32 low-frequency baselines into explicit candidate specs and baseline hurdles. It is spec-only: no strategy implementation, no backtest, no Dry-run, and no live trading approval.",
        "",
        "## Status",
        "",
        f"- currentStatus: {payload['currentStatus']}",
        f"- sourceBaselineReport: {payload['sourceBaselineReport']}",
        f"- dryRunApproved: {payload['dryRunApproved']}",
        f"- liveTradingApproved: {payload['liveTradingApproved']}",
        "",
        "## Universal Hurdles",
        "",
    ]
    for key, value in payload["baselineHurdles"]["universalHurdles"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Candidates", ""])
    for candidate in payload["candidates"]:
        lines.extend(
            [
                f"### {candidate['candidateId']} - {candidate['name']}",
                "",
                f"- direction: {candidate['direction']}",
                f"- timeframe: {candidate['timeframe']}",
                f"- status: {candidate['status']}",
                "- coreConditions:",
            ]
        )
        for condition in candidate["coreConditions"]:
            lines.append(f"  - {condition}")
        lines.append("- validationPlan:")
        for item in candidate["validationPlan"]:
            lines.append(f"  - {item}")
        lines.append("")
    scores = payload["directionalScoreFramework"]
    lines.extend(
        [
            "## Directional Score Framework",
            "",
            f"- status: {scores['status']}",
            f"- scoreRange: {scores['scoreRange']['min']}-{scores['scoreRange']['max']}",
            "- longScoreInputs: " + ", ".join(scores["longScoreInputs"]),
            "- shortScoreInputs: " + ", ".join(scores["shortScoreInputs"]),
            "- avoidScoreInputs: " + ", ".join(scores["avoidScoreInputs"]),
            "",
            "## V13.4.34 Plan",
            "",
            f"- name: {payload['v13_4_34Plan']['name']}",
            f"- timerange: {payload['v13_4_34Plan']['scope']['timerange']}",
            "- candidatesToImplement:",
        ]
    )
    for item in payload["v13_4_34Plan"]["scope"]["candidatesToImplement"]:
        lines.append(f"  - {item}")
    lines.extend(["", "## Safety Boundary", ""])
    for key, value in payload["safetyBoundary"].items():
        lines.append(f"- {key}: {value}")
    if payload["warnings"]:
        lines.extend(["", "## Warnings", ""])
        for warning in payload["warnings"]:
            lines.append(f"- {warning}")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    report = build_report()
    _write_json(OUTPUT_JSON, report.to_dict())
    _write_text(OUTPUT_SUMMARY, render_summary(report))
    print(f"Wrote {OUTPUT_JSON}")
    print(f"Wrote {OUTPUT_SUMMARY}")
    print(f"currentStatus={report.currentStatus}")
    print(f"candidateCount={len(report.candidates)}")


if __name__ == "__main__":
    main()
