"""Report writer for V13.4.22 factor evaluation outputs."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [json_safe(item) for item in value]
    if isinstance(value, bool) or value is None or isinstance(value, str) or isinstance(value, int):
        return value
    if isinstance(value, float):
        return None if math.isnan(value) or math.isinf(value) else value
    try:
        if value != value:
            return None
    except Exception:  # noqa: BLE001 - defensive JSON sanitization.
        pass
    return value


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(json_safe(payload), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _format_factor_rows(rows: list[dict[str, Any]], metric: str) -> list[str]:
    if not rows:
        return ["- none"]
    return [f"- {row['factorId']}: {metric}={row.get(metric)}" for row in rows]


def build_summary_markdown(report: dict[str, Any]) -> str:
    candidate_factors = report.get("candidateFactors", [])
    warnings = report.get("warnings", [])
    lines = [
        "# AlphaPilot V13.4.22 Factor Evaluation Summary",
        "",
        "This report evaluates point-in-time manual factors against forward labels. It is research-only and does not create a trading strategy, run a Freqtrade backtest, enter Dry-run, use API keys, read accounts, create orders, or auto trade.",
        "",
        "## Evaluation Status",
        "",
        f"- status: {report.get('status')}",
        f"- factorCount: {report.get('factorCount')}",
        f"- evaluatedFactorCount: {report.get('evaluatedFactorCount')}",
        f"- sampleCount: {report.get('sampleCount')}",
        f"- validLabelCount: {report.get('validLabelCount')}",
        f"- horizons: {', '.join(str(item) for item in report.get('horizons', []))}",
        f"- primaryHorizon: {report.get('primaryHorizon')}",
        f"- quantiles: {report.get('quantiles')}",
        f"- TP / SL labels: +{report.get('tpPct')} / -{report.get('slPct')}",
        "",
        "## Top Factors By RankIC",
        "",
    ]
    lines.extend(_format_factor_rows(report.get("topFactorsByRankIC", []), "meanRankIC"))
    lines.extend(["", "## Top Factors By Q5-Q1 Spread", ""])
    lines.extend(_format_factor_rows(report.get("topFactorsBySpread", []), "topBottomSpread"))
    lines.extend(["", "## Top Factors By Profit Factor", ""])
    lines.extend(_format_factor_rows(report.get("topFactorsByProfitFactor", []), "profitFactor"))
    lines.extend(["", "## Candidate Factors", ""])
    if candidate_factors:
        for candidate in candidate_factors:
            lines.append(
                f"- {candidate['factorId']}: RankIC={candidate.get('meanRankIC')}, spread={candidate.get('topBottomSpread')}, PF={candidate.get('profitFactor')}, status=research_only / not_trade_ready / not_dry_run_ready"
            )
    else:
        lines.append("- none")
    lines.extend(["", "## Low Coverage Factors", ""])
    low_coverage = report.get("lowCoverageFactors", [])
    if low_coverage:
        for row in low_coverage:
            lines.append(f"- {row['factorId']}: coveragePct={row.get('coveragePct')}")
    else:
        lines.append("- none")
    lines.extend(["", "## Unstable Factors", ""])
    unstable = report.get("unstableFactors", [])[:10]
    if unstable:
        for row in unstable:
            lines.append(
                f"- {row['factorId']}: months={row.get('stableAcrossMonths')}, pairs={row.get('stableAcrossPairs')}, regimes={row.get('stableAcrossRegimes')}"
            )
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## No-Lookahead Boundary",
            "",
            "- Features are point-in-time and use only current or historical rows.",
            "- Forward labels use future candles only as evaluation targets.",
            "- Forward labels do not alter factor values, sample selection, or universe membership.",
            "- Candidate factors are research artifacts, not signals or orders.",
            "",
            "## Warnings",
            "",
        ]
    )
    if warnings:
        lines.extend(f"- {warning}" for warning in warnings)
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Safety Boundary",
            "",
            f"- dryRunApproved: {report.get('dryRunApproved')}",
            f"- liveTradingApproved: {report.get('liveTradingApproved')}",
            "- no strategy implementation",
            "- no backtest execution",
            "- no Trade API / Withdraw API",
            "- no real API key",
            "- no account or position reads",
            "- no real orders",
            "- no auto trading",
            "",
            f"Next step: {report.get('nextStepRecommendation')}",
            "",
        ]
    )
    return "\n".join(lines)


def write_summary(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_summary_markdown(report), encoding="utf-8")


def build_candidates_payload(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "reportId": "v13_4_22_factor_candidates",
        "version": "V13.4.22",
        "sourceReportId": report.get("reportId"),
        "candidateFactors": report.get("candidateFactors", []),
        "candidateCount": len(report.get("candidateFactors", [])),
        "status": "research_only",
        "notTradeReady": True,
        "notDryRunReady": True,
        "dryRunApproved": False,
        "liveTradingApproved": False,
        "warnings": [
            "Candidate factors are statistical research artifacts only.",
            "Do not convert candidate factors directly into entries, orders, Dry-run, or live trading.",
        ],
        "generatedAt": report.get("generatedAt"),
    }


def write_factor_evaluation_outputs(report: dict[str, Any], output_report: Path, output_summary: Path, output_candidates: Path) -> None:
    write_json(output_report, report)
    write_summary(output_summary, report)
    write_json(output_candidates, build_candidates_payload(report))
