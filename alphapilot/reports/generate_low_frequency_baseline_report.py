"""Generate V13.4.32 low-frequency data and baseline reports.

This generator is report-only. It reads local public OHLCV files, writes data
quality and benchmark reports, and does not implement strategy logic, run a
Freqtrade backtest, enter Dry-run, use private exchange APIs, create orders, or
auto trade.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from alphapilot.low_frequency.baseline_builder import build_low_frequency_baselines
from alphapilot.low_frequency.low_frequency_data_checker import build_low_frequency_data_report
from alphapilot.low_frequency.low_frequency_data_schema import (
    DEFAULT_LOW_FREQUENCY_PAIRS,
    DEFAULT_LOW_FREQUENCY_TIMEFRAMES,
    LowFrequencyDataCheckConfig,
)
from alphapilot.reports.low_frequency_baseline_schema import LowFrequencyBaselineReport


REPORT_ID = "v13_4_32_low_frequency_baseline_report"
VERSION = "V13.4.32"
DATA_OUTPUT_JSON = Path("reports/v13_4_32_low_frequency_data_report.json")
BASELINE_OUTPUT_JSON = Path("reports/v13_4_32_low_frequency_baseline_report.json")
SUMMARY_OUTPUT_MD = Path("reports/v13_4_32_low_frequency_baseline_summary.md")
RESEARCH_PLAN_PATH = Path("reports/v13_4_31_low_frequency_research_plan.json")


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")


def _parse_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _comparison_rows(baselines: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in [baselines["noTrade"], *baselines["buyHold"], *baselines["equalWeight"]]:
        rows.append(
            {
                "baselineId": item.get("baselineId"),
                "name": item.get("name"),
                "pair": item.get("pair"),
                "timeframe": item.get("timeframe"),
                "status": item.get("status"),
                "totalReturnPct": item.get("totalReturnPct"),
                "maxDrawdownPct": item.get("maxDrawdownPct"),
                "volatilityPct": item.get("volatilityPct"),
                "bestDrawupPct": item.get("bestDrawupPct"),
                "tradeCount": item.get("tradeCount"),
                "syntheticHoldingCount": item.get("syntheticHoldingCount"),
                "exposureTimePct": item.get("exposureTimePct"),
            }
        )
    return rows


def _build_interpretation(status: str) -> list[str]:
    lines = [
        "NoTrade is the capital-preservation baseline and opportunity-cost anchor.",
        "BuyHold baselines describe passive exposure to BTC/ETH/SOL over the selected historical sample.",
        "EqualWeight baselines describe simple passive mainstream-coin basket exposure.",
        "Future low-frequency strategies must outperform relevant passive baselines after drawdown, exposure, and stability are considered.",
        "These baselines are historical research context only. They are not trading advice and not an execution command.",
    ]
    if status != "completed":
        lines.append("Some data quality checks did not pass; future strategy work should wait until the listed gaps are resolved.")
    return lines


def build_report(
    *,
    timerange: str,
    pairs: list[str],
    timeframes: list[str],
    data_path: str,
) -> tuple[dict[str, Any], LowFrequencyBaselineReport]:
    config = LowFrequencyDataCheckConfig(timerange=timerange, pairs=pairs, timeframes=timeframes, dataPath=data_path)
    data_report = build_low_frequency_data_report(config)
    data_payload = data_report.to_dict()
    baselines = build_low_frequency_baselines(timerange=timerange, pairs=pairs, timeframes=timeframes, data_path=data_path)
    comparison_table = _comparison_rows(baselines)

    unavailable_baselines = [row for row in comparison_table if row.get("status") == "unavailable"]
    status = "completed"
    warnings = list(data_payload.get("warnings") or []) + list(baselines.get("warnings") or [])
    if data_report.status == "insufficient_data" or unavailable_baselines:
        status = "insufficient_data"
        if unavailable_baselines:
            warnings.append(f"Unavailable baseline rows: {len(unavailable_baselines)}.")
    elif data_report.status == "warning":
        status = "completed_with_warnings"

    report = LowFrequencyBaselineReport(
        reportId=REPORT_ID,
        version=VERSION,
        status=status,
        timerange=timerange,
        pairs=pairs,
        timeframes=timeframes,
        dataReportPath=DATA_OUTPUT_JSON.as_posix(),
        researchPlanPath=RESEARCH_PLAN_PATH.as_posix(),
        dataQualitySummary=data_payload["summary"],
        baselines=baselines,
        comparisonTable=comparison_table,
        benchmarkRequirementsForFutureStrategy=[
            "Beat NoTrade on risk-adjusted opportunity cost, not only raw return.",
            "Compare against same-pair BuyHold for each tested direction and timeframe.",
            "Compare against EqualWeight BTC/ETH/SOL to avoid mistaking market beta for alpha.",
            "Report max drawdown, volatility, exposure time, and regime breakdown before any strategy approval.",
            "Do not approve Dry-run or live trading from V13.4.32 baseline reports.",
        ],
        interpretation=_build_interpretation(status),
        safetyBoundary={
            "strategyImplemented": False,
            "backtestExecuted": False,
            "freqtradeBacktestExecuted": False,
            "dryRunApproved": False,
            "liveTradingApproved": False,
            "tradeApiUsed": False,
            "withdrawApiUsed": False,
            "apiKeyStored": False,
            "accountRead": False,
            "positionRead": False,
            "orderCreated": False,
            "autoTradingUsed": False,
        },
        generatedAt=utc_now(),
        warnings=warnings,
    )
    return data_payload, report


def render_summary(report: LowFrequencyBaselineReport) -> str:
    payload = report.to_dict()
    lines = [
        "# AlphaPilot V13.4.32 Low-Frequency Data and Baseline Report",
        "",
        "V13.4.32 prepares BTC/ETH/SOL 4h/1d public OHLCV data and builds report-only NoTrade / BuyHold / EqualWeight baselines.",
        "",
        "## Status",
        "",
        f"- status: {payload['status']}",
        f"- timerange: {payload['timerange']}",
        f"- pairs: {', '.join(payload['pairs'])}",
        f"- timeframes: {', '.join(payload['timeframes'])}",
        f"- data report: {payload['dataReportPath']}",
        "",
        "## Data Quality Summary",
        "",
    ]
    for key, value in payload["dataQualitySummary"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Baseline Comparison", ""])
    lines.append("| Baseline | Pair | Timeframe | Status | Return % | Max DD % | Vol % | Exposure % |")
    lines.append("| --- | --- | --- | --- | ---: | ---: | ---: | ---: |")
    for row in payload["comparisonTable"]:
        lines.append(
            "| {name} | {pair} | {timeframe} | {status} | {ret} | {dd} | {vol} | {exposure} |".format(
                name=row.get("name") or "--",
                pair=row.get("pair") or "--",
                timeframe=row.get("timeframe") or "--",
                status=row.get("status") or "--",
                ret=row.get("totalReturnPct"),
                dd=row.get("maxDrawdownPct"),
                vol=row.get("volatilityPct"),
                exposure=row.get("exposureTimePct"),
            )
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
        ]
    )
    for item in payload["interpretation"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Future Strategy Benchmark Requirements", ""])
    for item in payload["benchmarkRequirementsForFutureStrategy"]:
        lines.append(f"- {item}")
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
    parser = argparse.ArgumentParser(description="Generate V13.4.32 low-frequency baseline reports.")
    parser.add_argument("--timerange", default="20240101-")
    parser.add_argument("--pairs", default=",".join(DEFAULT_LOW_FREQUENCY_PAIRS))
    parser.add_argument("--timeframes", default=",".join(DEFAULT_LOW_FREQUENCY_TIMEFRAMES))
    parser.add_argument("--data-path", default="user_data/data/okx/futures")
    args = parser.parse_args()

    pairs = _parse_csv(args.pairs)
    timeframes = _parse_csv(args.timeframes)
    data_payload, report = build_report(
        timerange=args.timerange,
        pairs=pairs,
        timeframes=timeframes,
        data_path=args.data_path,
    )
    _write_json(DATA_OUTPUT_JSON, data_payload)
    _write_json(BASELINE_OUTPUT_JSON, report.to_dict())
    _write_text(SUMMARY_OUTPUT_MD, render_summary(report))
    print(f"Wrote {DATA_OUTPUT_JSON}")
    print(f"Wrote {BASELINE_OUTPUT_JSON}")
    print(f"Wrote {SUMMARY_OUTPUT_MD}")
    print(f"status={report.status}")


if __name__ == "__main__":
    main()
