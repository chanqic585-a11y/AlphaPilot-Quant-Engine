"""Generate V13.4.31 low-frequency mainstream coin research plan.

The generator reads local research reports and writes a research plan only. It
does not write strategy code, download data, run Freqtrade, enter Dry-run,
call exchange APIs, read accounts, create orders, or auto trade.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from alphapilot.reports.low_frequency_research_plan_schema import LowFrequencyResearchPlanReport
from alphapilot.research_factory.low_frequency_research_plan import build_low_frequency_research_plan

REPORT_ID = "v13_4_31_low_frequency_research_plan"
SOURCE_REPORTS = [
    Path("reports/v13_4_30_short_rejection_failure_review.json"),
    Path("reports/v13_4_30_negative_research_rules.json"),
    Path("reports/v13_4_27_market_regime_data_integrity_report.json"),
]
OPTIONAL_REPORTS = [
    Path("reports/v13_4_23_benchmark_suite_report.json"),
    Path("reports/v13_4_24_benchmark_result_review.json"),
    Path("reports/v13_4_22_factor_evaluation_report.json"),
    Path("reports/v13_4_28_market_data_expansion_report.json"),
]
OUTPUT_JSON = Path("reports/v13_4_31_low_frequency_research_plan.json")
OUTPUT_SUMMARY = Path("reports/v13_4_31_low_frequency_research_summary.md")


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


def _summarize_report(path: Path, required: bool, warnings: list[str]) -> dict[str, Any]:
    if not path.exists():
        message = f"{'Required' if required else 'Optional'} input report missing: {path.as_posix()}"
        if required:
            raise FileNotFoundError(message)
        warnings.append(message)
        return {"path": path.as_posix(), "available": False}
    data = _read_json(path)
    summary: dict[str, Any] = {
        "path": path.as_posix(),
        "available": True,
        "reportId": data.get("reportId"),
        "status": data.get("status") or data.get("currentStatus"),
        "generatedAt": data.get("generatedAt"),
    }
    for key in [
        "currentStatus",
        "researchWorthContinuing",
        "nextStepRecommendation",
        "dryRunApproved",
        "liveTradingApproved",
        "warnings",
    ]:
        if key in data:
            summary[key] = data[key]
    data_integrity = data.get("dataIntegrity")
    if isinstance(data_integrity, dict):
        integrity_summary = data_integrity.get("summary")
        summary["dataIntegrity"] = integrity_summary if isinstance(integrity_summary, dict) else {"available": True}
    btc_regime = data.get("btcRegime")
    if isinstance(btc_regime, dict):
        summary["btcRegime"] = {
            "status": btc_regime.get("status"),
            "timerange": btc_regime.get("timerange"),
            "btcPair": btc_regime.get("btcPair"),
            "regimeDistribution": btc_regime.get("regimeDistribution"),
            "dominantRegimes": btc_regime.get("dominantRegimes"),
            "breadthSummary": btc_regime.get("breadthSummary"),
            "warnings": btc_regime.get("warnings"),
            "labelCount": len(btc_regime.get("labels") or []),
        }
    return summary


def build_report() -> LowFrequencyResearchPlanReport:
    warnings: list[str] = []
    input_summaries: dict[str, Any] = {}
    for report in SOURCE_REPORTS:
        input_summaries[report.as_posix()] = _summarize_report(report, True, warnings)
    for report in OPTIONAL_REPORTS:
        input_summaries[report.as_posix()] = _summarize_report(report, False, warnings)

    plan = build_low_frequency_research_plan()
    plan_payload = plan.to_dict()
    return LowFrequencyResearchPlanReport(
        reportId=REPORT_ID,
        currentStatus=plan.currentStatus,
        sourceReports=[path.as_posix() for path in SOURCE_REPORTS],
        inputReportSummaries=input_summaries,
        scope=plan_payload["scope"],
        hypotheses=plan_payload["hypotheses"],
        longShortFramework=plan.longShortFramework,
        minimalConditionsPhilosophy=plan.minimalConditionsPhilosophy,
        benchmarkRequirements=plan.benchmarkRequirements,
        evaluationMetrics=plan.evaluationMetrics,
        dataRequirements=plan.dataRequirements,
        optionalFutureData=plan.optionalFutureData,
        nextStepRecommendation=plan.nextStepRecommendation,
        dryRunApproved=False,
        liveTradingApproved=False,
        generatedAt=utc_now(),
        warnings=warnings,
        notes=plan.notes
        + [
            "V13.4.31 is research-plan-only.",
            "No strategy code, data download, backtest, Dry-run, live trading, Trade API, Withdraw API, account read, position read, order creation, or auto trading was used.",
        ],
    )


def render_summary(report: LowFrequencyResearchPlanReport) -> str:
    payload = report.to_dict()
    scope = payload["scope"]
    hypotheses = payload["hypotheses"]
    framework = payload["longShortFramework"]
    minimal = payload["minimalConditionsPhilosophy"]
    lines = [
        "# AlphaPilot V13.4.31 Low-Frequency Mainstream Coin Research Plan",
        "",
        "V13.4.31 narrows the next research track to BTC/ETH/SOL on 4h/1d timeframes. It is a research plan only: no strategy code, no new data download, no backtest, no Dry-run, and no live trading approval.",
        "",
        "## Status",
        "",
        f"- currentStatus: {payload['currentStatus']}",
        f"- dryRunApproved: {payload['dryRunApproved']}",
        f"- liveTradingApproved: {payload['liveTradingApproved']}",
        f"- nextStepRecommendation: {payload['nextStepRecommendation']}",
        "",
        "## Scope",
        "",
        f"- pairs: {', '.join(scope['pairs'])}",
        f"- primaryTimeframes: {', '.join(scope['primaryTimeframes'])}",
        f"- optionalTimeframes: {', '.join(scope['optionalTimeframes'])}",
        "- excludedFromMainline:",
    ]
    for item in scope["excludedFromMainline"]:
        lines.append(f"  - {item}")
    lines.extend([
        "",
        "## Hypotheses",
        "",
    ])
    for item in hypotheses:
        lines.extend(
            [
                f"### {item['hypothesisId']} - {item['name']}",
                "",
                f"- thesis: {item['thesis']}",
                f"- direction: {item['direction']}",
                f"- primaryTimeframe: {item['primaryTimeframe']}",
                f"- regimeUse: {item['regimeUse']}",
                "- coreConditions:",
            ]
        )
        for condition in item["coreConditions"]:
            lines.append(f"  - {condition}")
        lines.append("- validationFocus:")
        for focus in item["validationFocus"]:
            lines.append(f"  - {focus}")
        lines.append("")
    lines.extend([
        "## Long / Short Framework",
        "",
        f"- scoreNames: {', '.join(framework['scoreNames'])}",
        f"- regimeRole: {framework['regimeRole']}",
        f"- longCandidate: {framework['interpretation']['longCandidate']}",
        f"- shortCandidate: {framework['interpretation']['shortCandidate']}",
        f"- noTrade: {framework['interpretation']['noTrade']}",
        "",
        "## Minimal Conditions Philosophy",
        "",
        f"- maxCoreConditionsPerDirection: {minimal['maxCoreConditionsPerDirection']}",
        "- avoid:",
    ])
    for item in minimal["avoid"]:
        lines.append(f"  - {item}")
    lines.extend([
        "",
        "## Benchmark Requirements",
        "",
    ])
    for item in payload["benchmarkRequirements"]:
        lines.append(f"- {item}")
    lines.extend([
        "",
        "## Evaluation Metrics",
        "",
    ])
    for item in payload["evaluationMetrics"]:
        lines.append(f"- {item}")
    lines.extend([
        "",
        "## Data Requirements",
        "",
    ])
    for item in payload["dataRequirements"]:
        lines.append(f"- {item}")
    lines.extend([
        "",
        "Optional future data:",
        "",
    ])
    for item in payload["optionalFutureData"]:
        lines.append(f"- {item}")
    lines.extend([
        "",
        "## Safety Boundary",
        "",
        "- no strategy code",
        "- no data download",
        "- no backtest",
        "- no Dry-run",
        "- no real API key",
        "- no Trade API / Withdraw API",
        "- no account or position reads",
        "- no real orders",
        "- no auto trading",
        "",
    ])
    if payload["warnings"]:
        lines.append("Warnings:")
        lines.append("")
        for warning in payload["warnings"]:
            lines.append(f"- {warning}")
        lines.append("")
    return "\n".join(lines)


def generate() -> dict[str, Any]:
    report = build_report()
    payload = report.to_dict()
    _write_json(OUTPUT_JSON, payload)
    _write_text(OUTPUT_SUMMARY, render_summary(report))
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate V13.4.31 low-frequency mainstream research plan.")
    parser.parse_args()
    payload = generate()
    print(f"V13.4.31 status: {payload['currentStatus']}")
    print(f"pairs: {', '.join(payload['scope']['pairs'])}")
    print(f"primaryTimeframes: {', '.join(payload['scope']['primaryTimeframes'])}")
    print(f"hypotheses: {len(payload['hypotheses'])}")
    print(f"dryRunApproved: {payload['dryRunApproved']}")
    print(f"liveTradingApproved: {payload['liveTradingApproved']}")
    print(f"Report: {OUTPUT_JSON}")
    print(f"Summary: {OUTPUT_SUMMARY}")


if __name__ == "__main__":
    main()
