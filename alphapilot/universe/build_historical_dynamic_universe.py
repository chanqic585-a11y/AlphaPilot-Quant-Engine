"""CLI for V13.4.13 Historical Dynamic Universe Builder."""

from __future__ import annotations

import argparse
from pathlib import Path

from alphapilot.universe.dynamic_universe_schema import DynamicUniverseConfig
from alphapilot.universe.historical_dynamic_universe_builder import build_historical_dynamic_universe, write_outputs


DEFAULT_OUTPUT = Path("reports/v13_4_13_dynamic_universe_snapshots.json")
DEFAULT_SAMPLE_OUTPUT = Path("reports/v13_4_13_dynamic_universe_sample_snapshots.json")
DEFAULT_BUILD_REPORT = Path("reports/v13_4_13_dynamic_universe_build_report.json")
DEFAULT_SUMMARY = Path("reports/v13_4_13_dynamic_universe_summary.md")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build historical Dynamic Universe snapshots.")
    parser.add_argument("--timerange", default="20260101-")
    parser.add_argument("--refresh-frequency", choices=["daily", "3d"], default="daily")
    parser.add_argument("--max-pairs", type=int, default=10)
    parser.add_argument("--candidate-mode", choices=["top30"], default="top30")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--sample-output", type=Path, default=DEFAULT_SAMPLE_OUTPUT)
    parser.add_argument("--build-report", type=Path, default=DEFAULT_BUILD_REPORT)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--data-path", default="user_data/data/okx/futures")
    parser.add_argument("--warmup-days", type=int, default=30)
    args = parser.parse_args()

    config = DynamicUniverseConfig(
        refreshFrequency=args.refresh_frequency,
        maxPairs=args.max_pairs,
        candidateMode=args.candidate_mode,
        timerange=args.timerange,
        warmupDays=args.warmup_days,
        dataPath=args.data_path,
    )
    outputs = build_historical_dynamic_universe(config)
    write_outputs(outputs, args.output, args.sample_output, args.build_report, args.summary)
    print(f"Dynamic universe status: {outputs.report.status}")
    print(f"Snapshot count: {len(outputs.snapshots)}")
    print(f"Snapshots: {args.output}")
    print(f"Sample snapshots: {args.sample_output}")
    print(f"Build report: {args.build_report}")
    print(f"Summary: {args.summary}")
    if outputs.report.status != "success":
        print("No successful snapshots were generated. Do not tag V13.4.13 until data availability is fixed.")


if __name__ == "__main__":
    main()

