"""Write the deterministic seed preregistration before any performance run."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .preregistration import build_seed_preregistration


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("research/factor_preregistrations/alpha191_seed_v1.json"),
    )
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(build_seed_preregistration(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
