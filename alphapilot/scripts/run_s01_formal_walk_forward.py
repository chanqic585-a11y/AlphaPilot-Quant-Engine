"""Run the V17 S01 formal preflight and stop mechanically when invalid."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from alphapilot.formal_validation.formal_reporting import (
    audit_executable_formal_contract,
    write_pre_run_terminal_bundle,
)
from alphapilot.formal_validation.phase1_contracts import (
    FORMAL_PREREGISTRATION_PATH,
    verify_s01_formal_preregistration,
)


DEFAULT_OUTPUT_ROOT = Path("reports/formal_validation/advisory_r_v17")


def run(repo_root: Path, *, output_root: Path | None = None) -> dict[str, Any]:
    """Execute only the frozen-contract preflight for the current campaign.

    The current frozen contract is incomplete.  This function therefore reads
    only the preregistration, writes a terminal audit bundle, and never opens
    market data, formal result artifacts, or Locked OOS content.
    """

    repo_root = Path(repo_root).resolve()
    preregistration_path = repo_root / FORMAL_PREREGISTRATION_PATH
    preregistration = json.loads(preregistration_path.read_text(encoding="utf-8"))
    if not verify_s01_formal_preregistration(preregistration):
        raise ValueError("frozen S01 formal preregistration hash mismatch")

    issues = audit_executable_formal_contract(preregistration)
    if not issues:
        raise RuntimeError(
            "Formal performance execution is not enabled by this preflight-only runner. "
            "Publish and review a complete new preregistration first."
        )
    destination = Path(output_root) if output_root is not None else repo_root / DEFAULT_OUTPUT_ROOT
    return write_pre_run_terminal_bundle(destination, preregistration, issues)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--output-root", type=Path)
    args = parser.parse_args(argv)
    route = run(args.repo_root, output_root=args.output_root)
    print(json.dumps(route, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
