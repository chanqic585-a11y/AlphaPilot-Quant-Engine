"""CLI for the bounded V13.27.1.46 portfolio rescue campaign."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from alphapilot.portfolio_rescue.contracts import build_default_campaign
from alphapilot.portfolio_rescue.evidence import (
    freeze_preregistration,
    run_and_write_portfolio_rescue,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    campaign = build_default_campaign()
    freeze_preregistration(args.output_dir, campaign, args.ledger_dir)
    summary = run_and_write_portfolio_rescue(args.output_dir, campaign, args.ledger_dir)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
