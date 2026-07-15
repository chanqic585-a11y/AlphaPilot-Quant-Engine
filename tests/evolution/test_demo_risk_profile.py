from __future__ import annotations

import pytest

from alphapilot.evolution.promotion.demo_risk_profile import (
    build_demo_risk_profile,
    validate_demo_risk_profile,
)


def test_default_demo_risk_profile_is_bounded_and_immutable() -> None:
    profile = build_demo_risk_profile()

    assert profile["minimumTargetR"] == 2.0
    assert profile["stopWideningAllowed"] is False
    assert profile["addingToLossAllowed"] is False
    assert profile["martingaleAllowed"] is False
    assert profile["automaticParameterChangeAllowed"] is False
    assert validate_demo_risk_profile(profile) == profile["riskConfigHash"]


def test_risk_profile_rejects_stop_widening_and_sub_2r_target() -> None:
    profile = build_demo_risk_profile()
    profile["minimumTargetR"] = 1.9
    profile["stopWideningAllowed"] = True

    with pytest.raises(ValueError):
        validate_demo_risk_profile(profile)
