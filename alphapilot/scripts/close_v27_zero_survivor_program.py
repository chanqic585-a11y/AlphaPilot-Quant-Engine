"""Materialize the terminal evidence bundle for a zero-survivor V27 program."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from alphapilot.research_factory.program_v27_closeout import (
    materialize_v27_zero_survivor_closeout,
)


DEFAULT_PROGRAM_ID = "automatic_strategy_to_demo_v26_2aff44adf84d039c"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--program-id", default=DEFAULT_PROGRAM_ID)
    parser.add_argument("--prompt-path", type=Path, required=True)
    parser.add_argument(
        "--generated-at",
        default=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    repo = args.repo_root.resolve()
    result = materialize_v27_zero_survivor_closeout(
        reports_root=repo / "reports",
        program_id=args.program_id,
        prompt_path=args.prompt_path.resolve(),
        generated_at=args.generated_at,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
