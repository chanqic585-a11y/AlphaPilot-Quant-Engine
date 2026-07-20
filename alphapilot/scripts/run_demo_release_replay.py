"""CLI for the V13.27.1.46 offline Demo release replay."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from alphapilot.demo_release_replay.evidence import write_replay_evidence
from alphapilot.demo_release_replay.replay import run_demo_release_replay


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contracts-dir", type=Path, required=True)
    parser.add_argument("--low-frequency-report", type=Path, required=True)
    parser.add_argument("--short-cycle-report", type=Path, required=True)
    parser.add_argument("--okx-data-path", type=Path, required=True)
    parser.add_argument("--binance-vision-data-path", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    contracts, results, originals, warnings = run_demo_release_replay(
        contracts_dir=args.contracts_dir,
        low_frequency_report=args.low_frequency_report,
        short_cycle_report=args.short_cycle_report,
        okx_data_path=args.okx_data_path,
        binance_vision_data_path=args.binance_vision_data_path,
    )
    summary = write_replay_evidence(
        args.output_dir,
        contracts,
        results,
        originals,
        load_warnings=warnings,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
