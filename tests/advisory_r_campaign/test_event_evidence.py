from __future__ import annotations

from copy import deepcopy

import pytest

from alphapilot.advisory_r_campaign.event_evidence import (
    EVENT_SCHEMA_FIELDS,
    build_event_evidence,
    verify_event_parity,
)


def _raw_event() -> dict:
    return {
        "candidateId": "candidate-1",
        "symbol": "BTC-USDT-SWAP",
        "side": "long",
        "signalTimestamp": "2026-01-01T00:00:00+00:00",
        "entryTimestamp": "2026-01-01T01:00:00+00:00",
        "entryPrice": 100.0,
        "initialStopPrice": 98.0,
        "riskDistance": 2.0,
        "exitPolicyMode": "partial_then_trailing",
        "exitPolicyHash": "exit-policy-hash",
        "legs": [
            {
                "fraction": 0.4,
                "reason": "partial",
                "triggerTimestamp": "2026-01-01T02:00:00+00:00",
                "executionTimestamp": "2026-01-01T03:00:00+00:00",
                "grossR": 0.8,
                "feesR": 0.01,
                "slippageR": 0.01,
                "spreadProxyR": 0.01,
                "fundingR": 0.0,
                "netR": 0.77,
                "price": 101.6,
            },
            {
                "fraction": 0.6,
                "reason": "trailing",
                "triggerTimestamp": "2026-01-01T04:00:00+00:00",
                "executionTimestamp": "2026-01-01T05:00:00+00:00",
                "grossR": 1.2,
                "feesR": 0.01,
                "slippageR": 0.01,
                "spreadProxyR": 0.01,
                "fundingR": 0.0,
                "netR": 1.17,
                "price": 102.4,
            },
        ],
        "grossR": 1.04,
        "feesR": 0.02,
        "slippageR": 0.02,
        "spreadProxyR": 0.02,
        "fundingR": 0.0,
        "netR": 0.98,
        "mfeR": 1.4,
        "maeR": -0.3,
    }


def test_event_evidence_has_complete_schema_and_unknown_funding_is_null() -> None:
    raw = _raw_event()
    event = build_event_evidence(
        raw,
        trial_id="trial-1",
        correction_campaign_id="campaign-1",
        implementation_conformance_hash="conformance-1",
        source_data_hash="source-1",
        market_regime="development_prefilter",
    )

    assert set(EVENT_SCHEMA_FIELDS).issubset(event)
    assert event["exitLegCount"] == 2
    assert event["fundingR"] is None
    assert all(leg["fundingR"] is None for leg in event["exitLegs"])
    assert event["signalId"].startswith("advisory_r_signal_")
    assert event["month"] == "2026-01"


def test_event_parity_fails_closed_on_changed_exit_leg() -> None:
    raw = _raw_event()
    event = build_event_evidence(
        raw,
        trial_id="trial-1",
        correction_campaign_id="campaign-1",
        implementation_conformance_hash="conformance-1",
        source_data_hash="source-1",
        market_regime="development_prefilter",
    )
    changed = deepcopy(event)
    changed["exitLegs"][0]["fraction"] = 0.5

    with pytest.raises(RuntimeError, match="event parity"):
        verify_event_parity([raw], [changed])


def test_portfolio_event_expands_long_and_short_market_legs() -> None:
    raw = _raw_event()
    raw.update(
        {
            "symbol": "PORTFOLIO",
            "longSymbols": ["ETH-USDT-SWAP", "SOL-USDT-SWAP"],
            "shortSymbols": ["BTC-USDT-SWAP"],
        }
    )
    event = build_event_evidence(
        raw,
        trial_id="trial-1",
        correction_campaign_id="campaign-1",
        implementation_conformance_hash="conformance-1",
        source_data_hash="source-1",
        market_regime="development_prefilter",
    )

    assert event["direction"] == "cross_sectional_long_short"
    assert event["legs"] == [
        {"symbol": "ETH-USDT-SWAP", "direction": "long", "weight": 0.25},
        {"symbol": "SOL-USDT-SWAP", "direction": "long", "weight": 0.25},
        {"symbol": "BTC-USDT-SWAP", "direction": "short", "weight": 0.5},
    ]
    assert verify_event_parity([raw], [event])["passed"] is True
