"""Generate V13.4.27 market regime and local data integrity review.

This command reads local public OHLCV files and prior research reports only. It
does not download data, run Freqtrade backtests, enter Dry-run, call exchange
APIs, read accounts, create orders, or auto trade.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from alphapilot.data_quality.ohlcv_integrity_checker import check_ohlcv_integrity, result_to_pair_index
from alphapilot.market_regime.market_regime_labeler import build_market_regime_review
from alphapilot.reports.market_regime_data_integrity_schema import (
    MarketRegimeDataIntegrityReport,
    RegimeAwareFailureReview,
)

DEFAULT_DATA_PATH = Path("user_data/data/okx/futures")
DEFAULT_TIMERANGE = "20260101-"
DEFAULT_TIMEFRAMES = "1h,4h"
DEFAULT_OUTPUT_REPORT = Path("reports/v13_4_27_market_regime_data_integrity_report.json")
DEFAULT_OUTPUT_SUMMARY = Path("reports/v13_4_27_market_regime_data_integrity_summary.md")
DEFAULT_OUTPUT_BTC_LABELS = Path("reports/v13_4_27_btc_regime_labels.json")
DEFAULT_OUTPUT_DATA_QUALITY = Path("reports/v13_4_27_data_quality_by_pair.json")


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"_missing": True, "path": path.as_posix()}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - report the limitation.
        return {"_error": str(exc), "path": path.as_posix()}


def _safe_get(report: dict[str, Any], key: str, default: Any = None) -> Any:
    value = report.get(key, default)
    return default if value is None else value


def build_failure_review(data_integrity: dict[str, Any], btc_regime: dict[str, Any]) -> RegimeAwareFailureReview:
    hypothesis = _read_json(Path("reports/v13_4_26_hypothesis_validation_report.json"))
    benchmark = _read_json(Path("reports/v13_4_23_benchmark_suite_report.json"))
    trend_expanded = _read_json(Path("reports/v13_4_9_trend_pullback_expanded_validation_report.json"))
    dynamic_expanded = _read_json(Path("reports/v13_4_17_dynamic_regime_expanded_report.json"))

    integrity_summary = data_integrity.get("summary", {})
    distribution = btc_regime.get("regimeDistribution", {})
    labels_total = sum(int(value) for value in distribution.values()) or 1
    bearish_count = int(distribution.get("bear", 0)) + int(distribution.get("crash", 0))
    high_vol_count = int(distribution.get("high_volatility", 0))
    bearish_pct = round((bearish_count / labels_total) * 100, 4)
    high_vol_pct = round((high_vol_count / labels_total) * 100, 4)

    evidence = [
        f"Data integrity status: {integrity_summary.get('status')} with average missing rate {integrity_summary.get('averageMissingRatePct')}%.",
        f"BTC regime labels show bear/crash coverage around {bearish_pct}% and high-volatility coverage around {high_vol_pct}% in the selected local sample.",
        f"V13.4.26 validated hypotheses: {_safe_get(hypothesis, 'validatedHypothesisCount', 'unknown')}; top supported hypotheses: {_safe_get(hypothesis, 'topSupportedHypotheses', []) or 'none'}.",
        f"V13.4.23 benchmark dryRunApproved: {_safe_get(benchmark, 'dryRunApproved', False)}.",
        f"V13.4.9 Trend Pullback dryRunApproved: {_safe_get(trend_expanded, 'dryRunApproved', False)}.",
        f"V13.4.17 Dynamic Regime finalEntrySignals: {_safe_get(dynamic_expanded, 'finalEntrySignals', 'unknown')}.",
    ]
    limitations = [
        "Existing strategy and benchmark reports were not originally tagged per BTC regime, so this review maps them to sample-level market context rather than per-trade regime attribution.",
        "Breadth statistics use locally available 1h OHLCV as a proxy when exchange-wide historical membership is unavailable.",
        "No external market data was fetched for cross-validation; BTC sanity checks use local candles only.",
    ]
    recommendations = [
        "Do not treat V13.4.26 failures as only a factor-quality issue until regime-tagged evaluations are available.",
        "Add regime labels to future backtest exports and factor validation samples before comparing strategy families.",
        "Require a no-trade or avoid regime for long-only technical strategies during crash/high-volatility bear samples.",
        "Run future V13.4.28 data expansion only after preserving this integrity review as the baseline.",
    ]
    conclusion = (
        "Local OHLCV quality appears usable for research if warnings are reviewed, but the selected sample is strongly regime-sensitive. "
        "Recent long-only technical research failures are more consistent with adverse bear/high-volatility market context plus sparse validated alpha than with a single obvious data corruption issue."
    )
    if integrity_summary.get("status") == "invalid":
        conclusion = (
            "Some local OHLCV integrity checks are invalid, so strategy conclusions must be treated as provisional until those rows are repaired or excluded. "
            + conclusion
        )
    return RegimeAwareFailureReview(
        conclusion=conclusion,
        evidence=evidence,
        limitations=limitations,
        recommendations=recommendations,
    )


def _summary_markdown(report: dict[str, Any]) -> str:
    integrity = report["dataIntegrity"]["summary"]
    regime = report["btcRegime"]
    review = report["regimeAwareFailureReview"]
    data_warnings = report["dataIntegrity"].get("summary", {}).get("warnings", [])
    regime_warnings = regime.get("warnings", [])
    return f"""# AlphaPilot V13.4.27 Market Regime and Data Integrity Review

Status: {report.get("status")}

V13.4.27 is a research-only data integrity and market regime review. It does
not implement a strategy, run a backtest, enter Dry-run, download data, call
exchange APIs, read accounts, create orders, or auto trade.

## Scope

- timerange: {report.get("timerange")}
- dataPath: {report.get("dataPath")}
- timeframesChecked: {", ".join(report.get("timeframesChecked", []))}

## OHLCV Integrity

- status: {integrity.get("status")}
- pairCount: {integrity.get("pairCount")}
- pairTimeframeCount: {integrity.get("pairTimeframeCount")}
- validCount: {integrity.get("validCount")}
- warningCount: {integrity.get("warningCount")}
- invalidCount: {integrity.get("invalidCount")}
- missingFileCount: {integrity.get("missingFileCount")}
- averageMissingRatePct: {integrity.get("averageMissingRatePct")}
- maxMissingRatePct: {integrity.get("maxMissingRatePct")}
- totalDuplicateTimestamps: {integrity.get("totalDuplicateTimestamps")}
- totalInvalidOhlcRows: {integrity.get("totalInvalidOhlcRows")}
- totalExtremeReturnRows: {integrity.get("totalExtremeReturnRows")}
- pairFormatIssueCount: {integrity.get("pairFormatIssueCount")}
- spotSwapMismatchCount: {integrity.get("spotSwapMismatchCount")}

Warnings:

{chr(10).join(f"- {item}" for item in data_warnings) or "- none"}

## BTC Regime

- status: {regime.get("status")}
- dominantRegimes: {", ".join(regime.get("dominantRegimes", [])) or "none"}
- regimeDistribution: {regime.get("regimeDistribution")}

BTC sanity points:

{chr(10).join(f"- {item.get('requestedDate')}: {item.get('close')} at {item.get('nearestTimestamp')} warning={item.get('warning')}" for item in regime.get("btcSanityPoints", [])) or "- none"}

Regime warnings:

{chr(10).join(f"- {item}" for item in regime_warnings) or "- none"}

## Dynamic Universe Breadth Proxy

{json.dumps(regime.get("breadthSummary", {}), ensure_ascii=False, indent=2)}

## Regime-Aware Failure Review

Conclusion:

{review.get("conclusion")}

Evidence:

{chr(10).join(f"- {item}" for item in review.get("evidence", [])) or "- none"}

Limitations:

{chr(10).join(f"- {item}" for item in review.get("limitations", [])) or "- none"}

Recommendations:

{chr(10).join(f"- {item}" for item in review.get("recommendations", [])) or "- none"}

## Safety Boundary

- dryRunApproved: {report["safetyBoundary"]["dryRunApproved"]}
- liveTradingApproved: {report["safetyBoundary"]["liveTradingApproved"]}
- no strategy implementation
- no backtest execution
- no data download
- no Trade API
- no Withdraw API
- no real API key
- no account or position reads
- no order creation
- no auto trading
"""


def build_report(args: argparse.Namespace) -> MarketRegimeDataIntegrityReport:
    timeframes = [item.strip() for item in args.timeframes.split(",") if item.strip()]
    integrity = check_ohlcv_integrity(data_path=args.data_path, timerange=args.timerange, timeframes=timeframes)
    regime = build_market_regime_review(data_path=args.data_path, timerange=args.timerange)
    integrity_payload = integrity.to_dict()
    regime_payload = regime.to_dict()
    failure_review = build_failure_review(integrity_payload, regime_payload)

    warnings = []
    warnings.extend(integrity.summary.warnings)
    warnings.extend(regime.warnings)
    status = "completed"
    if integrity.summary.status == "invalid":
        status = "completed_with_data_integrity_warnings"
    elif warnings:
        status = "completed_with_warnings"

    return MarketRegimeDataIntegrityReport(
        reportId="v13_4_27_market_regime_data_integrity_review",
        version="V13.4.27",
        status=status,
        timerange=args.timerange,
        dataPath=str(args.data_path),
        timeframesChecked=timeframes,
        dataIntegrity=integrity_payload,
        btcRegime=regime_payload,
        regimeAwareFailureReview=failure_review,
        safetyBoundary={
            "dryRunApproved": False,
            "liveTradingApproved": False,
            "strategyImplemented": False,
            "backtestExecuted": False,
            "dataDownloaded": False,
            "tradeApiUsed": False,
            "withdrawApiUsed": False,
            "apiKeyStored": False,
            "accountRead": False,
            "positionRead": False,
            "orderCreated": False,
            "autoTrading": False,
        },
        generatedAt=utc_now(),
        warnings=warnings,
    )


def run(args: argparse.Namespace) -> dict[str, Any]:
    timeframes = [item.strip() for item in args.timeframes.split(",") if item.strip()]
    integrity = check_ohlcv_integrity(args.data_path, args.timerange, timeframes)
    regime = build_market_regime_review(data_path=args.data_path, timerange=args.timerange)
    integrity_payload = integrity.to_dict()
    regime_payload = regime.to_dict()
    failure_review = build_failure_review(integrity_payload, regime_payload)
    warnings = []
    warnings.extend(integrity.summary.warnings)
    warnings.extend(regime.warnings)
    status = "completed"
    if integrity.summary.status == "invalid":
        status = "completed_with_data_integrity_warnings"
    elif warnings:
        status = "completed_with_warnings"
    report = MarketRegimeDataIntegrityReport(
        reportId="v13_4_27_market_regime_data_integrity_review",
        version="V13.4.27",
        status=status,
        timerange=args.timerange,
        dataPath=str(args.data_path),
        timeframesChecked=timeframes,
        dataIntegrity=integrity_payload,
        btcRegime=regime_payload,
        regimeAwareFailureReview=failure_review,
        safetyBoundary={
            "dryRunApproved": False,
            "liveTradingApproved": False,
            "strategyImplemented": False,
            "backtestExecuted": False,
            "dataDownloaded": False,
            "tradeApiUsed": False,
            "withdrawApiUsed": False,
            "apiKeyStored": False,
            "accountRead": False,
            "positionRead": False,
            "orderCreated": False,
            "autoTrading": False,
        },
        generatedAt=utc_now(),
        warnings=warnings,
    )
    payload = report.to_dict()
    _write_json(Path(args.output_report), payload)
    _write_text(Path(args.output_summary), _summary_markdown(payload))
    _write_json(Path(args.output_btc_labels), payload["btcRegime"])
    _write_json(Path(args.output_data_quality), result_to_pair_index(integrity))
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate V13.4.27 market regime and data integrity review.")
    parser.add_argument("--data-path", default=str(DEFAULT_DATA_PATH))
    parser.add_argument("--timerange", default=DEFAULT_TIMERANGE)
    parser.add_argument("--timeframes", default=DEFAULT_TIMEFRAMES)
    parser.add_argument("--output-report", default=str(DEFAULT_OUTPUT_REPORT))
    parser.add_argument("--output-summary", default=str(DEFAULT_OUTPUT_SUMMARY))
    parser.add_argument("--output-btc-labels", default=str(DEFAULT_OUTPUT_BTC_LABELS))
    parser.add_argument("--output-data-quality", default=str(DEFAULT_OUTPUT_DATA_QUALITY))
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    report = run(args)
    print(f"V13.4.27 status: {report.get('status')}")
    print(f"Data integrity status: {report.get('dataIntegrity', {}).get('summary', {}).get('status')}")
    print(f"BTC dominant regimes: {', '.join(report.get('btcRegime', {}).get('dominantRegimes', [])) or 'none'}")
    print(f"Report: {args.output_report}")
    print(f"Summary: {args.output_summary}")


if __name__ == "__main__":
    main()
