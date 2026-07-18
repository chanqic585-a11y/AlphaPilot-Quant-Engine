"""Explicit turnover-unit semantics for formal capacity evidence."""

from __future__ import annotations

import math
from typing import Any, Mapping, Sequence


SUPPORTED_VOLUME_UNITS = {"quote_asset", "base_asset", "contracts"}


def resolve_quote_turnover(
    *, volume: float, close: float, unit: str, contract_size: float | None = None
) -> float | None:
    values = (float(volume), float(close))
    if not all(math.isfinite(value) and value >= 0 for value in values):
        return None
    if unit == "quote_asset":
        return values[0]
    if unit == "base_asset":
        return values[0] * values[1]
    if unit == "contracts":
        if contract_size is None or not math.isfinite(float(contract_size)):
            return None
        return values[0] * float(contract_size) * values[1]
    return None


def audit_capacity_semantics(
    rows: Sequence[Mapping[str, Any]], *, core_instruments: Sequence[str]
) -> dict[str, Any]:
    by_instrument = {
        str(row.get("instrumentId")): str(row.get("volumeUnit") or "unknown")
        for row in rows
    }
    availability = {
        instrument: by_instrument.get(instrument) in SUPPORTED_VOLUME_UNITS
        for instrument in core_instruments
    }
    return {
        "schemaVersion": "capacity_data_semantics_audit_v1",
        "implementationComplete": True,
        "dataAvailableBySymbol": availability,
        "unknownUnitInstruments": sorted(
            instrument for instrument, available in availability.items() if not available
        ),
        "unknownUnitAction": "reject_capacity_evidence_unavailable",
    }
