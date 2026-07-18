"""Funding evidence registry that never fabricates actual observations."""

from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

from alphapilot.evolution.registry.hashing import stable_hash


FUNDING_UNAVAILABLE_ROUTE = "walk_forward_research_pass_funding_unavailable"


def build_funding_input_registry(
    *,
    instrument_id: str,
    actual_rates: Sequence[Mapping[str, Any]],
    stress_rate: float | None,
) -> dict[str, Any]:
    normalized = [
        {"timestamp": str(row.get("timestamp") or ""), "rate": float(row["rate"])}
        for row in actual_rates
        if row.get("timestamp")
        and row.get("rate") is not None
        and math.isfinite(float(row["rate"]))
    ]
    if normalized:
        status = "actual"
        rates = normalized
        provenance = "instrument_specific_actual_history"
    elif stress_rate is not None and math.isfinite(float(stress_rate)):
        status = "stress"
        rates = [{"stressRate": float(stress_rate)}]
        provenance = "preregistered_stress_only"
    else:
        status = "unavailable"
        rates = []
        provenance = "unavailable_no_substitution"
    registry = {
        "schemaVersion": "funding_input_registry_v1",
        "instrumentId": str(instrument_id),
        "fundingStatus": status,
        "rates": rates,
        "provenance": provenance,
        "crossExchangeSubstitution": False,
        "zeroFillUsed": False,
    }
    registry["fundingInputHash"] = stable_hash(registry, prefix="funding_input")
    return registry


def cap_route_for_funding(route: str, registry: Mapping[str, Any]) -> str:
    normalized = str(route)
    if (
        registry.get("fundingStatus") == "unavailable"
        and normalized.startswith("walk_forward_research_pass_")
    ):
        return FUNDING_UNAVAILABLE_ROUTE
    return normalized
