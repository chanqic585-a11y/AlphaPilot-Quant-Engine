"""V41 dual-track successor identity and isolated evidence ledgers."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Iterable, Mapping

from alphapilot.data_foundation.checkpoint import write_json_atomic
from alphapilot.evolution.registry.hashing import stable_hash

from .contracts import MechanismBreakthroughBudget


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n")


def write_successor_program_evidence(
    *,
    output_root: str | Path,
    frozen_at: str,
    quant_merge_commit: str,
    console_merge_commit: str,
    docs_merge_commit: str,
    inherited_full_backtests: int,
    demo_credentials_injected: bool,
) -> dict[str, Any]:
    root = Path(output_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    budget = MechanismBreakthroughBudget.default(
        inherited_full_backtests=inherited_full_backtests
    )
    merge_commits = {
        "quant": quant_merge_commit,
        "console": console_merge_commit,
        "docs": docs_merge_commit,
    }
    merge_receipt = {
        "schemaVersion": "alphapilot_v41_integration_merge_receipt_v1",
        "frozenAt": frozen_at,
        "mergeCommits": merge_commits,
        "mergeStrategy": "merge_no_rebase_no_force_push",
        "historicalArtifactMutationCount": 0,
        "historicalTagMutationCount": 0,
    }
    merge_receipt["receiptHash"] = stable_hash(merge_receipt, prefix="integration_merge")
    write_json_atomic(root / "integration_merge_receipt.json", merge_receipt)

    program_core = {
        "schemaVersion": "alphapilot_v41_v45_successor_program_v1",
        "frozenAt": frozen_at,
        "baselineMergeReceiptHash": merge_receipt["receiptHash"],
        "budgetPolicyHash": budget.policy_hash,
        "tracks": {
            "research": {
                "classification": "strategy_research",
                "ledger": "research_evidence_ledger.jsonl",
                "formalEligibility": True,
            },
            "product": {
                "classification": "engineering_only",
                "ledger": "product_engineering_ledger.jsonl",
                "formalEligibility": False,
            },
        },
        "trackIsolation": {
            "engineeringSmokeQualifiesStrategy": False,
            "engineeringOrdersCountAsStrategyEvidence": False,
            "sharedCredentials": False,
            "sharedLedgers": False,
        },
        "targetRGateMode": "advisory",
        "minimumTargetR": None,
        "liveEnabled": False,
        "withdrawEnabled": False,
        "credentialsPersisted": False,
    }
    program_id = stable_hash(program_core, prefix="mechanism_breakthrough_and_demo_smoke_v41")
    program_spec = {**program_core, "programId": program_id}
    write_json_atomic(root / "program_spec.json", program_spec)
    write_json_atomic(
        root / "program_budget.json",
        {
            "schemaVersion": "alphapilot_v41_v45_program_budget_v1",
            "programId": program_id,
            "policy": asdict(budget),
            "policyHash": budget.policy_hash,
            "inheritedFullBacktestsRemaining": inherited_full_backtests,
            "budgetReset": False,
        },
    )

    product_status = (
        "ready_for_hash_approved_engineering_smoke"
        if demo_credentials_injected
        else "blocked_demo_credentials_not_injected"
    )
    state = {
        "schemaVersion": "alphapilot_v41_v45_program_state_v1",
        "programId": program_id,
        "researchTrackStatus": "ready",
        "productTrackStatus": product_status,
        "demoCredentialsInjected": demo_credentials_injected,
        "demoCredentialsPersisted": False,
        "formalRunCount": 0,
        "releaseCount": 0,
        "strategyOrderCount": 0,
        "engineeringOrderCount": 0,
        "liveEnabled": False,
        "withdrawEnabled": False,
    }
    write_json_atomic(root / "program_state.json", state)
    program_event = {
        "sequence": 1,
        "event": "successor_program_frozen",
        "programId": program_id,
        "frozenAt": frozen_at,
        "previousEventHash": None,
    }
    program_event["eventHash"] = stable_hash(program_event, prefix="program_event")
    _write_jsonl(root / "program_ledger.jsonl", [program_event])
    _write_jsonl(
        root / "research_evidence_ledger.jsonl",
        [
            {
                "sequence": 1,
                "event": "research_track_ready",
                "programId": program_id,
                "formalClaim": False,
                "lockedOosReadCount": 0,
            }
        ],
    )
    _write_jsonl(
        root / "product_engineering_ledger.jsonl",
        [
            {
                "sequence": 1,
                "event": product_status,
                "programId": program_id,
                "strategyEvidenceDelta": 0,
                "credentialsPersisted": False,
            }
        ],
    )
    _write_jsonl(
        root / "program_budget_ledger.jsonl",
        [
            {
                "sequence": 1,
                "event": "inherited_budget_registered",
                "programId": program_id,
                "fullBacktestsRemaining": inherited_full_backtests,
                "budgetReset": False,
            }
        ],
    )
    return state

