"""Formal provenance eligibility for the three preregistered directions."""

from __future__ import annotations

from typing import Any, Mapping


def _same_exchange_fields(
    evidence: Mapping[str, Any], required: tuple[str, ...]
) -> tuple[list[str], set[str]]:
    missing: list[str] = []
    exchanges: set[str] = set()
    for field in required:
        row = evidence.get(field)
        if not isinstance(row, Mapping):
            missing.append(field)
            continue
        exchange = str(row.get("exchange") or "")
        provenance = str(row.get("provenanceHash") or "")
        if not exchange or not provenance:
            missing.append(field)
            continue
        exchanges.add(exchange)
    return missing, exchanges


def evaluate_formal_data_gate(
    *,
    direction: str,
    evidence: Mapping[str, Any],
) -> dict[str, Any]:
    normalized = direction.upper()
    missing: list[str] = []
    maximum_outcome = "formal_pass"
    exchange: str | None = None

    if normalized in {"A", "A1"}:
        required = ("perpetualPrice", "funding", "openInterest", "realLiquidation")
        missing, exchanges = _same_exchange_fields(evidence, required)
        if len(exchanges) > 1:
            missing.append("sameExchangeCoreFields")
        elif exchanges:
            exchange = next(iter(exchanges))
    elif normalized == "A2":
        missing.append("realLiquidation")
        maximum_outcome = "provisional_research_pass"
    elif normalized == "B":
        required = ("funding", "openInterest", "perpetualPrice", "spotPrice", "basis")
        missing, exchanges = _same_exchange_fields(evidence, required)
        if len(exchanges) > 1:
            missing.append("sameExchangeCoreFields")
        elif exchanges:
            exchange = next(iter(exchanges))
    elif normalized == "C":
        required_flags = (
            "pitTradability",
            "pitLiquidity",
            "listingDelisting",
            "historicalContractUniverse",
        )
        missing.extend(field for field in required_flags if evidence.get(field) is not True)
        if evidence.get("currentTopNBackfill") is True:
            missing.append("pointInTimeUniverseWithoutBackfill")
            maximum_outcome = "provisional_research_pass"
    else:
        raise ValueError(f"unknown preregistered direction: {direction}")

    passed = not missing and maximum_outcome == "formal_pass"
    return {
        "schemaVersion": "formal_data_gate_v2",
        "direction": normalized,
        "formalDataProvenancePassed": passed,
        "maximumOutcome": maximum_outcome if not passed else "formal_pass",
        "sameExchange": exchange,
        "missingEvidence": sorted(set(missing)),
    }
