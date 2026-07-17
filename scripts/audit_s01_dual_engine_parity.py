from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the positive-signal S01 synthetic dual-engine parity audit."
    )
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    repo_root = args.repo_root.resolve()
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from alphapilot.formal_validation.dual_engine_parity import (
        write_dual_engine_parity_report,
    )
    from alphapilot.formal_validation.s01_dual_engine_audit import (
        run_s01_synthetic_parity,
    )

    report = run_s01_synthetic_parity(repo_root)
    output = write_dual_engine_parity_report(args.output, report)
    print(
        json.dumps(
            {
                "status": report["status"],
                "adapterRuntimeBase": report["adapterRuntimeBase"],
                "formalSignalCount": report["formalSignalCount"],
                "adapterSignalCount": report["adapterSignalCount"],
                "matchedEventCount": report["matchedEventCount"],
                "matchedLegCount": report["matchedLegCount"],
                "output": str(output),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
