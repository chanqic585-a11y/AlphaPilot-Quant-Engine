from __future__ import annotations

import pytest

from alphapilot.research_factory.renewal_candidate_types import (
    build_cross_sectional_portfolio_candidate,
    build_directional_event_candidate,
    build_pair_relative_value_candidate,
    validate_candidate_batch,
    validate_candidate_novelty,
)


def _base() -> dict[str, object]:
    return {
        "data_contract": {"formalReady": True, "contractHash": "data-1"},
        "benchmark_contract": {"formalGateEligible": True, "contractHash": "bench-1"},
        "falsification": "No positive net edge after cost and capital competition.",
    }


def test_directional_event_v2_requires_low_frequency_and_complete_contracts() -> None:
    candidate = build_directional_event_candidate(
        family_id="volatility_compression_release",
        candidate_id="dir-1",
        side="long_short",
        timeframe="4h",
        mechanism_signature="compression-release-v1",
        signal_definition={"event": "compression_then_directional_release"},
        ranking_definition={"field": "release_strength_z", "direction": "descending"},
        capacity_definition={"field": "quote_turnover", "minimumCoveragePct": 100.0},
        risk_definition={"riskUnit": "R", "maximumConcurrent": 3},
        exit_definition={"policyId": "adaptive_exit_v1"},
        **_base(),
    )

    assert candidate["strategyType"] == "directional_event_v2"
    assert candidate["timeframe"] == "4h"
    assert candidate["candidateHash"]

    with pytest.raises(ValueError, match="directional_event_timeframe"):
        build_directional_event_candidate(
            family_id="too-fast",
            candidate_id="dir-fast",
            side="long",
            timeframe="15m",
            mechanism_signature="too-fast-v1",
            signal_definition={"event": "x"},
            ranking_definition={"field": "x"},
            capacity_definition={"field": "quote_turnover"},
            risk_definition={"riskUnit": "R"},
            exit_definition={"policyId": "x"},
            **_base(),
        )


def test_pair_relative_value_requires_two_legs_and_synchronized_execution() -> None:
    candidate = build_pair_relative_value_candidate(
        family_id="btc_eth_relative_dislocation",
        candidate_id="pair-1",
        timeframe="4h",
        mechanism_signature="cointegration-dislocation-v1",
        legs=[
            {"instrumentId": "BTC-USDT-SWAP", "side": "long"},
            {"instrumentId": "ETH-USDT-SWAP", "side": "short"},
        ],
        pair_identity="BTC-USDT-SWAP|ETH-USDT-SWAP",
        hedge_ratio_definition={"method": "rolling_beta", "lookbackBars": 180},
        exposure_definition={"targetNetBeta": 0.0, "maximumGrossExposure": 1.0},
        synchronization_policy={"maximumEntryLagBars": 0},
        two_leg_capacity_definition={"minimumCoveragePct": 100.0},
        two_leg_cost_definition={"stressMultipliers": [1.0, 1.5, 2.0]},
        fill_failure_policy={"action": "cancel_both_legs"},
        exit_definition={"policyId": "spread_mean_reversion_exit_v1"},
        **_base(),
    )

    assert candidate["strategyType"] == "pair_relative_value_v1"
    assert len(candidate["legs"]) == 2
    assert candidate["pairUniverseFrozenBeforeResults"] is True

    with pytest.raises(ValueError, match="pair_requires_exactly_two_legs"):
        build_pair_relative_value_candidate(
            family_id="broken-pair",
            candidate_id="pair-broken",
            timeframe="4h",
            mechanism_signature="broken-v1",
            legs=[{"instrumentId": "BTC-USDT-SWAP", "side": "long"}],
            pair_identity="broken",
            hedge_ratio_definition={"method": "rolling_beta"},
            exposure_definition={"targetNetBeta": 0.0},
            synchronization_policy={"maximumEntryLagBars": 0},
            two_leg_capacity_definition={"minimumCoveragePct": 100.0},
            two_leg_cost_definition={"stressMultipliers": [1.0]},
            fill_failure_policy={"action": "cancel_both_legs"},
            exit_definition={"policyId": "x"},
            **_base(),
        )


def test_cross_sectional_portfolio_requires_pit_universe_and_portfolio_controls() -> None:
    candidate = build_cross_sectional_portfolio_candidate(
        family_id="cross_sectional_residual_momentum",
        candidate_id="portfolio-1",
        rebalance_timeframe="1d",
        mechanism_signature="residual-momentum-neutral-v1",
        universe_policy={"pointInTime": True, "minimumAssets": 20},
        ranking_definition={"field": "residual_momentum", "deterministicTieBreak": "instrumentId"},
        quantile_policy={"longQuantile": 0.2, "shortQuantile": 0.2},
        exposure_policy={"gross": 1.0, "net": 0.0},
        turnover_policy={"maximumOneWayTurnover": 0.5},
        capacity_definition={"minimumCoveragePct": 100.0},
        cluster_neutrality_policy={"policyHash": "cluster-1"},
        btc_beta_policy={"policyHash": "beta-1"},
        **_base(),
    )

    assert candidate["strategyType"] == "cross_sectional_portfolio_v1"
    assert candidate["singleTradeRGateApplicable"] is False
    assert candidate["universePolicy"]["pointInTime"] is True

    with pytest.raises(ValueError, match="portfolio_requires_pit_universe"):
        build_cross_sectional_portfolio_candidate(
            family_id="bad-portfolio",
            candidate_id="portfolio-bad",
            rebalance_timeframe="1d",
            mechanism_signature="bad-v1",
            universe_policy={"pointInTime": False},
            ranking_definition={"field": "x"},
            quantile_policy={"longQuantile": 0.2, "shortQuantile": 0.2},
            exposure_policy={"gross": 1.0, "net": 0.0},
            turnover_policy={"maximumOneWayTurnover": 0.5},
            capacity_definition={"minimumCoveragePct": 100.0},
            cluster_neutrality_policy={"policyHash": "cluster-1"},
            btc_beta_policy={"policyHash": "beta-1"},
            **_base(),
        )


def test_novelty_rejects_failed_identity_threshold_tweak_and_old_family() -> None:
    candidate = build_directional_event_candidate(
        family_id="opening_range_failure_reversal",
        candidate_id="failed-id",
        side="short",
        timeframe="4h",
        mechanism_signature="old-mechanism",
        signal_definition={"event": "same_event", "threshold": 1.1},
        ranking_definition={"field": "same_rank"},
        capacity_definition={"field": "quote_turnover"},
        risk_definition={"riskUnit": "R"},
        exit_definition={"policyId": "same-exit"},
        **_base(),
    )
    result = validate_candidate_novelty(
        candidate=candidate,
        prior_candidate_ids={"failed-id"},
        prior_family_ids={"opening_range_failure_reversal"},
        failed_mechanism_signatures={"old-mechanism"},
    )

    assert result["novel"] is False
    assert "candidate_identity_reused" in result["rejectionReasons"]
    assert "failed_mechanism_reused" in result["rejectionReasons"]
    assert "prohibited_legacy_family" in result["rejectionReasons"]


def test_batch_limits_two_families_and_four_candidates_per_type() -> None:
    candidates = []
    for index in range(5):
        candidates.append(
            build_directional_event_candidate(
                family_id=f"family-{index % 2}",
                candidate_id=f"candidate-{index}",
                side="long_short",
                timeframe="4h",
                mechanism_signature=f"mechanism-{index}",
                signal_definition={"event": f"event-{index}"},
                ranking_definition={"field": "rank"},
                capacity_definition={"field": "quote_turnover"},
                risk_definition={"riskUnit": "R"},
                exit_definition={"policyId": "adaptive"},
                **_base(),
            )
        )

    with pytest.raises(ValueError, match="candidate_type_budget_exceeded"):
        validate_candidate_batch(candidates)

