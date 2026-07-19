from __future__ import annotations

import numpy as np
import pandas as pd

from alphapilot.reference_strategy_research.candidates import build_selected_candidates
from alphapilot.reference_strategy_research.signals import replay_reference_candidate_events


COSTS = {"feeBpsPerSide": 0.0, "slippageBpsPerSide": 0.0, "spreadProxyBpsPerSide": 0.0}


def _candidate(candidate_id: str, direction: str):
    candidates = build_selected_candidates(
        [
            {
                "candidateId": candidate_id,
                "marketHypothesis": "causal fixture",
            }
        ]
    )
    return next(row for row in candidates if row.direction == direction)


def test_utc_range_breakout_uses_frozen_prior_range_and_next_bar_entry() -> None:
    dates = pd.date_range("2024-01-01T00:00:00Z", periods=32, freq="1h")
    frame = pd.DataFrame(
        {
            "date": dates,
            "open": np.full(32, 100.0),
            "high": np.full(32, 101.0),
            "low": np.full(32, 99.0),
            "close": np.full(32, 100.0),
            "volume": np.full(32, 1000.0),
        }
    )
    frame.loc[24, ["open", "high", "low", "close"]] = [100.0, 103.0, 99.8, 102.5]
    frame.loc[25, ["open", "high", "low", "close"]] = [102.6, 104.0, 102.0, 103.5]
    frame.loc[28, ["open", "high", "low", "close"]] = [101.0, 101.2, 99.8, 100.0]
    candidate = _candidate("ref_utc_session_range_breakout_1h_v1", "long")

    events = replay_reference_candidate_events(candidate=candidate, frame=frame, costs=COSTS)

    assert len(events) == 1
    event = events[0]
    assert event["signalPosition"] == 24
    assert event["entryPosition"] == 25
    assert event["entryPrice"] == 102.6
    assert event["initialStopPrice"] == 99.0
    assert event["entryReference"] == "next_bar_open"


def test_breakout_failure_requires_causal_second_test_and_next_bar_entry() -> None:
    dates = pd.date_range("2024-01-01T00:00:00Z", periods=50, freq="4h")
    frame = pd.DataFrame(
        {
            "date": dates,
            "open": np.full(50, 102.0),
            "high": np.full(50, 104.0),
            "low": np.full(50, 100.0),
            "close": np.full(50, 102.0),
            "volume": np.full(50, 1000.0),
        }
    )
    frame.loc[25, ["open", "high", "low", "close"]] = [101.0, 101.5, 98.5, 99.5]
    frame.loc[26, ["open", "high", "low", "close"]] = [99.7, 102.0, 99.2, 101.0]
    frame.loc[27, ["open", "high", "low", "close"]] = [100.8, 103.5, 99.1, 103.0]
    frame.loc[28, ["open", "high", "low", "close"]] = [103.1, 106.0, 102.5, 105.0]
    frame.loc[29, ["open", "high", "low", "close"]] = [105.0, 109.0, 104.0, 108.0]
    candidate = _candidate("ref_pa_breakout_failure_second_entry_4h_v1", "long")

    events = replay_reference_candidate_events(candidate=candidate, frame=frame, costs=COSTS)

    assert len(events) == 1
    event = events[0]
    assert event["signalPosition"] == 27
    assert event["entryPosition"] == 28
    assert event["entryPrice"] == 103.1
    assert event["initialStopPrice"] < 98.5
    assert event["entryReference"] == "next_bar_open"


def test_future_bar_change_does_not_change_signal_timestamp() -> None:
    dates = pd.date_range("2024-01-01T00:00:00Z", periods=32, freq="1h")
    frame = pd.DataFrame(
        {
            "date": dates,
            "open": np.full(32, 100.0),
            "high": np.full(32, 101.0),
            "low": np.full(32, 99.0),
            "close": np.full(32, 100.0),
            "volume": np.full(32, 1000.0),
        }
    )
    frame.loc[24, ["open", "high", "low", "close"]] = [100.0, 103.0, 99.8, 102.5]
    frame.loc[25, ["open", "high", "low", "close"]] = [102.6, 104.0, 102.0, 103.5]
    candidate = _candidate("ref_utc_session_range_breakout_1h_v1", "long")
    original = replay_reference_candidate_events(candidate=candidate, frame=frame, costs=COSTS)
    changed = frame.copy()
    changed.loc[31, ["open", "high", "low", "close"]] = [500.0, 600.0, 400.0, 550.0]
    replayed = replay_reference_candidate_events(candidate=candidate, frame=changed, costs=COSTS)

    assert original[0]["signalTimestamp"] == replayed[0]["signalTimestamp"]
    assert original[0]["entryTimestamp"] == replayed[0]["entryTimestamp"]
