"""Backfill official OKX monthly funding archives for V36 readiness."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from alphapilot.data_foundation.okx_historical_funding import (
    OkxHistoricalFundingBackfill,
)
from alphapilot.data_foundation.okx_public import OkxPublicClient
from alphapilot.standard_replication.tsmom_engine import TSMOM_SYMBOLS


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--warehouse-root", type=Path, required=True)
    parser.add_argument("--begin", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--observed-at")
    parser.add_argument("--instrument-id", action="append", dest="instruments")
    parser.add_argument("--base-url", default="https://openapi.okx.com")
    parser.add_argument("--pause-marker", type=Path)
    parser.add_argument("--include-recent-tail", action="store_true")
    return parser


def run(
    argv: Sequence[str] | None = None,
    *,
    client: Any | None = None,
    archive_loader: Callable[[str], bytes] | None = None,
) -> dict[str, Any]:
    args = _parser().parse_args(argv)
    observed_at = args.observed_at or datetime.now(UTC).isoformat()
    backfill_arguments: dict[str, Any] = {
        "warehouse_root": args.warehouse_root,
        "client": client or OkxPublicClient(base_url=args.base_url),
        "instruments": tuple(args.instruments or TSMOM_SYMBOLS),
        "begin": args.begin,
        "end": args.end,
        "observed_at": observed_at,
        "pause_marker": args.pause_marker,
        "include_recent_tail": args.include_recent_tail,
    }
    if archive_loader is not None:
        backfill_arguments["archive_loader"] = archive_loader
    return OkxHistoricalFundingBackfill(**backfill_arguments).run()


def main() -> None:
    result = run()
    summary = {
        key: result[key]
        for key in (
            "status",
            "backfillId",
            "archiveCount",
            "completedArchiveCount",
            "downloadedArchiveCount",
            "recentTailRowCount",
            "manifestPath",
            "checkpointPath",
            "publicDataOnly",
            "sameExchangeOnly",
            "zeroFillUsed",
            "mixedExchangeFundingUsed",
        )
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
