from __future__ import annotations

import math

import pandas as pd

from alphapilot.advisory_r_campaign.candidates import build_candidate_inventory
from alphapilot.advisory_r_campaign.pair_replay import replay_pair_candidate


def _frame(
    multiplier: float,
    bump: float = 0.0,
    idiosyncratic_amplitude: float = 0.0,
) -> pd.DataFrame:
    dates = pd.date_range("2025-01-01", periods=600, freq="1h", tz="UTC")
    closes = [
        100.0
        + index * 0.03 * multiplier
        + math.sin(index * 0.23) * 2.0 * multiplier
        + idiosyncratic_amplitude * math.sin(index * 0.11 + 0.4)
        for index in range(600)
    ]
    for index in range(540, 546):
        closes[index] += bump * (index - 539)
    for index in range(546, 553):
        closes[index] += bump * (553 - index)
    return pd.DataFrame(
        {
            "date": dates,
            "open": closes,
            "high": [value + 0.15 for value in closes],
            "low": [value - 0.15 for value in closes],
            "close": closes,
            "volume": [2_000.0] * 600,
            "confirmed": [1] * 600,
        }
    )


def test_s04_replay_is_two_leg_and_charges_both_legs() -> None:
    candidate = next(row for row in build_candidate_inventory() if row["variantId"] == "S04")
    events = replay_pair_candidate(
        candidate,
        {
            "BTC-USDT-SWAP": _frame(1.0),
            "ETH-USDT-SWAP": _frame(
                1.2,
                bump=0.02,
                idiosyncratic_amplitude=0.05,
            ),
        },
        round_trip_cost_rate=0.002,
    )

    assert events
    assert all(len(row["marketLegs"]) == 2 for row in events)
    assert all(row["marketLegCount"] == 2 for row in events)
    assert all(row["twoLegCostMultiplier"] == 2.0 for row in events)
    assert all(row["fundingR"] is None for row in events)
