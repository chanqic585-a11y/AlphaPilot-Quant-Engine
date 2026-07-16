"""Honest forward-only collection plan for unavailable derivatives fields."""

from __future__ import annotations

from typing import Any, Iterable

from alphapilot.evolution.registry.hashing import stable_hash


_REQUIRED_DATA_TYPES = (
    "OHLCV",
    "Open Interest",
    "Funding",
    "Basis",
    "Liquidation",
    "Spread",
    "Instrument State",
    "PIT Liquidity",
)


def build_forward_collection_plan(
    *, available_data_types: Iterable[str], start_at: str
) -> dict[str, Any]:
    available = set(available_data_types)
    rows: dict[str, dict[str, Any]] = {}
    for data_type in _REQUIRED_DATA_TYPES:
        is_available = data_type in available
        rows[data_type] = {
            "status": "available_existing" if is_available else "forward_only_missing_history",
            "historicalValue": "retained_existing" if is_available else None,
            "appendOnly": not is_available,
            "startAt": start_at if not is_available else None,
        }
    core = {
        "schemaVersion": "minimal_forward_collection_plan_v1",
        "forwardDataCannotBackfillHistory": True,
        "dataTypes": rows,
        "credentialRequirement": "public_data_only",
        "tradeApiEnabled": False,
        "withdrawApiEnabled": False,
    }
    return {**core, "planHash": stable_hash(core, prefix="forward_collection_plan")}
