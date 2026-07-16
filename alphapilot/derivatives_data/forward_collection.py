"""Pre-register append-only public derivatives collection for future evidence."""

from __future__ import annotations

from typing import Any


FORWARD_STREAMS = (
    "open_interest",
    "funding",
    "spot_ohlcv",
    "perpetual_ohlcv",
    "basis",
    "instrument_state",
    "pit_liquidity",
    "spread",
    "liquidation",
)


def build_forward_collection_plan(
    capabilities: dict[str, bool],
    budget: dict[str, int | float],
) -> dict[str, Any]:
    streams = [
        {
            "dataType": data_type,
            "status": "ready_to_collect" if capabilities.get(data_type) else "unavailable",
            "appendOnly": True,
            "strictAvailabilityClockRequired": True,
        }
        for data_type in FORWARD_STREAMS
    ]
    return {
        "schemaVersion": "v13_27_1_12_forward_collection_plan_v1",
        "status": "planned",
        "appendOnly": True,
        "resumable": True,
        "auditable": True,
        "publicDataOnly": True,
        "accountAccess": False,
        "orderCreation": False,
        "historicalFormalReady": False,
        "futureCollectionReady": any(row["status"] == "ready_to_collect" for row in streams),
        "budgets": dict(budget),
        "streams": streams,
        "warning": "future collection cannot substitute for historical formal evidence",
    }
