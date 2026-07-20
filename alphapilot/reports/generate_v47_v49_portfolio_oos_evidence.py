"""CLI for V47 verification and V49 pre-result portfolio identity freezing."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from alphapilot.portfolio_oos import generate_v47_v49_evidence


def _git(repo: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=repo, text=True, encoding="utf-8"
    ).strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--v46-report-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--remote-ref", required=True)
    args = parser.parse_args()

    local_commit = _git(args.repo, "rev-parse", "HEAD")
    remote_commit = _git(args.repo, "rev-parse", args.remote_ref)
    result = generate_v47_v49_evidence(
        v46_report_dir=args.v46_report_dir,
        output_dir=args.output_dir,
        publish_receipt={
            "branch": _git(args.repo, "branch", "--show-current"),
            "commit": local_commit,
            "remoteBranch": args.remote_ref,
            "remoteCommit": remote_commit,
            "pushed": local_commit == remote_commit,
        },
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
