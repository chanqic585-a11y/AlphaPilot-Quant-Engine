"""Frozen point-in-time portfolio context used before ranking and admission."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from alphapilot.evolution.registry.hashing import stable_hash


PIT_FIELDS = (
    "contextTimestamp",
    "currentEquity",
    "openPositions",
    "openRiskR",
    "sameDirectionRiskR",
    "clusterRiskByCluster",
    "portfolioBeta",
    "concurrentPositionCount",
    "symbolAlreadyOpen",
    "clusterMembership",
    "assetBeta",
    "capacityInputs",
)
RESULT_FIELDS = {"realizedPnl", "finalReturn", "exitReason", "result"}


def freeze_pit_portfolio_context(
    *, signal_id: str, state: Mapping[str, Any], formal_policy_hash: str
) -> dict[str, Any]:
    missing = [field for field in PIT_FIELDS if field not in state]
    if missing:
        raise ValueError(f"pit_context_field_unavailable:{','.join(missing)}")
    if RESULT_FIELDS & set(state):
        raise ValueError("pit_context_contains_result_fields")
    context = {
        "signalId": str(signal_id),
        **{field: state[field] for field in PIT_FIELDS},
        "formalPolicyHash": str(formal_policy_hash),
    }
    context["pitContextHash"] = stable_hash(context, prefix="pit_portfolio_context")
    return context


def audit_pit_context_parity(
    core_rows: Sequence[Mapping[str, Any]], adapter_rows: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    core = {str(row.get("signalId")): dict(row) for row in core_rows}
    adapter = {str(row.get("signalId")): dict(row) for row in adapter_rows}
    shared = sorted(set(core) & set(adapter))
    fields = (*PIT_FIELDS, "formalPolicyHash")
    total = len(shared) * len(fields)
    matches = sum(
        core[key].get(field) == adapter[key].get(field)
        for key in shared
        for field in fields
    )
    hash_matches = sum(
        core[key].get("pitContextHash") == adapter[key].get("pitContextHash")
        for key in shared
    )
    return {
        "schemaVersion": "pit_portfolio_context_parity_v1",
        "fieldParityPct": round(100.0 * matches / total, 6) if total else 100.0,
        "hashParityPct": round(100.0 * hash_matches / len(shared), 6)
        if shared
        else 100.0,
        "resultReconstructionCount": sum(
            bool(RESULT_FIELDS & set(row)) for row in [*core_rows, *adapter_rows]
        ),
        "unmappedCount": len(set(core) ^ set(adapter)),
    }
