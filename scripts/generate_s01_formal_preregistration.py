"""Generate the frozen S01 formal preregistration without running results."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from alphapilot.formal_validation.phase1_contracts import (
    build_s01_formal_preregistration,
    verify_s01_formal_preregistration,
    write_s01_formal_preregistration,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    repo_root = args.repo_root.resolve()
    payload = build_s01_formal_preregistration(repo_root)
    if not verify_s01_formal_preregistration(payload):
        raise RuntimeError("generated preregistration hash verification failed")
    path = write_s01_formal_preregistration(payload, repo_root)
    print(
        json.dumps(
            {
                "status": "preregistered_not_executed",
                "campaignId": payload["campaignId"],
                "candidateId": payload["sourceCandidateId"],
                "preregistrationHash": payload["preregistrationHash"],
                "path": path.relative_to(repo_root).as_posix(),
                "formalResultCount": 0,
                "lockedOosAccessCount": 0,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
