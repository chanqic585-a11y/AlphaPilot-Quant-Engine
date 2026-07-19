"""Run the bounded and resumable V37B reference-strategy campaign."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from alphapilot.reference_strategy_research.workflow import run_reference_workflow


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--code-commit", required=True)
    parser.add_argument(
        "--prepare-only",
        action="store_true",
        help="Freeze artifacts and preregistration without reading campaign results.",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    result = run_reference_workflow(
        repo_root=args.repo,
        package_path=args.package,
        code_commit=str(args.code_commit),
        execute_campaign=not args.prepare_only,
    )
    print(json.dumps(result, ensure_ascii=False, default=str))
    return 0 if result["status"] in {"preregistered", "completed"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
