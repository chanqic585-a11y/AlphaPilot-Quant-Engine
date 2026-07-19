"""Run V37I bounded acquisition and emit the pre-Formal V37J route."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from alphapilot.v37i_acquisition import run_bounded_acquisition


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--panel-manifest", required=True, type=Path)
    parser.add_argument("--inherited-budget", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--frozen-at", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_bounded_acquisition(
        panel_manifest_path=args.panel_manifest,
        inherited_budget_path=args.inherited_budget,
        output_root=args.output_root,
        frozen_at=args.frozen_at,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
