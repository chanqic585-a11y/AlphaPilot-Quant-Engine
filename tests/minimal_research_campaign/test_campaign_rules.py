from __future__ import annotations

import pandas as pd
import pytest

from alphapilot.minimal_research_campaign.campaign import (
    build_hypothesis_inventory,
    build_representative_universe,
    route_prefilter_results,
)
from alphapilot.minimal_research_campaign.execution import simulate_long_event


def _member(index: int) -> dict[str, object]:
    return {
        "instrumentId": f"C{index:02d}-USDT-SWAP",
        "historyMonths": 24 + index,
        "liquidityScore": 50.0 + index,
        "volatilityScore": float(index % 5),
    }


def test_hypothesis_inventory_is_bounded_and_marks_cross_sectional_as_diagnostic() -> None:
    inventory = build_hypothesis_inventory(
        archived_family_ids={"trend_pullback", "breakout"}
    )

    assert 1 <= len(inventory) <= 3
    by_id = {row["strategyId"]: row for row in inventory}
    assert by_id["core_breadth_transition_leader_continuation_4h"]["noveltyStatus"] == "rejected_overlap"
    diagnostic = by_id["diagnostic_fixed_core_cross_sectional_momentum_1d"]
    assert diagnostic["diagnosticOnly"] is True
    assert diagnostic["formalPassEligible"] is False
    assert diagnostic["releaseEligible"] is False


def test_representative_universe_is_deterministic_and_includes_btc_eth() -> None:
    members = [_member(index) for index in range(18)]
    members[0]["instrumentId"] = "BTC-USDT-SWAP"
    members[1]["instrumentId"] = "ETH-USDT-SWAP"

    first = build_representative_universe(members, count=10)
    second = build_representative_universe(list(reversed(members)), count=10)

    assert first == second
    assert len(first) == 10
    assert {"BTC-USDT-SWAP", "ETH-USDT-SWAP"}.issubset(
        {row["instrumentId"] for row in first}
    )


def test_event_execution_uses_next_bar_and_never_widens_stop() -> None:
    frame = pd.DataFrame(
        {
            "open": [100.0, 101.0, 102.0, 103.0],
            "high": [150.0, 103.0, 106.0, 108.0],
            "low": [90.0, 99.0, 101.0, 102.0],
            "close": [120.0, 102.0, 105.0, 107.0],
        }
    )

    trade = simulate_long_event(
        frame,
        signal_index=0,
        initial_stop=99.0,
        target_r=2.0,
        maximum_hold_bars=3,
        round_trip_cost_rate=0.002,
    )

    assert trade["entryIndex"] == 1
    assert trade["entryPrice"] == 101.0
    assert set(trade["stopHistory"]) == {99.0}
    assert trade["targetPrice"] == 105.0
    assert trade["costR"] > 0


def test_event_execution_rejects_zero_cost_assumption() -> None:
    frame = pd.DataFrame(
        {"open": [100.0, 101.0], "high": [101.0, 102.0], "low": [99.0, 100.0], "close": [100.0, 101.0]}
    )

    with pytest.raises(ValueError, match="cost"):
        simulate_long_event(
            frame,
            signal_index=0,
            initial_stop=99.0,
            target_r=2.0,
            maximum_hold_bars=1,
            round_trip_cost_rate=0.0,
        )


def test_prefilter_failures_never_enter_formal_or_create_release() -> None:
    routed = route_prefilter_results(
        [
            {"strategyId": "failed", "passed": False},
            {"strategyId": "survivor", "passed": True},
            {
                "strategyId": "diagnostic",
                "passed": True,
                "diagnosticOnly": True,
            },
        ]
    )

    assert routed["formalStrategyIds"] == ["survivor"]
    assert routed["archivedStrategyIds"] == ["failed"]
    assert routed["releaseCount"] == 0
    assert routed["demoArm"] is False
    assert routed["orderCount"] == 0
