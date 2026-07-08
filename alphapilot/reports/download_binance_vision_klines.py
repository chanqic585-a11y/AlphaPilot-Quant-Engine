"""CLI for Binance Vision public kline downloads.

This command downloads public historical OHLCV data only. It does not use API
keys, private exchange endpoints, account data, positions, orders, dry-run, or
live trading.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from alphapilot.data_expansion.binance_vision_klines import (
    BinanceVisionDownloadConfig,
    download_binance_vision_klines,
    save_download_report,
)


def _split_csv(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


def main() -> None:
    parser = argparse.ArgumentParser(description="Download Binance Vision public USDT futures klines.")
    parser.add_argument("--pairs", required=True)
    parser.add_argument("--timeframes", default="15m,30m,1h")
    parser.add_argument("--start-month", default="2020-01")
    parser.add_argument("--end-month", default="2026-07")
    parser.add_argument("--output-path", default="user_data/data/binance_vision/futures")
    parser.add_argument("--cache-path", default="user_data/data/binance_vision/raw_zip_cache")
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--timeout-seconds", type=int, default=30)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--report-path", default="reports/v13_7_40_binance_vision_download_report.json")
    args = parser.parse_args()

    config = BinanceVisionDownloadConfig(
        pairs=_split_csv(args.pairs),
        timeframes=_split_csv(args.timeframes),
        startMonth=args.start_month,
        endMonth=args.end_month,
        outputPath=Path(args.output_path),
        cachePath=Path(args.cache_path),
        workers=args.workers,
        force=args.force,
        timeoutSeconds=args.timeout_seconds,
    )
    report = download_binance_vision_klines(config)
    save_download_report(report, Path(args.report_path))
    print(json.dumps({
        "status": report["status"],
        "taskCount": report["taskCount"],
        "statusCounts": report["statusCounts"],
        "outputCount": report["outputCount"],
        "elapsedSeconds": report["elapsedSeconds"],
        "reportPath": args.report_path,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
