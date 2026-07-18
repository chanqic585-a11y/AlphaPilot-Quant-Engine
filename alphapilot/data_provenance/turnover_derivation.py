"""Conservative quote-turnover derivations with explicit evidence types."""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any


def _number(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and number >= 0.0 else None


def _unavailable(reason: str) -> dict[str, Any]:
    return {
        "status": "capacity_semantics_unavailable",
        "value": None,
        "evidenceType": None,
        "isExact": False,
        "formula": None,
        "reason": reason,
    }

def derive_quote_turnover(
    *,
    volume: float,
    low: float,
    close: float,
    semantic_type: str,
    contract_metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    parsed_volume = _number(volume)
    parsed_low = _number(low)
    parsed_close = _number(close)
    if parsed_volume is None or parsed_low is None or parsed_close is None:
        return _unavailable("nonfinite_or_negative_input")

    if semantic_type == "exact_quote_turnover":
        return {
            "status": "ready",
            "value": parsed_volume,
            "evidenceType": "exact_quote_turnover",
            "isExact": True,
            "formula": "quote_turnover_source_field",
            "reason": None,
        }
    if semantic_type == "verified_base_volume":
        return {
            "status": "ready",
            "value": parsed_low * parsed_volume,
            "evidenceType": "conservative_quote_turnover_lower_bound",
            "isExact": False,
            "formula": "candle_low * base_volume",
            "reason": None,
        }
    if semantic_type != "verified_contract_volume":
        return _unavailable("unsupported_volume_semantic_type")

    metadata = dict(contract_metadata or {})
    required = {
        "contractSize",
        "contractValueCurrency",
        "quoteCurrency",
        "contractType",
        "priceConversionRule",
        "metadataVersion",
    }
    if required - set(metadata):
        return _unavailable("incomplete_contract_metadata")
    size = _number(metadata.get("contractSize"))
    if size is None or size <= 0.0:
        return _unavailable("invalid_contract_size")
    rule = str(metadata.get("priceConversionRule"))
    if rule == "contracts * contract_size * price":
        value = parsed_volume * size * parsed_close
    elif rule == "contracts * contract_size":
        value = parsed_volume * size
    else:
        return _unavailable("unsupported_contract_price_conversion_rule")
    return {
        "status": "ready",
        "value": value,
        "evidenceType": "verified_contract_quote_turnover",
        "isExact": True,
        "formula": rule,
        "reason": None,
    }
