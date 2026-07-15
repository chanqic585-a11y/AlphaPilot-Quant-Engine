from __future__ import annotations

from alphapilot.derivatives_data.data_readiness_v2 import evaluate_v2_data_readiness


def test_readiness_fails_closed_when_fewer_than_two_directions_are_formal() -> None:
    report = evaluate_v2_data_readiness(
        {
            "A1": {"formalReady": False, "missing": ["realLiquidation"]},
            "A2": {"formalReady": False, "provisionalReady": True, "missing": ["realLiquidation"]},
            "B": {"formalReady": False, "missing": ["historicalOpenInterest", "historicalBasis"]},
            "C": {"formalReady": False, "missing": ["pointInTimeUniverse"]},
        }
    )

    assert report["status"] == "data_not_ready"
    assert report["campaignMayRun"] is False
    assert report["formalReadyDirectionCount"] == 0
    assert report["provisionalReadyDirections"] == ["A2"]


def test_readiness_requires_two_top_level_directions_not_two_variants() -> None:
    report = evaluate_v2_data_readiness(
        {
            "A1": {"formalReady": True, "missing": []},
            "A2": {"formalReady": True, "missing": []},
            "B": {"formalReady": False, "missing": ["historicalBasis"]},
            "C": {"formalReady": False, "missing": ["pointInTimeUniverse"]},
        }
    )

    assert report["formalReadyDirectionCount"] == 1
    assert report["status"] == "data_not_ready"


def test_readiness_allows_campaign_with_two_distinct_formal_directions() -> None:
    report = evaluate_v2_data_readiness(
        {
            "A1": {"formalReady": True, "missing": []},
            "A2": {"formalReady": False, "provisionalReady": True, "missing": ["realLiquidation"]},
            "B": {"formalReady": True, "missing": []},
            "C": {"formalReady": False, "missing": ["pointInTimeUniverse"]},
        }
    )

    assert report["formalReadyDirectionCount"] == 2
    assert report["status"] == "ready_for_preregistration"
    assert report["campaignMayRun"] is True
