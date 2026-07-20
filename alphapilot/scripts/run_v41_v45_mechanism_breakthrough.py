"""Run the bounded V41-V45 mechanism campaign using reusable local OHLCV only."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Sequence

from alphapilot.mechanism_breakthrough.campaign import run_mechanism_breakthrough_campaign
from alphapilot.mechanism_breakthrough.program import write_successor_program_evidence


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--reference-package-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--frozen-at", required=True)
    parser.add_argument("--code-commit", required=True)
    parser.add_argument("--quant-merge-commit", required=True)
    parser.add_argument("--console-merge-commit", required=True)
    parser.add_argument("--docs-merge-commit", required=True)
    parser.add_argument("--inherited-full-backtests", type=int, default=91)
    parser.add_argument("--prepare-only", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    credentials_injected = all(
        bool(os.environ.get(name))
        for name in (
            "OKX_DEMO_API_KEY",
            "OKX_DEMO_SECRET_KEY",
            "OKX_DEMO_PASSPHRASE",
        )
    )
    write_successor_program_evidence(
        output_root=args.output_root,
        frozen_at=args.frozen_at,
        quant_merge_commit=args.quant_merge_commit,
        console_merge_commit=args.console_merge_commit,
        docs_merge_commit=args.docs_merge_commit,
        inherited_full_backtests=args.inherited_full_backtests,
        demo_credentials_injected=credentials_injected,
    )
    result = run_mechanism_breakthrough_campaign(
        data_root=args.data_root,
        reference_package_root=args.reference_package_root,
        output_root=args.output_root / "research",
        inherited_full_backtests=args.inherited_full_backtests,
        frozen_at=args.frozen_at,
        code_commit=args.code_commit,
        prepare_only=args.prepare_only,
    )
    print(
        {
            "status": result["status"],
            "campaignId": result["campaignId"],
            "candidateCount": result["candidateCount"],
            "prefilterSurvivorCount": result["prefilterSurvivorCount"],
            "lockedOosReadCount": result["lockedOosReadCount"],
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
