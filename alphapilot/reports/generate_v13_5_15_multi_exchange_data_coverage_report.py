"""Generate V13.5.15 multi-exchange historical data coverage report.

This report audits local public OHLCV files across exchanges before strategy
logic is changed. It does not download data, build signals, run Dry-run, create
orders, or connect to private exchange endpoints.
"""

from __future__ import annotations

import argparse
import math
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean
from typing import Any

import pandas as pd

from alphapilot.reports.generate_v13_5_derivatives_ml_strategy_report import _json_ready, write_json, write_text
from alphapilot.universe.top100_usdt_swap_research import get_top100_usdt_swap_research_pairs


VERSION = "V13.5.15"
REPORT_ID = "v13_5_15_multi_exchange_data_coverage_report"
DEFAULT_DATA_ROOT = Path("user_data/data")
DEFAULT_OUTPUT_REPORT = Path("reports/v13_5_15_multi_exchange_data_coverage_report.json")
DEFAULT_OUTPUT_SUMMARY = Path("reports/v13_5_15_multi_exchange_data_coverage_summary.md")
DEFAULT_EXCHANGES = ["okx", "binance", "bybit"]
DEFAULT_TIMEFRAMES = ["4h", "1d"]
DEFAULT_CORE_PAIRS = ["BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT"]
TARGET_START = pd.Timestamp("2020-01-01T00:00:00Z")
TARGET_LATEST_YEAR = 2026


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _round(value: Any, digits: int = 6) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return round(number, digits)


def _parse_csv(value: str | None, default: list[str]) -> list[str]:
    if not value:
        return default.copy()
    return [item.strip() for item in value.split(",") if item.strip()]


def _normalize_pair(pair: str) -> str:
    return pair.replace("/", "_").replace(":", "_")


def _expected_file(data_root: Path, exchange: str, pair: str, timeframe: str) -> Path:
    filename = f"{_normalize_pair(pair)}-{timeframe}-futures.feather"
    futures_path = data_root / exchange / "futures" / filename
    if futures_path.exists():
        return futures_path
    return data_root / exchange / filename


def _summarize_feather(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "status": "missing",
            "path": str(path),
            "rowCount": 0,
            "firstDate": None,
            "lastDate": None,
            "coverageYears": None,
            "startsAtOrBefore2020": False,
            "latestYear": None,
            "fileSizeBytes": None,
            "lastWriteTime": None,
            "error": None,
        }
    try:
        frame = pd.read_feather(path, columns=["date"])
    except Exception as exc:
        try:
            frame = pd.read_feather(path)
        except Exception as fallback_exc:
            return {
                "status": "read_error",
                "path": str(path),
                "rowCount": 0,
                "firstDate": None,
                "lastDate": None,
                "coverageYears": None,
                "startsAtOrBefore2020": False,
                "latestYear": None,
                "fileSizeBytes": path.stat().st_size,
                "lastWriteTime": datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat(),
                "error": f"{type(exc).__name__}: {exc}; fallback={type(fallback_exc).__name__}: {fallback_exc}",
            }
    if frame.empty or "date" not in frame.columns:
        return {
            "status": "empty",
            "path": str(path),
            "rowCount": int(len(frame)),
            "firstDate": None,
            "lastDate": None,
            "coverageYears": None,
            "startsAtOrBefore2020": False,
            "latestYear": None,
            "fileSizeBytes": path.stat().st_size,
            "lastWriteTime": datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat(),
            "error": None,
        }

    dates = pd.to_datetime(frame["date"], utc=True, errors="coerce").dropna()
    if dates.empty:
        first_date = None
        last_date = None
        coverage_years = None
        latest_year = None
        starts_at_or_before_2020 = False
    else:
        first_date = dates.min()
        last_date = dates.max()
        coverage_years = (last_date - first_date).total_seconds() / (365.25 * 24 * 60 * 60)
        latest_year = int(last_date.year)
        starts_at_or_before_2020 = bool(first_date <= TARGET_START)

    return {
        "status": "available",
        "path": str(path),
        "rowCount": int(len(frame)),
        "firstDate": first_date.isoformat() if first_date is not None else None,
        "lastDate": last_date.isoformat() if last_date is not None else None,
        "coverageYears": _round(coverage_years, 4),
        "startsAtOrBefore2020": starts_at_or_before_2020,
        "latestYear": latest_year,
        "fileSizeBytes": path.stat().st_size,
        "lastWriteTime": datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat(),
        "error": None,
    }


def _coverage_rows(
    data_root: Path,
    exchanges: list[str],
    pairs: list[str],
    timeframes: list[str],
    core_pairs: list[str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    core_set = set(core_pairs)
    for exchange in exchanges:
        for pair in pairs:
            for timeframe in timeframes:
                summary = _summarize_feather(_expected_file(data_root, exchange, pair, timeframe))
                rows.append(
                    {
                        "exchange": exchange,
                        "pair": pair,
                        "timeframe": timeframe,
                        "isCorePair": pair in core_set,
                        **summary,
                    }
                )
    return rows


def _aggregate(rows: list[dict[str, Any]], exchanges: list[str], timeframes: list[str]) -> dict[str, Any]:
    total_expected = len(rows)
    available = [row for row in rows if row["status"] == "available"]
    missing = [row for row in rows if row["status"] == "missing"]
    unavailable = [row for row in rows if row["status"] != "available"]

    by_exchange: list[dict[str, Any]] = []
    for exchange in exchanges:
        exchange_rows = [row for row in rows if row["exchange"] == exchange]
        exchange_available = [row for row in exchange_rows if row["status"] == "available"]
        timeframe_rows = []
        for timeframe in timeframes:
            scoped = [row for row in exchange_rows if row["timeframe"] == timeframe]
            scoped_available = [row for row in scoped if row["status"] == "available"]
            rows_counts = [row["rowCount"] for row in scoped_available if row["rowCount"]]
            timeframe_rows.append(
                {
                    "timeframe": timeframe,
                    "availableCount": len(scoped_available),
                    "expectedCount": len(scoped),
                    "availablePairCount": len({row["pair"] for row in scoped_available}),
                    "missingCount": len([row for row in scoped if row["status"] == "missing"]),
                    "errorCount": len([row for row in scoped if row["status"] not in {"available", "missing"}]),
                    "averageRows": _round(mean(rows_counts), 2) if rows_counts else None,
                }
            )
        first_dates = [row["firstDate"] for row in exchange_available if row["firstDate"]]
        last_dates = [row["lastDate"] for row in exchange_available if row["lastDate"]]
        by_exchange.append(
            {
                "exchange": exchange,
                "availableCount": len(exchange_available),
                "expectedCount": len(exchange_rows),
                "availablePairCount": len({row["pair"] for row in exchange_available}),
                "missingCount": len([row for row in exchange_rows if row["status"] == "missing"]),
                "errorCount": len([row for row in exchange_rows if row["status"] not in {"available", "missing"}]),
                "earliestFirstDate": min(first_dates) if first_dates else None,
                "latestLastDate": max(last_dates) if last_dates else None,
                "timeframes": timeframe_rows,
            }
        )

    core_rows = [row for row in rows if row["isCorePair"]]
    core_available = [row for row in core_rows if row["status"] == "available"]
    core_matrix = []
    for exchange in exchanges:
        for timeframe in timeframes:
            scoped = [row for row in core_rows if row["exchange"] == exchange and row["timeframe"] == timeframe]
            core_matrix.append(
                {
                    "exchange": exchange,
                    "timeframe": timeframe,
                    "availablePairs": sorted([row["pair"] for row in scoped if row["status"] == "available"]),
                    "missingPairs": sorted([row["pair"] for row in scoped if row["status"] != "available"]),
                }
            )

    return {
        "totalExpectedFiles": total_expected,
        "availableCount": len(available),
        "missingCount": len(missing),
        "unavailableCount": len(unavailable),
        "availablePct": _round(len(available) / total_expected * 100 if total_expected else 0, 4),
        "byExchange": by_exchange,
        "coreMatrix": core_matrix,
        "coreAvailableCount": len(core_available),
        "coreExpectedCount": len(core_rows),
        "coreAvailablePct": _round(len(core_available) / len(core_rows) * 100 if core_rows else 0, 4),
    }


def _decision(summary: dict[str, Any], exchanges: list[str], timeframes: list[str]) -> dict[str, Any]:
    core_expected = len(DEFAULT_CORE_PAIRS) * len(exchanges) * len(timeframes)
    multi_exchange_core_ready = summary["coreAvailableCount"] >= core_expected
    top100_okx = next((item for item in summary["byExchange"] if item["exchange"] == "okx"), None)
    top100_okx_partial = bool(top100_okx and top100_okx["availableCount"] > 0 and top100_okx["availableCount"] < top100_okx["expectedCount"])
    return {
        "multiExchangeCoreDataReady": multi_exchange_core_ready,
        "top100OkxExpansionPartial": top100_okx_partial,
        "top100FullMultiExchangeReady": summary["availableCount"] == summary["totalExpectedFiles"],
        "readyToRunMultiExchangeStrategyRobustness": False,
        "reason": "Public data coverage is now mapped, but feature panel and strategy replay remain OKX-centered and must be made exchange-aware before multi-exchange robustness claims.",
        "nextAction": "build_exchange_aware_feature_panel_and_core_triad_replay",
        "exchangeDryRunApproved": False,
        "liveTradingApproved": False,
    }


def _summary_markdown(report: dict[str, Any]) -> str:
    coverage = report["coverageSummary"]
    decision = report["decision"]
    lines = [
        "# AlphaPilot V13.5.15 Multi-Exchange Data Coverage",
        "",
        "This is a public historical data coverage report. It is not a strategy change, Dry-run approval, or live-trading approval.",
        "",
        "## Coverage",
        "",
        f"- Expected files: {coverage['totalExpectedFiles']}",
        f"- Available files: {coverage['availableCount']}",
        f"- Available percentage: {coverage['availablePct']}%",
        f"- Core BTC/ETH/SOL coverage: {coverage['coreAvailableCount']} / {coverage['coreExpectedCount']} ({coverage['coreAvailablePct']}%)",
        "",
        "## By Exchange",
        "",
    ]
    for exchange in coverage["byExchange"]:
        lines.append(
            f"- {exchange['exchange']}: {exchange['availableCount']} / {exchange['expectedCount']} files, "
            f"{exchange['availablePairCount']} pairs, latest={exchange['latestLastDate']}"
        )
        for timeframe in exchange["timeframes"]:
            lines.append(
                f"  - {timeframe['timeframe']}: {timeframe['availableCount']} / {timeframe['expectedCount']} files, "
                f"avgRows={timeframe['averageRows']}"
            )

    lines.extend(
        [
            "",
            "## Decision",
            "",
            f"- multiExchangeCoreDataReady: {decision['multiExchangeCoreDataReady']}",
            f"- top100OkxExpansionPartial: {decision['top100OkxExpansionPartial']}",
            f"- top100FullMultiExchangeReady: {decision['top100FullMultiExchangeReady']}",
            f"- readyToRunMultiExchangeStrategyRobustness: {decision['readyToRunMultiExchangeStrategyRobustness']}",
            f"- nextAction: {decision['nextAction']}",
            "",
            "## Runtime Notes",
            "",
        ]
    )
    for note in report["runtimeNotes"]:
        lines.append(f"- {note}")

    lines.extend(
        [
            "",
            "## Safety Boundary",
            "",
            "- No Trade API.",
            "- No Withdraw API.",
            "- No API key storage.",
            "- No real account reads.",
            "- No real position reads.",
            "- No order creation.",
            "- No automatic trading.",
        ]
    )
    return "\n".join(lines) + "\n"


def generate_report(args: argparse.Namespace) -> dict[str, Any]:
    pairs = _parse_csv(args.pairs, get_top100_usdt_swap_research_pairs())
    exchanges = _parse_csv(args.exchanges, DEFAULT_EXCHANGES)
    timeframes = _parse_csv(args.timeframes, DEFAULT_TIMEFRAMES)
    core_pairs = _parse_csv(args.core_pairs, DEFAULT_CORE_PAIRS)
    rows = _coverage_rows(args.data_root, exchanges, pairs, timeframes, core_pairs)
    coverage = _aggregate(rows, exchanges, timeframes)
    report = {
        "version": VERSION,
        "reportId": REPORT_ID,
        "generatedAt": utc_now(),
        "source": "local_public_ohlcv_files",
        "dataRoot": str(args.data_root),
        "targetWindow": {
            "requestedStart": TARGET_START.isoformat(),
            "requestedLatestYear": TARGET_LATEST_YEAR,
            "note": "Coverage reflects local files actually present after public data download attempts.",
        },
        "scope": {
            "exchanges": exchanges,
            "timeframes": timeframes,
            "pairCount": len(pairs),
            "corePairs": core_pairs,
        },
        "coverageSummary": coverage,
        "coverageRows": rows,
        "decision": _decision(coverage, exchanges, timeframes),
        "runtimeNotes": [
            "OKX Top100 2020-2026 expansion can be too heavy for one uninterrupted command; partial public files are reported instead of fabricated.",
            "Binance and Bybit core BTC/ETH/SOL public OHLCV samples were added for exchange-path validation.",
            "The current strategy feature panel remains OKX-centered; multi-exchange data must be wired deliberately before robustness claims.",
        ],
        "safety": {
            "tradeApi": False,
            "withdrawApi": False,
            "apiKeyStorage": False,
            "realAccountRead": False,
            "realPositionRead": False,
            "orderCreation": False,
            "automaticTrading": False,
        },
    }
    return _json_ready(report)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate V13.5.15 multi-exchange data coverage report.")
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--exchanges", default=",".join(DEFAULT_EXCHANGES))
    parser.add_argument("--pairs", default=None)
    parser.add_argument("--core-pairs", default=",".join(DEFAULT_CORE_PAIRS))
    parser.add_argument("--timeframes", default=",".join(DEFAULT_TIMEFRAMES))
    parser.add_argument("--output-report", type=Path, default=DEFAULT_OUTPUT_REPORT)
    parser.add_argument("--output-summary", type=Path, default=DEFAULT_OUTPUT_SUMMARY)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = generate_report(args)
    write_json(args.output_report, report)
    write_text(args.output_summary, _summary_markdown(report))
    print(f"Wrote {args.output_report}")
    print(f"Wrote {args.output_summary}")
    print(
        "available="
        f"{report['coverageSummary']['availableCount']}/{report['coverageSummary']['totalExpectedFiles']} "
        f"core={report['coverageSummary']['coreAvailableCount']}/{report['coverageSummary']['coreExpectedCount']}"
    )


if __name__ == "__main__":
    main()
