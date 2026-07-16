from __future__ import annotations

import numpy as np
import pandas as pd

from alphapilot.minimal_research_campaign.event_strategy import (
    replay_selloff_recovery_events,
)


def test_selloff_recovery_replays_only_on_next_bar_with_frozen_stop() -> None:
    size = 90
    close = np.linspace(100.0, 110.0, size)
    close[60] = 82.0
    close[61] = 90.0
    close[62:] = np.linspace(91.0, 105.0, size - 62)
    frame = pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=size, freq="4h", tz="UTC"),
            "open": close - 0.2,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": np.full(size, 1000.0),
            "confirmed": np.ones(size, dtype=int),
        }
    )
    market_return = pd.Series(np.zeros(size), index=frame.index)

    events = replay_selloff_recovery_events(
        frame,
        market_return=market_return,
        symbol="TEST-USDT-SWAP",
        residual_z_threshold=-1.5,
        residual_recovery_delta=0.1,
        market_crash_floor=-0.08,
        atr_stop_multiple=0.25,
        target_r=2.0,
        maximum_hold_bars=18,
        round_trip_cost_rate=0.002,
    )

    assert events
    assert all(row["entryIndex"] == row["signalIndex"] + 1 for row in events)
    assert all(row["initialStopMayWiden"] is False for row in events)
    assert all(row["targetR"] >= 2 for row in events)
    assert all(row["costR"] > 0 for row in events)

