"""Generate the additive V46 provisional research Demo approval sidecar."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from alphapilot.portfolio_provisional_demo.evidence import generate_patch_evidence
from alphapilot.portfolio_provisional_demo.sources import (
    build_replay_parity_audit,
    load_demo_universe_snapshot,
    load_research_instruments,
    sha256_file,
    verify_patch_instruction,
)


def _timestamp(value: str | None) -> str:
    return value or datetime.now(UTC).isoformat().replace("+00:00", "Z")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Freeze an unapproved V46 provisional research Demo release."
    )
    parser.add_argument("--v46-report-dir", type=Path, required=True)
    parser.add_argument("--v49-identity-dir", type=Path, required=True)
    parser.add_argument("--component-contract-dir", type=Path, required=True)
    parser.add_argument("--demo-universe-database", type=Path, required=True)
    parser.add_argument("--v46-evidence-zip", type=Path, required=True)
    parser.add_argument("--expected-v46-evidence-zip-sha256", required=True)
    parser.add_argument("--patch-instruction", type=Path, required=True)
    parser.add_argument("--patch-manifest", type=Path, required=True)
    parser.add_argument("--quant-source-commit", required=True)
    parser.add_argument("--console-source-commit", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--generated-at")
    parser.add_argument("--test-evidence", action="append", default=[])
    args = parser.parse_args()

    generated_at = _timestamp(args.generated_at)
    patch_receipt = verify_patch_instruction(
        args.patch_instruction, args.patch_manifest
    )
    zip_sha = sha256_file(args.v46_evidence_zip)
    if zip_sha != args.expected_v46_evidence_zip_sha256:
        raise ValueError("v46_evidence_zip_hash_mismatch")

    v46_report = args.v46_report_dir.resolve()
    selected_ledger = v46_report / "policy_ledgers" / "pair_14d_cooldown.parquet"
    research_instruments = load_research_instruments(selected_ledger)
    replay_audit = build_replay_parity_audit(
        v46_report_dir=v46_report,
        selected_policy_ledger=selected_ledger,
    )
    universe = load_demo_universe_snapshot(args.demo_universe_database)
    replay_source = Path(__file__).parents[1] / "portfolio_rescue" / "replay.py"
    v49 = args.v49_identity_dir.resolve()
    verification = json.loads(
        (v49 / "v46_evidence_verification.json").read_text(encoding="utf-8")
    )
    implementation_receipt = {
        "schemaVersion": "v46_provisional_demo_patch_implementation_receipt_v1",
        "generatedAt": generated_at,
        "currentAtomicWork": {"preserved": True, "interrupted": False},
        "patchInstruction": patch_receipt,
        "sourceCommits": {
            "quant": args.quant_source_commit,
            "console": args.console_source_commit,
        },
        "historicalEvidence": {
            "v46ArtifactsChanged": False,
            "v46EvidenceZip": args.v46_evidence_zip.name,
            "v46EvidenceZipSha256": zip_sha,
            "historicalEvidenceClass": "development_selected_result",
            "formalPass": False,
        },
        "runtimeSources": {
            "demoUniverseDatabase": args.demo_universe_database.name,
            "demoUniverseDatabaseSha256": universe["sourceDatabaseSha256"],
            "demoUniverseReadOnly": universe["readOnly"],
        },
        "safety": {
            "approvalCreated": False,
            "demoArm": False,
            "strategyOrderCreated": False,
            "liveEnabled": False,
            "withdrawEnabled": False,
            "credentialRead": False,
        },
        "unresolvedImplementationBlockers": [],
    }
    test_summary = {
        "schemaVersion": "v46_provisional_demo_patch_test_summary_v1",
        "status": "passed",
        "evidence": list(args.test_evidence),
    }
    result = generate_patch_evidence(
        v46_report_dir=v46_report,
        v49_identity_dir=v49,
        component_contract_dir=args.component_contract_dir,
        output_dir=args.output_dir,
        research_instruments=research_instruments,
        public_snapshot_hash=universe["publicSnapshotHash"],
        public_count=universe["publicCount"],
        authenticated_hash=universe["authenticatedHash"],
        authenticated_count=universe["authenticatedCount"],
        authenticated_exact_list_retained=universe[
            "authenticatedExactListRetained"
        ],
        runtime_snapshot_hash=universe["runtimeSnapshotHash"],
        runtime_instruments=universe["runtimeInstruments"],
        v46_evidence_zip_sha256=zip_sha,
        v46_evidence_verification=verification,
        replay_implementation_path="alphapilot/portfolio_rescue/replay.py",
        replay_implementation_sha256=sha256_file(replay_source),
        replay_parity_percent=float(replay_audit["parityPercent"]),
        replay_parity_audit=replay_audit,
        generated_at=generated_at,
        implementation_receipt=implementation_receipt,
        test_summary=test_summary,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
