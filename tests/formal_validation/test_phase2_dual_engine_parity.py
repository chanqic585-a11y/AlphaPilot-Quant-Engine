from __future__ import annotations

import json
from copy import deepcopy

import pytest

from alphapilot.formal_validation.dual_engine_parity import (
    DualEngineParityError,
    assert_dual_engine_parity,
    evaluate_dual_engine_parity,
    write_dual_engine_parity_report,
)


def _event(signal_id: str = "signal-1") -> dict[str, object]:
    return {
        "candidateId": "s01_bear_idiosyncratic_selloff_recovery_4h",
        "signalId": signal_id,
        "symbol": "ETH/USDT:USDT",
        "direction": "long",
        "signalTimestamp": "2026-01-01T00:00:00+00:00",
        "entryTimestamp": "2026-01-01T04:00:00+00:00",
        "entryPrice": 100.0,
        "initialStop": 96.8,
        "exitPolicyHash": "sha256:exit-policy",
        "exitLegCount": 2,
        "exitLegs": [
            {
                "legIndex": 0,
                "legFraction": 0.4,
                "exitReason": "partial_target",
                "triggerTimestamp": "2026-01-01T08:00:00+00:00",
                "executionTimestamp": "2026-01-01T08:00:00+00:00",
                "price": 102.24,
                "grossR": 0.28,
                "feesR": 0.01,
                "slippageR": 0.005,
                "spreadProxyR": 0.005,
                "fundingR": 0.0,
                "netR": 0.26,
                "isGapFill": False,
                "ambiguousPath": False,
            },
            {
                "legIndex": 1,
                "legFraction": 0.6,
                "exitReason": "maximum_hold",
                "triggerTimestamp": "2026-01-05T00:00:00+00:00",
                "executionTimestamp": "2026-01-05T00:00:00+00:00",
                "price": 103.0,
                "grossR": 0.5625,
                "feesR": 0.015,
                "slippageR": 0.0075,
                "spreadProxyR": 0.0075,
                "fundingR": 0.0,
                "netR": 0.5325,
                "isGapFill": False,
                "ambiguousPath": False,
            },
        ],
    }


def test_nonzero_exact_parity_passes_and_writes_report(tmp_path) -> None:
    reference = [_event()]
    implementation = deepcopy(reference)
    implementation[0]["entryPrice"] = 100.0 + 5e-10
    implementation[0]["exitLegs"][0]["netR"] = 0.26 - 5e-10

    report = assert_dual_engine_parity(reference, implementation)
    output = tmp_path / "dual_engine_readiness_parity.json"
    write_dual_engine_parity_report(output, report)

    written = json.loads(output.read_text(encoding="utf-8"))
    assert written["status"] == "passed"
    assert written["referenceEventCount"] == 1
    assert written["implementationEventCount"] == 1
    assert written["matchedEventCount"] == 1
    assert written["matchedLegCount"] == 2
    assert written["zeroSignalParityRejected"] is True


def test_zero_signal_parity_is_rejected() -> None:
    report = evaluate_dual_engine_parity([], [])

    assert report["status"] == "blocked"
    assert "zero_signal_fixture" in report["blockers"]
    with pytest.raises(DualEngineParityError, match="zero_signal_fixture"):
        assert_dual_engine_parity([], [])


def test_duplicate_events_are_compared_as_a_multiset() -> None:
    reference = [_event(), _event()]
    implementation = [_event()]

    report = evaluate_dual_engine_parity(reference, implementation)

    assert report["status"] == "failed"
    assert report["missingEventCount"] == 1
    with pytest.raises(DualEngineParityError, match="missing_event"):
        assert_dual_engine_parity(reference, implementation)


def test_exact_identity_and_leg_fields_do_not_use_numeric_tolerance() -> None:
    implementation = _event()
    implementation["signalTimestamp"] = "2026-01-01T00:00:01+00:00"
    implementation["exitLegs"][0]["legFraction"] = 0.4000000005

    report = evaluate_dual_engine_parity([_event()], [implementation])

    assert report["status"] == "failed"
    assert "event_identity_mismatch" in report["blockers"]


def test_null_or_non_finite_numeric_values_fail_closed() -> None:
    implementation = _event()
    implementation["initialStop"] = None

    with pytest.raises(DualEngineParityError, match="invalid_numeric_value"):
        assert_dual_engine_parity([_event()], [implementation])
