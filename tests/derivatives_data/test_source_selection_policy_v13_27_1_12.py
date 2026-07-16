from __future__ import annotations

from alphapilot.derivatives_data.source_selection_policy import select_formal_source_chain


def _capability(exchange: str, data_type: str, *, eligible: bool = True) -> dict[str, object]:
    return {
        "exchange": exchange,
        "dataType": data_type,
        "formalHistoricalEligible": eligible,
        "historicalCompleteness": "verified_complete" if eligible else "insufficient",
        "licenseOrUsageTerms": "documented_public_terms",
        "probeStatus": "passed",
    }


def test_source_policy_selects_preferred_complete_same_exchange_chain() -> None:
    required = ["perpetual_ohlcv", "funding", "open_interest", "spot_ohlcv", "basis"]
    capabilities = [_capability("OKX", data_type) for data_type in required]
    capabilities += [_capability("Binance", data_type) for data_type in required]

    decision = select_formal_source_chain(
        capabilities,
        required_data_types=required,
        preferred_exchange="OKX",
    )

    assert decision["formalEligible"] is True
    assert decision["selectedExchange"] == "OKX"
    assert decision["crossExchangeSplicingUsed"] is False
    assert decision["missingDataTypes"] == []


def test_source_policy_rejects_cross_exchange_splicing() -> None:
    capabilities = [
        _capability("OKX", "perpetual_ohlcv"),
        _capability("OKX", "funding"),
        _capability("Binance", "open_interest"),
        _capability("Binance", "spot_ohlcv"),
        _capability("Binance", "basis"),
    ]

    decision = select_formal_source_chain(
        capabilities,
        required_data_types=[
            "perpetual_ohlcv",
            "funding",
            "open_interest",
            "spot_ohlcv",
            "basis",
        ],
        preferred_exchange="OKX",
    )

    assert decision["formalEligible"] is False
    assert decision["selectedExchange"] is None
    assert decision["crossExchangeSplicingUsed"] is False
    assert decision["reason"] == "no_single_exchange_has_complete_formal_chain"
