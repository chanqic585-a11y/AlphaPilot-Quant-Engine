"""Generate V13.5.11 cross-market public data smoke report."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from alphapilot.cross_market.public_market_data import (
    DEFAULT_CROSS_MARKET_SYMBOLS,
    CrossMarketSymbol,
    collect_cross_market_smoke,
    parse_date,
)
from alphapilot.reports.generate_v13_5_derivatives_ml_strategy_report import _json_ready, write_json, write_text


DEFAULT_OUTPUT_REPORT = Path("reports/v13_5_11_cross_market_public_data_smoke_report.json")
DEFAULT_OUTPUT_SUMMARY = Path("reports/v13_5_11_cross_market_public_data_smoke_summary.md")
DEFAULT_RAW_CACHE_DIR = Path("user_data/cross_market_data/v13_5_11")


def parse_symbols(value: str | None) -> list[CrossMarketSymbol]:
    if not value:
        return DEFAULT_CROSS_MARKET_SYMBOLS
    defaults = {item.symbol: item for item in DEFAULT_CROSS_MARKET_SYMBOLS}
    output: list[CrossMarketSymbol] = []
    for raw in value.split(","):
        symbol = raw.strip()
        if not symbol:
            continue
        output.append(defaults.get(symbol) or CrossMarketSymbol(symbol, symbol, "custom", "unknown", "unknown"))
    return output


def build_summary(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# V13.5.11 Cross-Market Public Data Smoke Report",
        "",
        "This report verifies public daily OHLCV access across A-share, Hong Kong, US ETF, and index samples.",
        "It is research-only and does not create trading signals or execution permissions.",
        "",
        "## Summary",
        "",
        f"- Status: `{report['status']}`",
        f"- Symbol count: `{summary['symbolCount']}`",
        f"- Success count: `{summary['successCount']}`",
        f"- Failure count: `{summary['failureCount']}`",
        f"- Total rows: `{summary['totalRows']}`",
        f"- Markets: `{', '.join(summary['markets'])}`",
        f"- Range: `{report['requestedRange']['startDate']} -> {report['requestedRange']['endDate']}`",
        f"- Interval: `{report['requestedRange']['interval']}`",
        "",
        "## Symbol Quality",
        "",
    ]
    for item in report["symbols"]:
        meta = item["metadata"]
        item_summary = item["summary"]
        lines.extend(
            [
                f"- `{meta['symbol']}` ({meta['market']}, {meta['display_name']})",
                f"  - status: `{item['status']}`",
                f"  - rows: `{item_summary.get('rowCount')}`",
                f"  - date range: `{item_summary.get('startDate')} -> {item_summary.get('endDate')}`",
                f"  - quality: `{item_summary.get('dataQualityScore')}`",
                f"  - daily volatility: `{item_summary.get('returnVolDailyPct')}`",
                f"  - max drawdown: `{item_summary.get('maxDrawdownPct')}`",
            ]
        )
        if item.get("error"):
            lines.append(f"  - error: `{item['error']}`")
    lines.extend(
        [
            "",
            "## Integration Boundary",
            "",
            "- Cross-market samples are research references only.",
            "- A-share, Hong Kong, US ETF, and index samples must stay explicitly labeled.",
            "- These samples are not crypto trade commands.",
            "- Raw cache files are local-only and are not committed to Git.",
            "- Data source terms must be reviewed before production redistribution.",
            "",
            "## Safety Boundary",
            "",
            "- No Trade API.",
            "- No Withdraw API.",
            "- No API key storage.",
            "- No real account reads.",
            "- No real position reads.",
            "- No real orders.",
            "- No exchange Dry-run approval.",
            "- No live trading approval.",
            "- No automatic trading.",
        ]
    )
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate V13.5.11 cross-market public data smoke report.")
    parser.add_argument("--start-date", default="2024-01-01")
    parser.add_argument("--end-date", default="2026-07-06")
    parser.add_argument("--interval", default="1d")
    parser.add_argument("--symbols", default=None)
    parser.add_argument("--output-report", default=str(DEFAULT_OUTPUT_REPORT))
    parser.add_argument("--output-summary", default=str(DEFAULT_OUTPUT_SUMMARY))
    parser.add_argument("--raw-cache-dir", default=str(DEFAULT_RAW_CACHE_DIR))
    parser.add_argument("--skip-raw-cache", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    symbols = parse_symbols(args.symbols)
    raw_cache_dir = None if args.skip_raw_cache else Path(args.raw_cache_dir)
    report = collect_cross_market_smoke(
        symbols=symbols,
        start_date=parse_date(args.start_date),
        end_date=parse_date(args.end_date),
        interval=args.interval,
        raw_cache_dir=raw_cache_dir,
    )
    write_json(Path(args.output_report), _json_ready(report))
    write_text(Path(args.output_summary), build_summary(report))


if __name__ == "__main__":
    main()
