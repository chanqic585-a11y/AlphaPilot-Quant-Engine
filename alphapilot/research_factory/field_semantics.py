"""Conservative field semantics used before hypothesis generation."""

from __future__ import annotations

from typing import Any

from alphapilot.research_factory.available_at import available_at_rule


def build_field_semantics_registry() -> dict[str, dict[str, Any]]:
    semantics: dict[str, dict[str, Any]] = {
        "open": {"unit": "quote_currency_per_base_currency", "status": "source_reported"},
        "high": {"unit": "quote_currency_per_base_currency", "status": "source_reported"},
        "low": {"unit": "quote_currency_per_base_currency", "status": "source_reported"},
        "close": {"unit": "quote_currency_per_base_currency", "status": "source_reported"},
        "reported_volume": {
            "unit": "source_reported_unknown",
            "status": "ready_proxy_semantics_unverified",
        },
        "base_volume": {"unit": "base_currency", "status": "unavailable_without_verified_semantics"},
        "quote_volume": {"unit": "quote_currency", "status": "unavailable_without_verified_semantics"},
        "contract_volume": {"unit": "contracts", "status": "unavailable_without_verified_semantics"},
        "quote_turnover": {"unit": "quote_currency", "status": "unavailable_without_verified_semantics"},
        "vwap": {"unit": "quote_currency_per_base_currency", "status": "unavailable_without_verified_turnover"},
        "btc_returns": {"unit": "decimal_return", "status": "derived_from_btc_close"},
        "residual_beta_inputs": {"unit": "decimal_return", "status": "derived_from_synchronized_closes"},
        "funding_rate": {"unit": "decimal_rate", "status": "public_source_reported"},
        "open_interest": {"unit": "unavailable", "status": "unavailable"},
        "basis": {"unit": "decimal_return", "status": "unavailable"},
        "spot_price": {"unit": "quote_currency_per_base_currency", "status": "available_not_selected"},
        "perpetual_price": {"unit": "quote_currency_per_base_currency", "status": "ready_proxy"},
        "liquidation": {"unit": "unavailable", "status": "unavailable"},
        "orderbook": {"unit": "unavailable", "status": "unavailable"},
        "instrument_state": {"unit": "state", "status": "diagnostic_proxy"},
        "pit_universe": {"unit": "membership", "status": "diagnostic_proxy"},
    }
    for field, payload in semantics.items():
        rule = available_at_rule(field)
        payload["availableAtRule"] = rule["rule"]
        payload["causal"] = rule["causal"]
    return semantics
