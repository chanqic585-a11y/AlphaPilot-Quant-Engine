from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pandas as pd
import pytest

from alphapilot.advisory_r_campaign.candidates import build_candidate_inventory
from alphapilot.evolution.registry.hashing import stable_hash
from alphapilot.formal_validation.candidate_adapters.s01 import S01CandidateAdapter
from alphapilot.formal_validation.formal_input import FormalInputBundle
from alphapilot.formal_validation.formal_parity import (
    canonicalize_formal_event,
    summarize_formal_parity,
)
from alphapilot.formal_validation.s01_dual_engine_audit import (
    build_s01_synthetic_fixture,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


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


def _real_signal_bundle() -> FormalInputBundle:
    frames = build_s01_synthetic_fixture()
    candidate = next(
        dict(row)
        for row in build_candidate_inventory()
        if row["candidateId"] == S01CandidateAdapter.CANDIDATE_ID
    )
    common_index = pd.DatetimeIndex(frames["BTC-USDT-SWAP"]["date"])
    return FormalInputBundle(
        preregistration={
            "campaignId": "v18_1_real_signal_regression",
            "costModel": {"baseRoundTripCostRate": 0.001},
        },
        candidate=candidate,
        snapshot={},
        frames=frames,
        commonIndex=common_index,
        inputMapping={},
        holdoutLineage={},
    )


def _zero_signal_bundle() -> FormalInputBundle:
    bundle = _real_signal_bundle()
    frames: dict[str, pd.DataFrame] = {}
    for instrument_id, raw_frame in bundle.frames.items():
        frame = raw_frame.copy()
        frame["open"] = 100.0
        frame["high"] = 101.0
        frame["low"] = 99.0
        frame["close"] = 100.0
        frames[instrument_id] = frame
    return FormalInputBundle(
        preregistration=dict(bundle.preregistration),
        candidate=dict(bundle.candidate),
        snapshot=dict(bundle.snapshot),
        frames=frames,
        commonIndex=bundle.commonIndex,
        inputMapping=dict(bundle.inputMapping),
        holdoutLineage=dict(bundle.holdoutLineage),
    )


def test_canonicalize_formal_event_uses_stable_real_input_identity() -> None:
    event = canonicalize_formal_event(
        _event(),
        candidate_adapter=S01CandidateAdapter(),
    )

    assert event["signalId"] == (
        "s01_formal::ETH-USDT-SWAP::2025-01-01T00:00:00+00:00"
    )
    assert event["initialStop"] == 96.8
    assert event["exitLegCount"] == 1
    assert event["exitLegs"][0]["exitReason"] == "maximum_hold"


def test_s01_formal_runtime_real_signal_branch_uses_authoritative_identity() -> None:
    report, reference_events, adapter_events = S01CandidateAdapter().run_parity(
        bundle=_real_signal_bundle(),
        repo_root=REPO_ROOT,
    )

    assert report["formalSignalCount"] == 1
    assert report["adapterSignalCount"] == 1
    assert len(reference_events) == len(adapter_events) == 1
    assert reference_events[0]["signalId"] == adapter_events[0]["signalId"]
    assert reference_events[0]["signalId"].startswith("s01_formal::")


def test_s01_formal_runtime_uses_frozen_round_trip_cost() -> None:
    bundle = _real_signal_bundle()
    bundle.preregistration["costModel"]["baseRoundTripCostRate"] = 0.002

    report, reference_events, adapter_events = S01CandidateAdapter().run_parity(
        bundle=bundle,
        repo_root=REPO_ROOT,
    )

    assert report["status"] in {"passed", "blocked"}
    if report["status"] == "blocked":
        assert report["blockers"] == ["freqtrade_runtime_not_loaded"]
    assert report["mismatches"] == []
    assert adapter_events[0]["exitLegs"] == reference_events[0]["exitLegs"]


def test_s01_formal_runtime_zero_signal_branch_does_not_resolve_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected_identity_call(*_: object, **__: object) -> str:
        raise AssertionError("zero-signal parity must not resolve an identity")

    monkeypatch.setattr(
        S01CandidateAdapter,
        "signal_identity",
        unexpected_identity_call,
    )
    report, reference_events, adapter_events = S01CandidateAdapter().run_parity(
        bundle=_zero_signal_bundle(),
        repo_root=REPO_ROOT,
    )

    assert report["formalSignalCount"] == 0
    assert report["adapterSignalCount"] == 0
    assert reference_events == []
    assert adapter_events == []


def test_same_timestamp_multi_symbol_ids_are_unique_and_stably_sorted() -> None:
    adapter = S01CandidateAdapter()
    events = [
        canonicalize_formal_event(
            {**_event(), "symbol": symbol},
            candidate_adapter=adapter,
        )
        for symbol in ("ETH-USDT-SWAP", "BTC-USDT-SWAP", "SOL-USDT-SWAP")
    ]
    signal_ids = [event["signalId"] for event in events]

    assert len(set(signal_ids)) == len(signal_ids)
    assert sorted(signal_ids) == [
        "s01_formal::BTC-USDT-SWAP::2025-01-01T00:00:00+00:00",
        "s01_formal::ETH-USDT-SWAP::2025-01-01T00:00:00+00:00",
        "s01_formal::SOL-USDT-SWAP::2025-01-01T00:00:00+00:00",
    ]


def test_formal_parity_repeat_is_byte_stable() -> None:
    adapter = S01CandidateAdapter()
    reference = canonicalize_formal_event(
        _event(),
        candidate_adapter=adapter,
    )

    first = summarize_formal_parity(
        [reference],
        [deepcopy(reference)],
        adapter_runtime_base="freqtrade.strategy.interface",
        require_freqtrade_runtime=True,
    )
    second = summarize_formal_parity(
        [deepcopy(reference)],
        [deepcopy(reference)],
        adapter_runtime_base="freqtrade.strategy.interface",
        require_freqtrade_runtime=True,
    )

    assert first == second
    assert stable_hash(first, prefix="v18_1_formal_parity_fixture") == stable_hash(
        second,
        prefix="v18_1_formal_parity_fixture",
    )


def test_s01_identity_preserves_historical_field_semantics() -> None:
    adapter = S01CandidateAdapter()
    base = _event()
    original = adapter.signal_identity(
        candidate_id=str(base["candidateId"]),
        symbol=str(base["symbol"]),
        direction=str(base["direction"]),
        signal_timestamp=str(base["signalTimestamp"]),
        expected_entry_timestamp=str(base["entryTimestamp"]),
        signal_context=base,
    )
    non_identity_change = adapter.signal_identity(
        candidate_id=str(base["candidateId"]),
        symbol=str(base["symbol"]),
        direction="short",
        signal_timestamp=str(base["signalTimestamp"]),
        expected_entry_timestamp="2025-01-01T08:00:00+00:00",
        signal_context={**base, "direction": "short"},
    )
    symbol_change = adapter.signal_identity(
        candidate_id=str(base["candidateId"]),
        symbol="BTC-USDT-SWAP",
        direction=str(base["direction"]),
        signal_timestamp=str(base["signalTimestamp"]),
        expected_entry_timestamp=str(base["entryTimestamp"]),
        signal_context=base,
    )
    timestamp_change = adapter.signal_identity(
        candidate_id=str(base["candidateId"]),
        symbol=str(base["symbol"]),
        direction=str(base["direction"]),
        signal_timestamp="2025-01-01T04:00:00+00:00",
        expected_entry_timestamp=str(base["entryTimestamp"]),
        signal_context=base,
    )

    assert original == non_identity_change
    assert original != symbol_change
    assert original != timestamp_change


def test_formal_parity_requires_actual_freqtrade_runtime_when_requested() -> None:
    reference = canonicalize_formal_event(
        _event(),
        candidate_adapter=S01CandidateAdapter(),
    )
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
    reference = canonicalize_formal_event(
        _event(),
        candidate_adapter=S01CandidateAdapter(),
    )

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
