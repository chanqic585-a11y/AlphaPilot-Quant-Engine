"""Write the V13.27.1.17 Phase 2 engineering-readiness evidence bundle."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from alphapilot.formal_validation.phase2_readiness import (  # noqa: E402
    DEFAULT_EVIDENCE_ROOT,
    build_phase2_readiness_audit,
    write_phase2_evidence_bundle,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--evidence-root", type=Path, default=DEFAULT_EVIDENCE_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_EVIDENCE_ROOT)
    args = parser.parse_args()
    repo_root = args.repo_root.resolve()
    evidence_root = args.evidence_root
    output_root = args.output_root
    if not evidence_root.is_absolute():
        evidence_root = repo_root / evidence_root
    if not output_root.is_absolute():
        output_root = repo_root / output_root
    audit = build_phase2_readiness_audit(repo_root, evidence_root)
    written = write_phase2_evidence_bundle(audit, output_root)
    print(
        json.dumps(
            {
                "status": "passed"
                if audit["gates"]["formalExecution"]["status"] == "ready"
                else "blocked",
                "route": audit["route"],
                "lockedOosAdmission": audit["gates"]["lockedOosAdmission"][
                    "status"
                ],
                "artifacts": [str(path) for path in written],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if audit["gates"]["formalExecution"]["status"] == "ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
