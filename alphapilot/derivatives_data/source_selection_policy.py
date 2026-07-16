"""Fail-closed same-exchange source-chain selection."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any


def _eligible(row: dict[str, Any]) -> bool:
    return bool(row.get("formalHistoricalEligible")) and (
        row.get("historicalCompleteness") == "verified_complete"
        and row.get("probeStatus") == "passed"
        and bool(row.get("licenseOrUsageTerms"))
    )


def select_formal_source_chain(
    capabilities: Iterable[dict[str, Any]],
    *,
    required_data_types: Sequence[str],
    preferred_exchange: str,
) -> dict[str, Any]:
    required = list(dict.fromkeys(required_data_types))
    rows = [dict(row) for row in capabilities]
    exchanges = sorted({str(row.get("exchange")) for row in rows if row.get("exchange")})
    ordered = ([preferred_exchange] if preferred_exchange in exchanges else []) + [
        exchange for exchange in exchanges if exchange != preferred_exchange
    ]
    coverage: dict[str, list[str]] = {}
    for exchange in ordered:
        available = {
            str(row.get("dataType"))
            for row in rows
            if row.get("exchange") == exchange and _eligible(row)
        }
        coverage[exchange] = sorted(available & set(required))
        if set(required) <= available:
            return {
                "formalEligible": True,
                "selectedExchange": exchange,
                "requiredDataTypes": required,
                "availableDataTypes": coverage[exchange],
                "missingDataTypes": [],
                "crossExchangeSplicingUsed": False,
                "reason": "complete_formal_chain_on_single_exchange",
                "coverageByExchange": coverage,
            }
    best = max(ordered, key=lambda exchange: len(coverage[exchange]), default=None)
    available = coverage.get(best, []) if best else []
    return {
        "formalEligible": False,
        "selectedExchange": None,
        "requiredDataTypes": required,
        "availableDataTypes": available,
        "missingDataTypes": [item for item in required if item not in available],
        "crossExchangeSplicingUsed": False,
        "reason": "no_single_exchange_has_complete_formal_chain",
        "coverageByExchange": coverage,
    }
