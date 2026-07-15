from alphapilot.research_screening.campaign_preregistration import (
    build_default_candidates,
    calculate_time_boundaries,
)


def test_default_campaign_has_six_bounded_market_mechanism_candidates() -> None:
    candidates = build_default_candidates()

    assert len(candidates) == 6
    assert {candidate.marketMechanismId for candidate in candidates} == {
        "volatility_compression_breakout",
        "idiosyncratic_shock_reversion",
        "funding_crowding_reversal",
    }
    assert {candidate.direction for candidate in candidates} == {"long", "short"}
    assert all(candidate.timeframe in {"1h", "4h"} for candidate in candidates)
    assert all(candidate.targetR >= 2 for candidate in candidates)
    assert all(not candidate.factorConfirmations for candidate in candidates)


def test_time_boundaries_use_common_coverage_and_five_walk_forward_folds() -> None:
    catalog = {
        "datasets": [
            {
                "dataType": "ohlcv",
                "timeframe": "1h",
                "startTime": "2020-01-01T00:00:00+00:00",
                "endTime": "2024-01-01T00:00:00+00:00",
            },
            {
                "dataType": "ohlcv",
                "timeframe": "1h",
                "startTime": "2020-02-01T00:00:00+00:00",
                "endTime": "2023-12-01T00:00:00+00:00",
            },
        ]
    }

    boundaries = calculate_time_boundaries(catalog, ("1h",))
    one_hour = boundaries["1h"]

    assert one_hour["developmentStart"] == "2020-02-01T00:00:00+00:00"
    assert one_hour["holdoutEnd"] == "2023-12-01T00:00:00+00:00"
    assert one_hour["developmentEnd"] == one_hour["walkForwardStart"]
    assert one_hour["walkForwardEnd"] == one_hour["holdoutStart"]
    assert len(one_hour["walkForwardFolds"]) == 5
    assert one_hour["walkForwardFolds"][0]["start"] == one_hour["walkForwardStart"]
    assert one_hour["walkForwardFolds"][-1]["end"] == one_hour["walkForwardEnd"]
