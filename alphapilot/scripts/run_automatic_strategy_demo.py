"""Run resumable stages of the automatic strategy-to-OKX-Demo program."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from alphapilot.research_factory.program_v19 import run_v19_data_capability


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("v19",), required=True)
    parser.add_argument("--reports-root", type=Path, default=Path("reports"))
    parser.add_argument("--program-id", required=True)
    parser.add_argument("--baseline-commit", required=True)
    parser.add_argument("--program-spec-hash", required=True)
    parser.add_argument("--generated-at", required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--source-audit", type=Path, required=True)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--baseline-artifact", type=Path, action="append", default=[])
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.stage != "v19":
        raise ValueError(f"unsupported stage: {args.stage}")
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
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["status"] == "completed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
