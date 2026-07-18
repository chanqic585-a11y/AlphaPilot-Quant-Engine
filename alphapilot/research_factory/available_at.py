"""Causal availability rules for research fields."""

from __future__ import annotations

from typing import Any


_CANDLE_FIELDS = {
    "open",
    "high",
    "low",
    "close",
    "reported_volume",
    "base_volume",
    "quote_volume",
    "contract_volume",
    "quote_turnover",
    "vwap",
    "btc_returns",
    "residual_beta_inputs",
    "spot_price",
    "perpetual_price",
}


def available_at_rule(field: str) -> dict[str, Any]:
    name = str(field).strip().lower()
    if name in _CANDLE_FIELDS:
        return {
            "rule": "candle_close_timestamp",
            "causal": True,
            "historicalStatus": "available_if_source_field_is_ready",
        }
    if name == "funding_rate":
        return {
            "rule": "source_timestamp_plus_publication_delay",
            "causal": True,
            "historicalStatus": "available_if_publication_timestamp_is_frozen",
        }
    if name in {"instrument_state", "pit_universe"}:
        return {
            "rule": "effective_timestamp_of_frozen_snapshot",
            "causal": True,
            "historicalStatus": "diagnostic_proxy_without_complete_listing_history",
        }
    if name in {"open_interest", "basis", "liquidation", "orderbook"}:
        return {
            "rule": "unavailable_without_frozen_publication_timestamp",
            "causal": True,
            "historicalStatus": "unavailable",
        }
    raise KeyError(f"unknown research field: {field}")
