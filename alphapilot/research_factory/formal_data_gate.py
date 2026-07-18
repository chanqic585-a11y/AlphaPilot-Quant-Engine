"""Fail-closed data gate evaluated before a one-shot formal claim."""

from __future__ import annotations

from typing import Any

from alphapilot.evolution.registry.hashing import stable_hash


def evaluate_formal_data_gate(
    *,
    all_formal_required_fields_semantically_verified: bool,
    formal_data_profile_status: str,
    formal_event_capacity_input_coverage: float,
    minimum_capacity_input_coverage: float,
) -> dict[str, Any]:
    checks = {
        "allFormalRequiredFieldsSemanticallyVerified": bool(
            all_formal_required_fields_semantically_verified
        ),
        "formalDataProfileReady": str(formal_data_profile_status) == "ready",
        "formalEventCapacityInputCoverage": float(
            formal_event_capacity_input_coverage
        )
        >= float(minimum_capacity_input_coverage),
    }
    failed = [name for name, passed in checks.items() if not passed]
    permitted = not failed
    payload: dict[str, Any] = {
        "schemaVersion": "formal_data_gate_v1",
        "status": "ready_for_formal_claim"
        if permitted
        else "formal_data_blocked_before_claim",
        "claimPermitted": permitted,
        "checks": checks,
        "failedConditions": failed,
        "formalDataProfileStatus": str(formal_data_profile_status),
        "formalEventCapacityInputCoverage": float(
            formal_event_capacity_input_coverage
        ),
        "minimumCapacityInputCoverage": float(minimum_capacity_input_coverage),
        "formalRunBudgetConsumed": 0,
        "ledgerDelta": {
            "claimCount": 0,
            "attemptCount": 0,
            "resultCount": 0,
            "resultReadCount": 0,
        },
        "blockedAction": None
        if permitted
        else "repair_data_semantics_without_reading_formal_results",
    }
    payload["gateHash"] = stable_hash(payload, prefix="formal_data_gate")
    return payload
