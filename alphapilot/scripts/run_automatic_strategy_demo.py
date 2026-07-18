"""Run resumable stages of the automatic strategy-to-OKX-Demo program."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from alphapilot.research_factory.catalog_frames import load_catalog_frames
from alphapilot.research_factory.program_v19 import run_v19_data_capability
from alphapilot.research_factory.program_v20 import run_v20_candidate_generation


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("v19", "v20"), required=True)
    parser.add_argument("--reports-root", type=Path, default=Path("reports"))
    parser.add_argument("--program-id", required=True)
    parser.add_argument("--baseline-commit")
    parser.add_argument("--program-spec-hash")
    parser.add_argument("--generated-at", required=True)
    parser.add_argument("--catalog", type=Path)
    parser.add_argument("--source-audit", type=Path)
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--baseline-artifact", type=Path, action="append", default=[])
    parser.add_argument("--historical-inventory", type=Path)
    parser.add_argument("--negative-rules", type=Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.stage == "v19":
        required = {
            "baseline_commit": args.baseline_commit,
            "program_spec_hash": args.program_spec_hash,
            "catalog": args.catalog,
            "source_audit": args.source_audit,
            "snapshot": args.snapshot,
        }
        missing = [key for key, value in required.items() if value is None]
        if missing:
            raise ValueError("v19_arguments_missing:" + ",".join(missing))
        result = run_v19_data_capability(
            reports_root=args.reports_root,
            program_id=args.program_id,
            baseline_commit=args.baseline_commit,
            program_spec_hash=args.program_spec_hash,
            generated_at=args.generated_at,
            catalog_path=args.catalog,
            source_audit_path=args.source_audit,
            snapshot_path=args.snapshot,
            baseline_artifacts=args.baseline_artifact,
        )
    elif args.stage == "v20":
        required = {
            "catalog": args.catalog,
            "historical_inventory": args.historical_inventory,
            "negative_rules": args.negative_rules,
        }
        missing = [key for key, value in required.items() if value is None]
        if missing:
            raise ValueError("v20_arguments_missing:" + ",".join(missing))
        result = run_v20_candidate_generation(
            reports_root=args.reports_root,
            program_id=args.program_id,
            generated_at=args.generated_at,
            historical_inventory_path=args.historical_inventory,
            negative_rules_path=args.negative_rules,
            frames=load_catalog_frames(args.catalog, timeframes=("1h", "4h")),
        )
    else:
        raise ValueError(f"unsupported stage: {args.stage}")
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["status"] == "completed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
