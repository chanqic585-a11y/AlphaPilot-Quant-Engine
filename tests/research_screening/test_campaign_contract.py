import pytest

from alphapilot.research_screening.campaign_contract import (
    CandidateSpec,
    ExperimentBudget,
    build_campaign_preregistration,
)


def _candidate(identifier: str = "candidate_a") -> CandidateSpec:
    return CandidateSpec(
        candidateId=identifier,
        familyId="volatility_compression_breakout",
        marketMechanismId="volatility_compression_breakout",
        direction="long",
        timeframe="1h",
        causalRationale="Compression can precede directional range expansion.",
        eventDefinition={"compressionQuantile": 0.25, "breakoutBars": 20},
        invalidation="Price crosses the fixed initial stop.",
        stopAtr=1.5,
        targetR=2.0,
        maximumHoldBars=24,
        requiredData=("ohlcv",),
        expectedFailureRegimes=("illiquid_gap",),
    )


def test_candidate_contract_rejects_sub_two_r_and_first_round_5m() -> None:
    with pytest.raises(ValueError, match="targetR"):
        CandidateSpec(**{**_candidate().__dict__, "targetR": 1.99})
    with pytest.raises(ValueError, match="5m"):
        CandidateSpec(**{**_candidate().__dict__, "timeframe": "5m"})


def test_preregistration_is_stable_and_locks_holdout_before_selection() -> None:
    boundaries = {
        "1h": {
            "developmentEnd": "2023-07-01T00:00:00+00:00",
            "walkForwardEnd": "2025-01-01T00:00:00+00:00",
            "holdoutEnd": "2026-05-20T00:00:00+00:00",
        }
    }
    kwargs = {
        "external_reference_manifest_hash": "external_hash",
        "data_snapshot_hash": "snapshot_hash",
        "factor_shortlist_hash": "shortlist_hash",
        "candidates": [_candidate()],
        "time_boundaries": boundaries,
        "code_commit": "abc123",
    }
    first = build_campaign_preregistration(**kwargs)
    second = build_campaign_preregistration(**kwargs)

    assert first == second
    assert first["campaignId"].startswith("phase3c_campaign_")
    assert first["holdout"]["hash"].startswith("holdout_")
    assert first["holdout"]["accessCountBeforeFinalEvaluation"] == 0
    assert first["splitPolicy"]["ratios"] == {
        "development": 0.55,
        "walkForward": 0.25,
        "holdout": 0.2,
    }
    assert first["experimentBudget"] == ExperimentBudget().to_dict()


def test_preregistration_enforces_bounded_candidate_budget() -> None:
    candidates = [
        CandidateSpec(**{**_candidate().__dict__, "candidateId": f"candidate_{index}"})
        for index in range(17)
    ]
    with pytest.raises(ValueError, match="maximumInitialCandidates"):
        build_campaign_preregistration(
            external_reference_manifest_hash="external_hash",
            data_snapshot_hash="snapshot_hash",
            factor_shortlist_hash="shortlist_hash",
            candidates=candidates,
            time_boundaries={},
            code_commit="abc123",
        )
