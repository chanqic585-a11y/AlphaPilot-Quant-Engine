"""Initialize V33 and run the bounded V34A OKX public-data pilot."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path

from alphapilot.data_foundation.checkpoint import write_json_atomic
from alphapilot.data_foundation.okx_official_v1 import OkxOfficialV1Pilot
from alphapilot.data_foundation.okx_public import OkxPublicClient
from alphapilot.evolution.registry.hashing import sha256_file
from alphapilot.research_factory.program_v33 import (
    initialize_dual_track_successor,
    record_v34a_data_pilot,
)


PREDECESSOR_ID = "automatic_strategy_renewal_v28_4e6ab55a5e949716"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--warehouse-root",
        type=Path,
        default=Path(r"D:\Codex-Workspace\回测数据"),
    )
    parser.add_argument("--implementation-contract", type=Path, required=True)
    parser.add_argument("--implementation-commit", required=True)
    parser.add_argument(
        "--generated-at",
        default=datetime.now(UTC).replace(microsecond=0).isoformat(),
    )
    parser.add_argument("--writer-id", default="v33-v34a-cli")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    repo_root = args.repo_root.resolve()
    reports_root = repo_root / "reports"
    contract_path = args.implementation_contract.resolve()
    if not contract_path.is_file():
        raise FileNotFoundError(contract_path)
    implementation_commit = str(args.implementation_commit).strip()
    if len(implementation_commit) < 7:
        raise ValueError("implementation_commit_is_not_a_git_identity")
    predecessor_root = (
        reports_root / "automatic_research_program" / PREDECESSOR_ID
    )
    summary = initialize_dual_track_successor(
        reports_root=reports_root,
        predecessor_program_root=predecessor_root,
        implementation_contract_hash=sha256_file(contract_path),
        implementation_commit=implementation_commit,
        generated_at=str(args.generated_at),
        writer_id=str(args.writer_id),
    )
    program_root = reports_root / "dual_track" / str(summary["programId"])
    pilot_result = OkxOfficialV1Pilot(
        warehouse_root=args.warehouse_root,
        client=OkxPublicClient(),
    ).run()
    receipt = {
        "schemaVersion": "v34a_okx_data_pilot_receipt_v1",
        "programId": summary["programId"],
        "implementationCommit": implementation_commit,
        "implementationContractPath": str(contract_path),
        "implementationContractSha256": sha256_file(contract_path),
        "warehouseRoot": str(args.warehouse_root.resolve()),
        "pilotResult": pilot_result,
    }
    write_json_atomic(program_root / "v34a_data_pilot_receipt.json", receipt)
    updated = record_v34a_data_pilot(
        program_root=program_root,
        pilot_result=pilot_result,
        created_at=datetime.now(UTC).replace(microsecond=0).isoformat(),
        writer_id=str(args.writer_id),
    )
    output = {
        "programSummary": updated,
        "pilotResult": pilot_result,
        "receiptPath": str(program_root / "v34a_data_pilot_receipt.json"),
    }
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
