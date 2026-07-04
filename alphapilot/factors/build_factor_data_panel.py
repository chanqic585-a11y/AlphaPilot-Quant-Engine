"""CLI for V13.4.21 FactorDataPanel and Manual Factor Library implementation."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from alphapilot.factors.compute_manual_factors import compute_manual_factors, sanitize_records
from alphapilot.factors.factor_data_panel import build_factor_data_panel, panel_to_records
from alphapilot.factors.factor_schema import FactorDataPanelConfig, FactorDataPanelReport

REPORT_ID = "v13_4_21_factor_panel_report"
REPORT_VERSION = "V13.4.21"

DEFAULT_PANEL_SAMPLE = Path("reports/v13_4_21_factor_panel_sample.json")
DEFAULT_PANEL_REPORT = Path("reports/v13_4_21_factor_panel_report.json")
DEFAULT_PANEL_SUMMARY = Path("reports/v13_4_21_factor_panel_summary.md")
DEFAULT_MANUAL_FACTOR_REPORT = Path("reports/v13_4_21_manual_factor_library_report.json")


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _parse_pairs(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _top_missing_factors(coverage: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for factor_id, payload in coverage.items():
        rows.append(
            {
                "factorId": factor_id,
                "coveragePct": payload.get("coveragePct", 0),
                "missingCount": int(payload.get("rowCount", 0)) - int(payload.get("nonNullCount", 0)),
            }
        )
    return sorted(rows, key=lambda row: (row["coveragePct"], -row["missingCount"]))[:8]


def _no_lookahead_assurance() -> list[str]:
    return [
        "Panel returns use close values from current and prior bars only.",
        "Manual rolling factors use current and historical rows within each pair only.",
        "Cross-sectional ranks use pairs at the same timestamp only.",
        "Dynamic universe membership is read from historical snapshots by snapshot date when enabled.",
        "No forward labels, trade outcomes, backtest results, or future candles feed into factor values.",
    ]


def _build_report(
    config: FactorDataPanelConfig,
    panel_build: Any,
    factor_report: dict[str, Any],
    output_panel_sample: Path,
    output_report: Path,
    output_summary: Path,
    manual_factor_report: Path,
    sample_size: int,
) -> FactorDataPanelReport:
    panel = panel_build.panel
    coverage = factor_report.get("factorCoverage", {})
    warnings = list(panel_build.warnings) + list(factor_report.get("warnings", []))
    status = "success" if not panel.empty else "blocked_no_readable_ohlcv"
    return FactorDataPanelReport(
        reportId=REPORT_ID,
        version=REPORT_VERSION,
        status=status,
        config=config,
        rowsGenerated=int(len(panel)),
        sampleRowsWritten=int(min(sample_size, len(panel))),
        timeframe=config.timeframe,
        timerange=config.timerange,
        loadedPairs=panel_build.loadReport.loadedPairs,
        failedPairs=panel_build.loadReport.failedPairs,
        missingTimeframes=sorted(set(panel_build.loadReport.missingTimeframes)),
        formatUsed=panel_build.loadReport.formatUsed,
        factorColumnsGenerated=factor_report.get("computedFactors", []),
        factorCoverage=coverage,
        topMissingFactors=_top_missing_factors(coverage),
        quoteVolumeEstimatedCount=int(panel["quoteVolumeEstimated"].sum()) if "quoteVolumeEstimated" in panel else 0,
        vwapEstimatedCount=int(panel["vwapEstimated"].sum()) if "vwapEstimated" in panel else 0,
        universeMembershipAvailable=panel_build.universeMembershipAvailable,
        universeMembershipSource=panel_build.universeMembershipSource,
        dynamicUniverseSnapshotsUsed=panel_build.dynamicUniverseSnapshotsUsed,
        warnings=warnings,
        noLookaheadAssurance=_no_lookahead_assurance(),
        dryRunApproved=False,
        liveTradingApproved=False,
        outputPanelSamplePath=str(output_panel_sample),
        outputReportPath=str(output_report),
        outputSummaryPath=str(output_summary),
        manualFactorLibraryReportPath=str(manual_factor_report),
        nextStepRecommendation="V13.4.22 - evaluate factor coverage and decide whether to build forward-label factor research.",
        generatedAt=utc_now(),
    )


def _write_summary(report: dict[str, Any], manual_factor_report: dict[str, Any], path: Path) -> None:
    lines = [
        "# AlphaPilot V13.4.21 FactorDataPanel Summary",
        "",
        "Status: research-only local data generation.",
        "",
        "V13.4.21 reads local public OHLCV files and computes point-in-time manual factors. It does not run a strategy backtest, enter Dry-run, call exchange private APIs, read accounts, create orders, or auto trade.",
        "",
        "## Build Status",
        "",
        f"- status: {report['status']}",
        f"- timerange: {report['timerange']}",
        f"- timeframe: {report['timeframe']}",
        f"- rowsGenerated: {report['rowsGenerated']}",
        f"- sampleRowsWritten: {report['sampleRowsWritten']}",
        f"- loadedPairs: {len(report['loadedPairs'])}",
        f"- failedPairs: {len(report['failedPairs'])}",
        f"- dynamicUniverseSnapshotsUsed: {report['dynamicUniverseSnapshotsUsed']}",
        f"- universeMembershipSource: {report['universeMembershipSource']}",
        "",
        "## Estimated Fields",
        "",
        f"- quoteVolumeEstimatedCount: {report['quoteVolumeEstimatedCount']}",
        f"- vwapEstimatedCount: {report['vwapEstimatedCount']}",
        "- quoteVolume uses close * volume because Freqtrade OHLCV does not carry exchange quote volume in this local file set.",
        "- vwap uses typical price fallback `(high + low + close) / 3` and is explicitly marked estimated.",
        "",
        "## Manual Factor Library",
        "",
        f"- factorCount: {manual_factor_report.get('factorCount', 0)}",
        f"- computedFactors: {', '.join(manual_factor_report.get('computedFactors', []))}",
        f"- averageCoveragePct: {manual_factor_report.get('averageCoveragePct', 0)}",
        "",
        "## Lowest Coverage Factors",
        "",
    ]
    top_missing = report.get("topMissingFactors", [])
    if top_missing:
        for row in top_missing:
            lines.append(f"- {row['factorId']}: coverage={row['coveragePct']}%, missing={row['missingCount']}")
    else:
        lines.append("- none")

    lines.extend(["", "## No-Lookahead Assurance", ""])
    lines.extend(f"- {item}" for item in report["noLookaheadAssurance"])

    lines.extend(["", "## Output Files", ""])
    lines.extend(
        [
            f"- panel sample: {report['outputPanelSamplePath']}",
            f"- panel report: {report['outputReportPath']}",
            f"- manual factor report: {report['manualFactorLibraryReportPath']}",
            "",
            "## Warnings",
            "",
        ]
    )
    if report["warnings"]:
        lines.extend(f"- {warning}" for warning in report["warnings"])
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Safety Boundary",
            "",
            f"- dryRunApproved: {report['dryRunApproved']}",
            f"- liveTradingApproved: {report['liveTradingApproved']}",
            "- no API key",
            "- no Trade API",
            "- no Withdraw API",
            "- no account or position reads",
            "- no real orders",
            "- no auto trading",
            "",
            f"Next step: {report['nextStepRecommendation']}",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def build_outputs(
    config: FactorDataPanelConfig,
    output_panel_sample: Path,
    output_report: Path,
    output_summary: Path,
    manual_factor_report: Path,
) -> FactorDataPanelReport:
    panel_build = build_factor_data_panel(config)
    factor_result = compute_manual_factors(panel_build.panel)

    sample_size = max(1, config.sampleSize)
    sample_records = sanitize_records(factor_result.panel.head(sample_size).to_dict(orient="records"))
    if not sample_records and not panel_build.panel.empty:
        sample_records = panel_to_records(panel_build.panel.head(sample_size))
    _write_json(output_panel_sample, sample_records)
    _write_json(manual_factor_report, factor_result.report)

    report = _build_report(
        config,
        panel_build,
        factor_result.report,
        output_panel_sample,
        output_report,
        output_summary,
        manual_factor_report,
        sample_size,
    )
    report_payload = report.to_dict()
    _write_json(output_report, report_payload)
    _write_summary(report_payload, factor_result.report, output_summary)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Build V13.4.21 FactorDataPanel from local OHLCV.")
    parser.add_argument("--timerange", default="20260101-")
    parser.add_argument("--timeframe", default="1h")
    parser.add_argument("--pairs", default="")
    parser.add_argument("--use-dynamic-universe", action="store_true")
    parser.add_argument("--universe-snapshots", default="reports/v13_4_13_dynamic_universe_snapshots.json")
    parser.add_argument("--data-path", default="user_data/data/okx/futures")
    parser.add_argument("--sample-size", type=int, default=200)
    parser.add_argument("--output-panel-sample", type=Path, default=DEFAULT_PANEL_SAMPLE)
    parser.add_argument("--output-report", type=Path, default=DEFAULT_PANEL_REPORT)
    parser.add_argument("--output-summary", type=Path, default=DEFAULT_PANEL_SUMMARY)
    parser.add_argument("--output-manual-factor-report", type=Path, default=DEFAULT_MANUAL_FACTOR_REPORT)
    args = parser.parse_args()

    config = FactorDataPanelConfig(
        timerange=args.timerange,
        timeframe=args.timeframe,
        pairs=_parse_pairs(args.pairs),
        dataPath=args.data_path,
        useDynamicUniverse=bool(args.use_dynamic_universe),
        universeSnapshotsPath=args.universe_snapshots,
        sampleSize=args.sample_size,
    )
    report = build_outputs(
        config=config,
        output_panel_sample=args.output_panel_sample,
        output_report=args.output_report,
        output_summary=args.output_summary,
        manual_factor_report=args.output_manual_factor_report,
    )
    print(f"Factor panel status: {report.status}")
    print(f"Rows generated: {report.rowsGenerated}")
    print(f"Loaded pairs: {len(report.loadedPairs)}")
    print(f"Panel sample: {args.output_panel_sample}")
    print(f"Panel report: {args.output_report}")
    print(f"Summary: {args.output_summary}")
    print(f"Manual factor report: {args.output_manual_factor_report}")
    if report.status != "success":
        raise SystemExit("FactorDataPanel build blocked. Do not tag V13.4.21 until local OHLCV data is readable.")


if __name__ == "__main__":
    main()
