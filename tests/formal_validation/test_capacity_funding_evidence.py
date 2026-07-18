from __future__ import annotations

from alphapilot.formal_validation.capacity_data_semantics import (
    audit_capacity_semantics,
    resolve_quote_turnover,
)
from alphapilot.formal_validation.funding_input_registry import (
    build_funding_input_registry,
    cap_route_for_funding,
)


def test_quote_base_contract_and_unknown_capacity_semantics() -> None:
    assert resolve_quote_turnover(volume=10.0, close=100.0, unit="quote_asset") == 10.0
    assert resolve_quote_turnover(volume=10.0, close=100.0, unit="base_asset") == 1000.0
    assert resolve_quote_turnover(
        volume=10.0, close=100.0, unit="contracts", contract_size=0.01
    ) == 10.0
    assert resolve_quote_turnover(volume=10.0, close=100.0, unit="unknown") is None

    audit = audit_capacity_semantics(
        [
            {"instrumentId": "BTC", "volumeUnit": "quote_asset", "volumeField": "volume"},
            {"instrumentId": "ETH", "volumeUnit": "unknown", "volumeField": "volume"},
        ],
        core_instruments=["BTC", "ETH"],
    )
    assert audit["implementationComplete"] is True
    assert audit["dataAvailableBySymbol"] == {"BTC": True, "ETH": False}


def test_funding_registry_never_fabricates_zero_and_caps_route() -> None:
    actual = build_funding_input_registry(
        instrument_id="BTC-USDT-SWAP",
        actual_rates=[{"timestamp": "2026-01-01T00:00:00Z", "rate": 0.0001}],
        stress_rate=None,
    )
    stress = build_funding_input_registry(
        instrument_id="ETH-USDT-SWAP", actual_rates=[], stress_rate=0.0003
    )
    unavailable = build_funding_input_registry(
        instrument_id="SOL-USDT-SWAP", actual_rates=[], stress_rate=None
    )

    assert actual["fundingStatus"] == "actual"
    assert stress["fundingStatus"] == "stress"
    assert unavailable["fundingStatus"] == "unavailable"
    assert unavailable["rates"] == []
    assert cap_route_for_funding("archive_s01_current_version", unavailable) == (
        "archive_s01_current_version"
    )
    assert cap_route_for_funding(
        "walk_forward_research_pass_no_clean_holdout", unavailable
    ) == "walk_forward_research_pass_funding_unavailable"
