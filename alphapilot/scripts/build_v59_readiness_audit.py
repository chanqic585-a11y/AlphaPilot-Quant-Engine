"""Build a read-only V59 audit of factor, model, and data registry evidence."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from alphapilot.adaptive_learning.v59_readiness_audit import audit_registry_database
from alphapilot.data_foundation.checkpoint import write_json_atomic


def build_console_summary(payload: dict, *, output_path: Path) -> dict:
    """Return a bounded terminal summary while the full audit stays on disk."""

    keys = (
        "status",
        "auditHash",
        "factorRunCount",
        "formalFactorRunCount",
        "modelCount",
        "liveEligibleModelCount",
        "dataSnapshotCount",
        "formalDataSnapshotCount",
        "blockers",
    )
    return {
        **{key: payload.get(key) for key in keys},
        "output": str(output_path),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry-path", type=Path, required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("reports/v59_adaptive_learning/registry_evidence_audit.json"),
    )
    parser.add_argument("--generated-at")
    args = parser.parse_args(argv)

    result = audit_registry_database(args.registry_path)
    payload = {
        **result,
        "generatedAt": args.generated_at
        or datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }
    output = args.output.expanduser().resolve()
    write_json_atomic(output, payload)
    print(
        json.dumps(
            build_console_summary(payload, output_path=output),
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
