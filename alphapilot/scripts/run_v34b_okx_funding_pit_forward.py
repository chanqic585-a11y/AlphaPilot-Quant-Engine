"""Run the bounded V34B OKX public funding, PIT, and forward-data extension."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path

from alphapilot.data_foundation.checkpoint import write_json_atomic
from alphapilot.data_foundation.okx_official_v1 import PILOT_INSTRUMENTS
from alphapilot.data_foundation.okx_official_v1_forward import (
    OkxOfficialV1ForwardCollector,
)
from alphapilot.data_foundation.okx_public import OkxPublicClient
from alphapilot.research_factory.program_v33 import record_v34b_data_extension


DEFAULT_WAREHOUSE_ROOT = Path("D:/Codex-Workspace") / "\u56de\u6d4b\u6570\u636e"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--program-root", type=Path, required=True)
    parser.add_argument(
        "--warehouse-root",
        type=Path,
        default=DEFAULT_WAREHOUSE_ROOT,
    )
    parser.add_argument(
        "--instruments",
        default=",".join(PILOT_INSTRUMENTS),
        help="Comma-separated OKX SWAP instrument ids.",
    )
    parser.add_argument(
        "--observed-at",
        default=datetime.now(UTC).replace(microsecond=0).isoformat(),
    )
    parser.add_argument("--implementation-commit", required=True)
    parser.add_argument("--writer-id", default="v34b-public-data-cli")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    program_root = args.program_root.resolve()
    if not (program_root / "program_summary.json").is_file():
        raise FileNotFoundError("v33_program_summary_missing")
    implementation_commit = str(args.implementation_commit).strip()
    if len(implementation_commit) < 7:
        raise ValueError("implementation_commit_is_not_a_git_identity")
    instruments = tuple(
        value.strip() for value in str(args.instruments).split(",") if value.strip()
    )
    program_summary = json.loads(
        (program_root / "program_summary.json").read_text(encoding="utf-8")
    )
    base_snapshot_id = str(program_summary.get("dataSnapshotId") or "").strip()
    if not base_snapshot_id:
        raise ValueError("v34a_data_snapshot_must_be_registered_first")
    result = OkxOfficialV1ForwardCollector(
        warehouse_root=args.warehouse_root,
        client=OkxPublicClient(),
        instruments=instruments,
        observed_at=str(args.observed_at),
        base_snapshot_id=base_snapshot_id,
    ).run()
    receipt = {
        "schemaVersion": "v34b_okx_public_data_extension_receipt_v1",
        "programId": program_summary["programId"],
        "implementationCommit": implementation_commit,
        "warehouseRoot": str(args.warehouse_root.resolve()),
        "extensionResult": result,
    }
    receipt_path = program_root / "v34b_data_extension_receipt.json"
    write_json_atomic(receipt_path, receipt)
    updated = record_v34b_data_extension(
        program_root=program_root,
        extension_result=result,
        created_at=datetime.now(UTC).replace(microsecond=0).isoformat(),
        writer_id=str(args.writer_id),
    )
    print(
        json.dumps(
            {
                "programSummary": updated,
                "extensionResult": result,
                "receiptPath": str(receipt_path),
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
