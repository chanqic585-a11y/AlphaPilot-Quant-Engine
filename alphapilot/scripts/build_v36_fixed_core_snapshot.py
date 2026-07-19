"""Build the V36 fixed-core reference manifest without copying candle files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from alphapilot.automatic_candidate_research.fixed_core_snapshot import (
    build_fixed_core_snapshot_manifest,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--core-universe-path", required=True, type=Path)
    parser.add_argument("--data-root", required=True, type=Path)
    parser.add_argument("--output-path", required=True, type=Path)
    parser.add_argument("--timeframe", action="append", default=[])
    args = parser.parse_args()
    manifest = build_fixed_core_snapshot_manifest(
        core_universe_path=args.core_universe_path,
        data_root=args.data_root,
        output_path=args.output_path,
        timeframes=tuple(args.timeframe or ["1h"]),
    )
    print(
        json.dumps(
            {
                "snapshotId": manifest["snapshotId"],
                "partitionCount": manifest["partitionCount"],
                "historicalPitUniverse": manifest["historicalPitUniverse"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
