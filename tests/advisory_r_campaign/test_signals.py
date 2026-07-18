import pandas as pd
import inspect

import alphapilot.advisory_r_campaign.signals as campaign_signals
from alphapilot.advisory_r_campaign.signals import (
    load_candidate_signals,
    replay_candidate,
)
from alphapilot.exit_policy import exit_policy_from_dict, exit_policy_hash


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
            "version": "advisory_r_exit_policy_v1",
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
    candidate["exitPolicyHash"] = exit_policy_hash(
        exit_policy_from_dict(candidate["exitPolicy"])
    )

    events = replay_candidate(
        candidate,
        {"BTC-USDT-SWAP": _frame()},
        round_trip_cost_rate=0.0012,
    )

    assert events
    assert all(row["entryIndex"] == row["signalIndex"] + 1 for row in events)
    assert all(row["exitPolicyHash"] == candidate["exitPolicyHash"] for row in events)
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
            "version": "advisory_r_exit_policy_v1",
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
    candidate["exitPolicyHash"] = exit_policy_hash(
        exit_policy_from_dict(candidate["exitPolicy"])
    )

    events = replay_candidate(
        candidate,
        {"BTC-USDT-SWAP": frame},
        round_trip_cost_rate=0.0012,
    )

    last_confirmed = frame.loc[frame["confirmed"] == 1, "date"].max()
    assert all(pd.Timestamp(row["entryTimestamp"]) <= last_confirmed for row in events)


def test_campaign_has_no_second_hand_written_exit_simulator() -> None:
    assert not hasattr(campaign_signals, "_simulate_event")
    assert "replay_exit_policy" in inspect.getsource(campaign_signals._replay_event)


def test_structural_signal_loader_never_calls_exit_replay(monkeypatch) -> None:
    candidate = {
        "candidateId": "test_candidate",
        "variantId": "S08",
        "familyId": "utc_session_transition",
        "direction": "conditional",
        "timeframe": "1h",
        "maximumHold": 4,
        "exitPolicy": {
            "version": "advisory_r_exit_policy_v1",
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
        "entryDefinition": {
            "kind": "utc_session_transition",
            "directionFromPriorBars": 3,
        },
    }
    monkeypatch.setattr(
        campaign_signals,
        "replay_exit_policy",
        lambda **_: (_ for _ in ()).throw(AssertionError("exit replay called")),
    )

    signals = load_candidate_signals(candidate, {"BTC-USDT-SWAP": _frame()})

    assert signals
    assert all(row["entryTimestamp"] > row["signalTimestamp"] for row in signals)
    assert all(row["structuralOnly"] is True for row in signals)
    assert all("realizedNetR" not in row for row in signals)
