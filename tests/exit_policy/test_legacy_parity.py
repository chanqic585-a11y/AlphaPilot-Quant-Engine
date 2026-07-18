from __future__ import annotations

import json

import pandas as pd
import pytest

from alphapilot.exit_policy.legacy_adapter import (
    legacy_fixed_r_policy,
    replay_legacy_candidate_exit,
)
from alphapilot.research_screening.campaign_contract import CandidateSpec
from alphapilot.research_screening.campaign_signals import replay_signal


def _candidate(direction: str = "long") -> CandidateSpec:
    return CandidateSpec(
        candidateId=f"legacy_{direction}",
        familyId="volatility_compression_breakout",
        marketMechanismId="volatility_compression_breakout",
        direction=direction,
        timeframe="1h",
        causalRationale="golden parity fixture",
        eventDefinition={"fixture": True},
        invalidation="fixed stop",
        stopAtr=1.0,
        targetR=2.0,
        maximumHoldBars=3,
        requiredData=("ohlcv",),
        expectedFailureRegimes=(),
    )


def _frame() -> pd.DataFrame:
    frame = pd.DataFrame(
        [
            {"open": 100, "high": 101, "low": 99, "close": 100, "volume": 10},
            {"open": 100, "high": 102.1, "low": 99.5, "close": 102, "volume": 10},
            {"open": 102, "high": 102.5, "low": 101, "close": 102, "volume": 10},
        ]
    )
    frame["date"] = pd.date_range("2024-01-01", periods=len(frame), freq="h", tz="UTC")
    return frame


def test_legacy_adapter_does_not_mutate_serialized_candidate_bytes() -> None:
    candidate = _candidate()
    before = json.dumps(
        candidate.to_dict(),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    policy = legacy_fixed_r_policy(candidate)

    after = json.dumps(
        candidate.to_dict(),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    assert after == before
    assert policy.parameters == {"targetR": 2.0}


def test_legacy_fixed_two_r_event_has_golden_execution_parity() -> None:
    frame = _frame()
    candidate = _candidate()
    kwargs = {
        "frame": frame,
        "signal_position": 0,
        "candidate": candidate,
        "atr_value": 1.0,
        "fee_bps_per_side": 5.0,
        "slippage_bps_per_side": 3.0,
        "spread_bps_per_side": 2.0,
    }

    legacy = replay_signal(**kwargs)
    advisory = replay_legacy_candidate_exit(**kwargs)

    assert legacy is not None
    assert advisory.entryPosition == legacy["entryPosition"]
    assert advisory.exitPosition == legacy["exitPosition"]
    assert advisory.legs[-1].reason == legacy["exitReason"]
    assert advisory.legs[-1].price == legacy["exitPrice"]
    assert advisory.ambiguousPath == legacy["ambiguousPath"]
    assert advisory.grossR == pytest.approx(legacy["grossR"])
    assert advisory.feesR == pytest.approx(legacy["feesR"])
    assert advisory.slippageR == pytest.approx(legacy["slippageR"])
    assert advisory.spreadProxyR == pytest.approx(legacy["spreadProxyR"])
    assert advisory.fundingR == pytest.approx(legacy["fundingR"])
    assert advisory.netR == pytest.approx(legacy["netR"])

