"""Collect verified public OKX candle increments after local cutoffs."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable

from alphapilot.data_foundation.okx_public import (
    BAR_VALUES,
    OkxPublicClient,
    PublicIncrement,
    collect_public_increment,
)


def _csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def parse_timeframes(value: str) -> list[str]:
    timeframes = list(dict.fromkeys(item.lower() for item in _csv(value)))
    invalid = sorted(set(timeframes) - set(BAR_VALUES))
    if invalid:
        raise argparse.ArgumentTypeError(
            f"Unsupported timeframe(s): {', '.join(invalid)}. "
            f"Supported values: {', '.join(BAR_VALUES)}"
        )
    if not timeframes:
        raise argparse.ArgumentTypeError("At least one timeframe is required")
    return timeframes


def build_report(rows: Iterable[PublicIncrement]) -> dict[str, object]:
    row_list = list(rows)
    status_counts = Counter(row.status for row in row_list)
    blocked_count = sum(count for status, count in status_counts.items() if status.startswith("blocked_"))
    failed_count = status_counts.get("failed", 0)
    continuity_failure_count = sum(
        row.continuityStatus in {"gap", "misaligned"}
        for row in row_list
        if row.status == "collected"
    )
    complete = bool(row_list) and not failed_count and not blocked_count and not continuity_failure_count
    return {
        "reportId": "v13_16_public_increment_report",
        "version": "V13.16.0",
        "status": "completed" if complete else "completed_with_errors",
        "generatedAt": datetime.now(UTC).isoformat(),
        "requestedCount": len(row_list),
        "collectedCount": status_counts.get("collected", 0),
        "upToDateOrUnavailableCount": status_counts.get("up_to_date_or_unavailable", 0),
        "blockedCount": blocked_count,
        "failedCount": failed_count,
        "continuityFailureCount": continuity_failure_count,
        "statusCounts": dict(sorted(status_counts.items())),
        "rows": [row.to_dict() for row in row_list],
        "safetyBoundary": {
            "publicDataOnly": True,
            "apiKeyUsed": False,
            "accountRead": False,
            "tradeApiUsed": False,
            "withdrawApiUsed": False,
            "orderCreated": False,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect V13.16 OKX public OHLCV increments.")
    parser.add_argument("--canonical-root", default="data/market/canonical")
    parser.add_argument("--instruments", default="BTC-USDT-SWAP,ETH-USDT-SWAP,SOL-USDT-SWAP")
    parser.add_argument("--timeframes", type=parse_timeframes, default=parse_timeframes("15m,1h,4h,1d"))
    parser.add_argument("--output-json", default="reports/v13_16_public_increment_report.json")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    client = OkxPublicClient()
    increments = [
        collect_public_increment(
            client=client,
            canonical_root=args.canonical_root,
            instrument_id=instrument,
            timeframe=timeframe,
        )
        for instrument in _csv(args.instruments)
        for timeframe in args.timeframes
    ]
    report = build_report(increments)
    output = Path(args.output_json)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: report[key] for key in (
        "reportId",
        "version",
        "status",
        "requestedCount",
        "collectedCount",
        "upToDateOrUnavailableCount",
        "blockedCount",
        "failedCount",
        "continuityFailureCount",
    )}, ensure_ascii=False, indent=2))
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
