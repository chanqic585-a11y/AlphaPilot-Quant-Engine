"""Write the complete fail-closed Alpha191 metadata registry."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from alphapilot.evolution.registry.hashing import stable_hash

from .registry import build_alpha191_registry


def write_registry(output_path: Path, conflict_path: Path) -> dict[str, object]:
    records = build_alpha191_registry()
    payload = {
        "schemaVersion": "alpha191_registry_v1",
        "registryHash": stable_hash([item.to_dict() for item in records], prefix="alpha191_registry"),
        "registeredCount": len(records),
        "reviewedExecutableCount": sum(bool(item.canonical_formula) for item in records),
        "records": [item.to_dict() for item in records],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    unresolved = [item.factor_id for item in records if item.formula_status == "待人工确认"]
    conflict_payload = {
        "schemaVersion": "alpha191_formula_conflicts_v1",
        "unresolvedCount": len(unresolved),
        "unresolvedFactorIds": unresolved,
        "policy": "Unresolved formulas remain non-executable and cannot enter a seed preregistration.",
    }
    conflict_path.write_text(
        json.dumps(conflict_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("reports/factor_lab/alpha191_registry.json"),
    )
    parser.add_argument(
        "--conflicts",
        type=Path,
        default=Path("reports/factor_lab/alpha191_formula_conflicts.json"),
    )
    args = parser.parse_args()
    write_registry(args.output, args.conflicts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
