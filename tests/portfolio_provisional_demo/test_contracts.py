from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from alphapilot.portfolio_provisional_demo.contracts import (
    build_cooldown_rejection,
    build_cooldown_semantics,
    build_execution_identity,
    build_portfolio_definition,
    build_provisional_release,
    build_release_binding_audit,
    build_risk_overlay,
    build_universe_audit,
    cooldown_is_blocked,
    validate_exact_approval,
    validate_provisional_release,
)


COMPONENTS = [
    {
        "candidateId": "short_1h",
        "strategyDefinitionHash": "strategy_short_hash",
        "family": "short_rejection",
        "direction": "short",
        "timeframe": "1h",
        "strategyDefinition": {"parameters": {"stop_atr": 1.0}},
    },
    {
        "candidateId": "long_1d",
        "strategyDefinitionHash": "strategy_long_hash",
        "family": "mean_reversion",
        "direction": "long",
        "timeframe": "1d",
        "strategyDefinition": {"parameters": {"atrMultiplier": 1.2}},
    },
    {
        "candidateId": "breakout_1d",
        "strategyDefinitionHash": "strategy_breakout_hash",
        "family": "squeeze_breakout",
        "direction": "long",
        "timeframe": "1d",
        "strategyDefinition": {"parameters": {"atrMultiplier": 2.0}},
    },
]


def _definition(cooldown_days: int = 14) -> dict:
    cooldown = build_cooldown_semantics(
        pair_cooldown_days=cooldown_days,
        implementation_path="alphapilot/portfolio_rescue/replay.py",
        implementation_sha256="replay_source_hash",
    )
    return build_portfolio_definition(
        candidate_id="portfolio_candidate",
        source_candidate_hash="candidate_hash",
        source_campaign_hash="campaign_hash",
        components=COMPONENTS,
        selected_policy={"policy_id": "pair_14d_cooldown", "policy_hash": "policy_hash"},
        cooldown_semantics=cooldown,
        allocation_semantics="source_trade_ledger_native_risk_no_posthoc_weighting",
        cost_model={"feeRate": 0.0005, "slippageRate": 0.0002},
    )


def test_portfolio_definition_has_exact_components_and_no_invented_weights() -> None:
    definition = _definition()

    assert [row["candidateId"] for row in definition["components"]] == [
        "short_1h",
        "long_1d",
        "breakout_1d",
    ]
    assert definition["componentWeightSemantics"] == "no_explicit_weights"
    assert definition["componentWeights"] is None
    assert definition["portfolioDefinitionHash"].startswith("portfolio_provisional_definition_")


def test_cooldown_is_utc_elapsed_time_from_previous_accepted_same_pair_exit() -> None:
    semantics = build_cooldown_semantics(
        pair_cooldown_days=14,
        implementation_path="alphapilot/portfolio_rescue/replay.py",
        implementation_sha256="replay_source_hash",
    )
    previous_exit = datetime(2026, 7, 1, tzinfo=UTC)

    assert semantics["cooldownScope"] == "canonical_instrument_id"
    assert semantics["cooldownAnchor"] == "previous_accepted_closed_trade_exit_timestamp"
    assert semantics["cooldownDurationSeconds"] == 14 * 24 * 60 * 60
    assert semantics["timezone"] == "UTC"
    assert (
        semantics["boundaryRule"]
        == "entry_timestamp_greater_than_or_equal_to_cooldown_end_is_allowed"
    )
    assert semantics["crossComponentScope"] == "all_three_portfolio_components"
    assert semantics["cooldownSemanticsHash"].startswith("portfolio_cooldown_semantics_")
    assert semantics["boundaryEqualityAllowed"] is True
    assert semantics["clock"] == "utc_elapsed_time"
    assert cooldown_is_blocked(
        semantics, previous_exit, previous_exit + timedelta(days=14) - timedelta(seconds=1)
    )
    assert not cooldown_is_blocked(semantics, previous_exit, previous_exit + timedelta(days=14))


def test_changing_cooldown_changes_portfolio_definition_hash() -> None:
    assert _definition(14)["portfolioDefinitionHash"] != _definition(7)["portfolioDefinitionHash"]


def test_risk_overlay_can_only_tighten_existing_limits() -> None:
    overlay = build_risk_overlay(
        {
            "riskPerTradePercent": 0.25,
            "maxOpenRiskPercent": 1.0,
            "maxConcurrentPositions": 3,
            "feeRate": 0.0005,
            "slippageRate": 0.0002,
            "marginMode": "isolated",
            "maxLeverage": 2,
        }
    )

    assert overlay["riskPerTradePercent"] == 0.10
    assert overlay["maximumPortfolioOpenRiskPercent"] == 0.30
    assert overlay["maximumConcurrentPositions"] == 3
    assert overlay["noAdding"] is True
    assert overlay["noAveraging"] is True
    assert overlay["noMartingale"] is True
    assert overlay["initialStopMayWiden"] is False


def test_demo_universe_is_intersection_and_empty_intersection_blocks() -> None:
    audit = build_universe_audit(
        research_instruments=["BTC-USDT-SWAP", "SOL-USDT-SWAP", "ADA-USDT-SWAP"],
        public_snapshot_hash="public_hash",
        public_count=20,
        authenticated_hash="authenticated_hash",
        authenticated_count=116,
        authenticated_exact_list_retained=False,
        runtime_snapshot_hash="runtime_hash",
        runtime_instruments=["BTC-USDT-SWAP"],
    )
    assert audit["executionIntersection"] == ["BTC-USDT-SWAP"]
    assert audit["authenticatedDemoCount"] == 116
    assert audit["confirmedRuntimeCount"] == 1
    assert audit["status"] == "ready"

    empty = build_universe_audit(
        research_instruments=["ADA-USDT-SWAP"],
        public_snapshot_hash="public_hash",
        public_count=20,
        authenticated_hash="authenticated_hash",
        authenticated_count=116,
        authenticated_exact_list_retained=False,
        runtime_snapshot_hash="runtime_hash",
        runtime_instruments=["BTC-USDT-SWAP"],
    )
    assert empty["status"] == "blocked_demo_universe_empty"


def test_prohibited_position_recovery_mechanics_block_definition() -> None:
    unsafe = [dict(row) for row in COMPONENTS]
    unsafe[0] = {
        **unsafe[0],
        "strategyDefinition": {"parameters": {"martingaleEnabled": True}},
    }
    cooldown = build_cooldown_semantics(
        pair_cooldown_days=14,
        implementation_path="alphapilot/portfolio_rescue/replay.py",
        implementation_sha256="replay_source_hash",
    )

    with pytest.raises(PermissionError, match="prohibited_position_mechanic"):
        build_portfolio_definition(
            candidate_id="unsafe",
            source_candidate_hash="candidate_hash",
            source_campaign_hash="campaign_hash",
            components=unsafe,
            selected_policy={"policy_id": "pair_14d_cooldown"},
            cooldown_semantics=cooldown,
            allocation_semantics="source_trade_ledger_native_risk_no_posthoc_weighting",
            cost_model={"feeRate": 0.0005, "slippageRate": 0.0002},
        )


def test_provisional_release_cannot_claim_formal_or_live_and_requires_exact_hash_approval() -> None:
    definition = _definition()
    risk = build_risk_overlay(
        {"riskPerTradePercent": 0.25, "maxOpenRiskPercent": 1.0, "maxConcurrentPositions": 3}
    )
    universe = build_universe_audit(
        research_instruments=["BTC-USDT-SWAP"],
        public_snapshot_hash="public_hash",
        public_count=20,
        authenticated_hash="authenticated_hash",
        authenticated_count=116,
        authenticated_exact_list_retained=False,
        runtime_snapshot_hash="runtime_hash",
        runtime_instruments=["BTC-USDT-SWAP"],
    )
    release = build_provisional_release(
        release_id="provisional_release_1",
        portfolio_definition=definition,
        risk_overlay=risk,
        universe_audit=universe,
        historical_metrics={"profitFactor": 1.6, "expectancyR": 0.3},
        cost_stress_metrics={"profitFactor": 1.36},
        replay_parity_percent=100.0,
        execution_identity=build_execution_identity(
            portfolio_definition=definition,
            risk_overlay=risk,
            universe_audit=universe,
            quant_implementation_commit="a" * 40,
            console_execution_commit="b" * 40,
            quant_runtime_implementation_hash="quant_runtime_hash",
            console_runtime_implementation_hash="console_runtime_hash",
        ),
        generated_at="2026-07-20T00:00:00Z",
    )

    validate_provisional_release(release)
    assert release["formalPass"] is False
    assert release["cleanHistoricalOosPass"] is False
    assert release["livePromotionEligible"] is False
    assert release["automaticLivePromotionAllowed"] is False
    assert release["approved"] is False
    assert release["demoArm"] is False
    assert release["route"] == "blocked_waiting_exact_release_approval"
    binding = build_release_binding_audit(
        release=release,
        portfolio_definition=definition,
        risk_overlay=risk,
        universe_audit=universe,
    )
    assert binding["allRequiredBindingsPresent"] is True
    assert binding["transitiveHashChainVerified"] is True

    with pytest.raises(PermissionError, match="exact_release_hash_approval_required"):
        validate_exact_approval(
            release,
            risk,
            {"releaseHash": "wrong", "riskOverlayHash": risk["riskOverlayHash"]},
        )
    assert validate_exact_approval(
        release,
        risk,
        {
            "releaseHash": release["releaseHash"],
            "riskOverlayHash": risk["riskOverlayHash"],
        },
    )["status"] == "approved_not_armed"


def test_execution_commit_change_requires_a_new_release_hash() -> None:
    definition = _definition()
    risk = build_risk_overlay(
        {"riskPerTradePercent": 0.25, "maxOpenRiskPercent": 1.0, "maxConcurrentPositions": 3}
    )
    universe = build_universe_audit(
        research_instruments=["BTC-USDT-SWAP"],
        public_snapshot_hash="public_hash",
        public_count=20,
        authenticated_hash="authenticated_hash",
        authenticated_count=116,
        authenticated_exact_list_retained=False,
        runtime_snapshot_hash="runtime_hash",
        runtime_instruments=["BTC-USDT-SWAP"],
    )

    def release_for(commit: str) -> dict:
        identity = build_execution_identity(
            portfolio_definition=definition,
            risk_overlay=risk,
            universe_audit=universe,
            quant_implementation_commit=commit,
            console_execution_commit="b" * 40,
            quant_runtime_implementation_hash="quant_runtime_hash",
            console_runtime_implementation_hash="console_runtime_hash",
        )
        return build_provisional_release(
            release_id="provisional_release_1",
            portfolio_definition=definition,
            risk_overlay=risk,
            universe_audit=universe,
            historical_metrics={"profitFactor": 1.6, "expectancyR": 0.3},
            cost_stress_metrics={"profitFactor": 1.36},
            replay_parity_percent=100.0,
            execution_identity=identity,
            generated_at="2026-07-20T00:00:00Z",
        )

    assert release_for("a" * 40)["releaseHash"] != release_for("c" * 40)["releaseHash"]


def test_cooldown_rejection_is_diagnostic_only() -> None:
    event = build_cooldown_rejection(
        signal_id="signal-1",
        component_id="short_1h",
        instrument_id="BTC-USDT-SWAP",
        signal_timestamp="2026-07-10T00:00:00Z",
        cooldown_start="2026-07-01T00:00:00Z",
        cooldown_end="2026-07-15T00:00:00Z",
        remaining_seconds=432000,
    )
    assert event["rejectionReason"] == "same_pair_14d_cooldown"
    assert not ({"order", "position", "pnl", "netR"} & set(event))
