import pandas as pd

from alphapilot.research_screening.campaign_contract import CandidateSpec
from alphapilot.research_screening.campaign_signals import replay_signal


def _candidate(direction: str = "long") -> CandidateSpec:
    return CandidateSpec(
        candidateId=f"fixture_{direction}",
        familyId="volatility_compression_breakout",
        marketMechanismId="volatility_compression_breakout",
        direction=direction,
        timeframe="1h",
        causalRationale="fixture",
        eventDefinition={},
        invalidation="fixed stop",
        stopAtr=1.0,
        targetR=2.0,
        maximumHoldBars=3,
        requiredData=("ohlcv",),
        expectedFailureRegimes=(),
    )


def _frame(rows: list[dict[str, float]]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    frame["date"] = pd.date_range("2024-01-01", periods=len(frame), freq="h", tz="UTC")
    return frame


def test_same_bar_stop_and_target_uses_conservative_stop_first() -> None:
    frame = _frame(
        [
            {"open": 100, "high": 101, "low": 99, "close": 100, "volume": 10},
            {"open": 100, "high": 104, "low": 98, "close": 101, "volume": 10},
            {"open": 101, "high": 102, "low": 100, "close": 101, "volume": 10},
        ]
    )
    event = replay_signal(
        frame=frame,
        signal_position=0,
        candidate=_candidate(),
        atr_value=1.0,
        fee_bps_per_side=0,
        slippage_bps_per_side=0,
        spread_bps_per_side=0,
    )

    assert event is not None
    assert event["grossR"] == -1.0
    assert event["ambiguousPath"] is True
    assert event["exitReason"] == "stop_loss"
    assert event["entryTimestamp"] == frame.iloc[1]["date"].isoformat()


def test_target_hit_records_two_r_and_separate_cost_components() -> None:
    frame = _frame(
        [
            {"open": 100, "high": 101, "low": 99, "close": 100, "volume": 10},
            {"open": 100, "high": 102.1, "low": 99.5, "close": 102, "volume": 10},
            {"open": 102, "high": 102.5, "low": 101, "close": 102, "volume": 10},
        ]
    )
    event = replay_signal(
        frame=frame,
        signal_position=0,
        candidate=_candidate(),
        atr_value=1.0,
        fee_bps_per_side=5,
        slippage_bps_per_side=3,
        spread_bps_per_side=2,
    )

    assert event is not None
    assert event["grossR"] == 2.0
    assert event["targetR"] == 2.0
    assert event["stopPrice"] == 99.0
    assert event["feesR"] > 0
    assert event["slippageR"] > 0
    assert event["spreadProxyR"] > 0
    assert event["netR"] < event["grossR"]
