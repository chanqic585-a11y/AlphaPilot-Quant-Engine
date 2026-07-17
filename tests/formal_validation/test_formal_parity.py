from __future__ import annotations

from copy import deepcopy

from alphapilot.formal_validation.formal_parity import (
    canonicalize_formal_event,
    summarize_formal_parity,
)


def _event() -> dict[str, object]:
    return {
        "candidateId": "s01_bear_idiosyncratic_selloff_recovery_4h",
        "symbol": "ETH-USDT-SWAP",
        "direction": "long",
        "signalTimestamp": "2025-01-01T00:00:00+00:00",
        "entryTimestamp": "2025-01-01T04:00:00+00:00",
        "entryPrice": 100.0,
        "initialStopPrice": 96.8,
        "exitPolicyHash": "sha256:exit",
        "legs": [
            {
                "fraction": 1.0,
                "reason": "maximum_hold",
                "triggerTimestamp": "2025-01-05T00:00:00+00:00",
                "executionTimestamp": "2025-01-05T04:00:00+00:00",
                "price": 103.0,
                "grossR": 0.9375,
                "feesR": 0.01,
                "slippageR": 0.005,
                "spreadProxyR": 0.005,
                "fundingR": 0.0,
                "netR": 0.9175,
                "isGapFill": False,
                "ambiguousPath": False,
            }
        ],
    }


def test_canonicalize_formal_event_uses_stable_real_input_identity() -> None:
    event = canonicalize_formal_event(_event())

    assert event["signalId"] == (
        "s01_formal::ETH-USDT-SWAP::2025-01-01T00:00:00+00:00"
    )
    assert event["initialStop"] == 96.8
    assert event["exitLegCount"] == 1
    assert event["exitLegs"][0]["exitReason"] == "maximum_hold"


def test_formal_parity_requires_actual_freqtrade_runtime_when_requested() -> None:
    reference = canonicalize_formal_event(_event())
    adapter = deepcopy(reference)

    report = summarize_formal_parity(
        [reference],
        [adapter],
        adapter_runtime_base="local_fallback.IStrategy",
        require_freqtrade_runtime=True,
    )

    assert report["status"] == "blocked"
    assert report["passed"] is False
    assert report["identityParityPct"] == 100.0
    assert report["exitLegParityPct"] == 100.0
    assert "freqtrade_runtime_not_loaded" in report["blockers"]


def test_formal_parity_accepts_exact_events_inside_freqtrade_runtime() -> None:
    reference = canonicalize_formal_event(_event())

    report = summarize_formal_parity(
        [reference],
        [deepcopy(reference)],
        adapter_runtime_base="freqtrade.strategy.interface",
        require_freqtrade_runtime=True,
    )

    assert report["status"] == "passed"
    assert report["passed"] is True
    assert report["fullFormalInput"] is True
    assert report["syntheticFixtureOnly"] is False
    assert report["lockedOosAccessCount"] == 0
    assert report["releaseCount"] == 0
    assert report["orderCount"] == 0
