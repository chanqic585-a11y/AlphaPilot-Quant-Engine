from __future__ import annotations

import pytest

from alphapilot.research_screening.exit_geometry import (
    build_event_exit_geometry,
    position_size_for_frozen_risk,
    validate_stop_update,
)


def test_event_stop_is_frozen_and_remaining_target_remains_in_r_units() -> None:
    geometry = build_event_exit_geometry(
        direction="long",
        entry_price=100.0,
        initial_stop_price=95.0,
        remaining_target_r=2.0,
        partial_at_one_r=True,
    )

    assert geometry["oneRPrice"] == 105.0
    assert geometry["remainingTargetPrice"] == 110.0
    assert geometry["initialStopMayWiden"] is False
    assert position_size_for_frozen_risk(100.0, 100.0, 95.0) == 20.0


def test_event_exit_geometry_accepts_preregistered_target_below_two_r() -> None:
    geometry = build_event_exit_geometry(
        direction="long",
        entry_price=100.0,
        initial_stop_price=96.0,
        remaining_target_r=1.25,
        partial_at_one_r=False,
    )

    assert geometry["remainingTargetR"] == 1.25
    assert geometry["remainingTargetPrice"] == 105.0


def test_stop_can_tighten_but_never_widen() -> None:
    assert validate_stop_update("long", 95.0, 97.0) is True
    with pytest.raises(ValueError, match="widen"):
        validate_stop_update("long", 95.0, 90.0)


def test_portfolio_strategy_cannot_use_single_symbol_r_target() -> None:
    with pytest.raises(ValueError, match="portfolio"):
        build_event_exit_geometry(
            direction="portfolio",
            entry_price=100.0,
            initial_stop_price=95.0,
            remaining_target_r=2.0,
            partial_at_one_r=False,
        )
