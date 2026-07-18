from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


SCRIPT_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPT_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_REPO_ROOT))

from alphapilot.formal_validation.future_locked_oos import (
    write_phase2_future_locked_oos_evidence,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Freeze metadata-only Future Locked OOS identity and zero-access ledger."
    )
    parser.add_argument("--repo-root", type=Path, default=SCRIPT_REPO_ROOT)
    parser.add_argument("--metadata-root", type=Path, default=None)
    parser.add_argument(
        "--evidence-root",
        type=Path,
        default=SCRIPT_REPO_ROOT
        / "reports"
        / "formal_validation"
        / "v13_27_1_17_s01_phase2_readiness",
    )
    args = parser.parse_args()
    result = write_phase2_future_locked_oos_evidence(
        args.repo_root,
        args.evidence_root,
        metadata_root=args.metadata_root,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
