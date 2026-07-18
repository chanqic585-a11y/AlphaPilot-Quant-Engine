"""Build the V13.27.1.17 read-only evidence delivery packages."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from alphapilot.reports.v17_evidence_delivery import build_evidence_delivery


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--route-root",
        type=Path,
        default=Path("reports/formal_validation/advisory_r_v17"),
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("reports/v13_27_1_17_evidence_delivery"),
    )
    parser.add_argument("--console-root", type=Path)
    parser.add_argument("--docs-root", type=Path)
    parser.add_argument("--git-executable", type=Path)
    args = parser.parse_args(argv)
    repo_root = args.repo_root.resolve()
    route_root = args.route_root
    if not route_root.is_absolute():
        route_root = repo_root / route_root
    output_root = args.output_root
    if not output_root.is_absolute():
        output_root = repo_root / output_root
    result = build_evidence_delivery(
        repo_root,
        output_root,
        route_root=route_root,
        console_root=args.console_root,
        docs_root=args.docs_root,
        git_executable=args.git_executable,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
