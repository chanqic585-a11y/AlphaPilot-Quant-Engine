import pandas as pd

from alphapilot.advisory_r_campaign.signals import replay_candidate


def _frame() -> pd.DataFrame:
    dates = pd.date_range("2026-01-01", periods=80, freq="1h", tz="UTC")
    closes = [100.0 + index * 0.1 for index in range(80)]
    closes[50] = 108.0
    closes[51] = 108.3
    return pd.DataFrame(
        {
            "date": dates,
            "open": closes,
            "high": [value + 0.5 for value in closes],
            "low": [value - 0.5 for value in closes],
            "close": closes,
            "volume": [1000.0] * 80,
            "confirmed": [1] * 80,
        }
    )


def test_replay_enters_on_next_bar_and_keeps_frozen_policy() -> None:
    candidate = {
        "candidateId": "test_candidate",
        "variantId": "S08",
        "familyId": "utc_session_transition",
        "direction": "conditional",
        "maximumHold": 4,
        "initialStopDefinition": {"kind": "atr", "multiple": 1.2, "mayWiden": False},
        "exitPolicyHash": "frozen_exit_hash",
        "exitPolicy": {
            "mode": "fixed_r",
            "maximumHoldBars": 4,
            "parameters": {"targetR": 1.2},
            "initialStopMayWiden": False,
        },
        "featureDefinition": {
            "utcEntryHours": [2],
            "trendWindow": 3,
            "minimumVolumeRatio": 0.5,
        },
        "entryDefinition": {"kind": "utc_session_transition", "directionFromPriorBars": 3},
    }

    events = replay_candidate(
        candidate,
        {"BTC-USDT-SWAP": _frame()},
        round_trip_cost_rate=0.0012,
    )

    assert events
    assert all(row["entryIndex"] == row["signalIndex"] + 1 for row in events)
    assert all(row["exitPolicyHash"] == "frozen_exit_hash" for row in events)
    assert all(row["initialStopMayWiden"] is False for row in events)
    assert all(row["targetR"] == 1.2 for row in events)


def test_replay_never_uses_unconfirmed_candles() -> None:
    frame = _frame()
    frame.loc[frame.index[-20:], "confirmed"] = 0
    candidate = {
        "candidateId": "test_candidate",
        "variantId": "S08",
        "familyId": "utc_session_transition",
        "direction": "conditional",
        "maximumHold": 4,
        "initialStopDefinition": {"kind": "atr", "multiple": 1.2, "mayWiden": False},
        "exitPolicyHash": "frozen_exit_hash",
        "exitPolicy": {
            "mode": "fixed_r",
            "maximumHoldBars": 4,
            "parameters": {"targetR": 1.2},
            "initialStopMayWiden": False,
        },
        "featureDefinition": {
            "utcEntryHours": [2],
            "trendWindow": 3,
            "minimumVolumeRatio": 0.5,
        },
        "entryDefinition": {"kind": "utc_session_transition", "directionFromPriorBars": 3},
    }

    events = replay_candidate(
        candidate,
        {"BTC-USDT-SWAP": frame},
        round_trip_cost_rate=0.0012,
    )

    last_confirmed = frame.loc[frame["confirmed"] == 1, "date"].max()
    assert all(pd.Timestamp(row["entryTimestamp"]) <= last_confirmed for row in events)
