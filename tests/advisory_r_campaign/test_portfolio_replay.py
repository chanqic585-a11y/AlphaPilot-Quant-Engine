from __future__ import annotations

import pandas as pd

from alphapilot.advisory_r_campaign.candidates import build_candidate_inventory
from alphapilot.advisory_r_campaign.portfolio_replay import replay_portfolio_candidate


def _frame(slope: float) -> pd.DataFrame:
    dates = pd.date_range("2025-01-01", periods=150, freq="4h", tz="UTC")
    closes = [100.0 + slope * index for index in range(150)]
    return pd.DataFrame(
        {
            "date": dates,
            "open": closes,
            "high": [value + 0.1 for value in closes],
            "low": [value - 0.1 for value in closes],
            "close": closes,
            "volume": [3_000.0] * 150,
            "confirmed": [1] * 150,
        }
    )


def test_s09_uses_long_short_quantiles_and_rebalance_grid() -> None:
    candidate = next(row for row in build_candidate_inventory() if row["variantId"] == "S09")
    frames = {"BTC-USDT-SWAP": _frame(-0.05)}
    for index, slope in enumerate([-0.01, -0.02, -0.03, -0.07, -0.09, -0.12], start=1):
        frames[f"C{index}-USDT-SWAP"] = _frame(slope)

    events = replay_portfolio_candidate(candidate, frames, round_trip_cost_rate=0.002)

    assert events
    assert all(row["grossExposure"] == 1.0 for row in events)
    assert all(abs(row["netExposure"]) < 1e-12 for row in events)
    assert all(row["longSymbols"] and row["shortSymbols"] for row in events)
    assert all(row["signalIndex"] % 6 == 0 for row in events)
    assert all(row["historicalPitAvailable"] is False for row in events)
    assert all(row["fixedCohortBias"] is True for row in events)
