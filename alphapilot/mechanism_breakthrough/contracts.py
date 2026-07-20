"""Frozen V41-V45 budgets and candidate identities."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from alphapilot.evolution.registry.hashing import stable_hash
from alphapilot.exit_policy import ExitPolicy, ExitPolicyMode
from alphapilot.research_screening.campaign_contract import (
    ADVISORY_CANDIDATE_SCHEMA,
    CandidateSpec,
)


@dataclass(frozen=True)
class MechanismBreakthroughBudget:
    maximum_campaigns: int
    maximum_mechanism_families: int
    maximum_candidates: int
    maximum_development_trials: int
    maximum_full_backtests: int
    maximum_formal_candidates: int
    inherited_full_backtests: int

    @classmethod
    def default(cls, *, inherited_full_backtests: int) -> "MechanismBreakthroughBudget":
        if inherited_full_backtests < 0:
            raise ValueError("inherited_full_backtests_must_be_non_negative")
        return cls(
            maximum_campaigns=2,
            maximum_mechanism_families=3,
            maximum_candidates=6,
            maximum_development_trials=12,
            maximum_full_backtests=6,
            maximum_formal_candidates=2,
            inherited_full_backtests=inherited_full_backtests,
        )

    @property
    def policy_hash(self) -> str:
        return stable_hash(asdict(self), prefix="v41_v45_mechanism_budget")

    def validate_usage(
        self,
        *,
        campaigns: int,
        families: int,
        candidates: int,
        development_trials: int,
        full_backtests: int,
        formal_candidates: int,
    ) -> None:
        checks = (
            ("maximum_campaigns", campaigns, self.maximum_campaigns),
            ("maximum_mechanism_families", families, self.maximum_mechanism_families),
            ("maximum_candidates", candidates, self.maximum_candidates),
            ("maximum_development_trials", development_trials, self.maximum_development_trials),
            ("maximum_full_backtests", full_backtests, self.maximum_full_backtests),
            ("maximum_formal_candidates", formal_candidates, self.maximum_formal_candidates),
            ("inherited_full_backtests", full_backtests, self.inherited_full_backtests),
        )
        for name, actual, maximum in checks:
            if actual > maximum:
                raise ValueError(f"{name}_exceeded:{actual}>{maximum}")


def _hybrid_exit(maximum_hold_bars: int) -> ExitPolicy:
    return ExitPolicy(
        mode=ExitPolicyMode.HYBRID,
        maximumHoldBars=maximum_hold_bars,
        parameters={
            "partialAtR": 1.0,
            "partialFraction": 0.5,
            "remainderMode": "trailing",
            "trailingAtrMultiple": 1.5,
        },
    )


def _breakout_candidate(direction: str) -> CandidateSpec:
    return CandidateSpec(
        candidateId=f"v42_breakout_trap_second_entry_{direction}_4h_v1",
        familyId="v42_breakout_trap_second_entry",
        marketMechanismId="v42_breakout_trap_second_entry",
        direction=direction,
        timeframe="4h",
        causalRationale=(
            "A failed first breakout followed by a second failed boundary test can force "
            "late breakout participants to exit and reprice back through the range."
        ),
        eventDefinition={
            "referenceBoundaryBars": 20,
            "atrWindow": 20,
            "maximumFirstBreakAtr": 0.5,
            "failureWindowBars": 2,
            "secondTestWindowBars": 6,
            "retestToleranceAtr": 0.1,
            "stopBufferAtr": 0.1,
            "maximumDistanceAtr": 2.5,
            "entryReference": "next_bar_open",
            "sameBarRule": "stop_first_conservative",
        },
        invalidation="Initial stop remains beyond both failed-test structural extremes plus 0.10 ATR20.",
        stopAtr=2.5,
        targetR=None,
        maximumHoldBars=20,
        requiredData=("ohlcv", "quote_turnover"),
        expectedFailureRegimes=("persistent_breakout", "gap_through_stop", "thin_liquidity"),
        schemaVersion=ADVISORY_CANDIDATE_SCHEMA,
        exitPolicy=_hybrid_exit(20),
    )


def _spike_candidate(direction: str) -> CandidateSpec:
    return CandidateSpec(
        candidateId=f"v42_spike_pullback_continuation_{direction}_1h_v1",
        familyId="v42_spike_pullback_continuation",
        marketMechanismId="v42_spike_pullback_continuation",
        direction=direction,
        timeframe="1h",
        causalRationale=(
            "Three unusually strong directional candles followed by a shallow two-to-four bar "
            "pullback can preserve one-sided order flow into a causal continuation confirmation."
        ),
        eventDefinition={
            "spikeBarsMin": 3,
            "bodyMedianWindow": 20,
            "minimumBodyMultiple": 1.5,
            "outerCloseFraction": 0.25,
            "pullbackBarsMinimum": 2,
            "pullbackBarsMaximum": 4,
            "maximumRetracement": 0.5,
            "atrWindow": 20,
            "stopBufferAtr": 0.1,
            "maximumDistanceAtr": 2.5,
            "entryReference": "next_bar_open",
            "sameBarRule": "stop_first_conservative",
        },
        invalidation="Initial stop remains beyond the frozen pullback extreme plus 0.10 ATR20.",
        stopAtr=2.5,
        targetR=None,
        maximumHoldBars=24,
        requiredData=("ohlcv", "quote_turnover"),
        expectedFailureRegimes=("exhaustion_spike", "deep_retrace", "thin_liquidity"),
        schemaVersion=ADVISORY_CANDIDATE_SCHEMA,
        exitPolicy=_hybrid_exit(24),
    )


def build_frozen_candidates() -> tuple[CandidateSpec, ...]:
    """Return the exact preregistered A/B directional identities."""

    return (
        _breakout_candidate("long"),
        _breakout_candidate("short"),
        _spike_candidate("long"),
        _spike_candidate("short"),
    )


def dynamic_pair_candidate_spec() -> dict[str, object]:
    core: dict[str, object] = {
        "candidateId": "v43_dynamic_residual_pair_portfolio_4h_v1",
        "familyId": "v43_dynamic_residual_pair_portfolio",
        "strategyType": "pair_relative_value",
        "direction": "market_neutral",
        "timeframe": "4h",
        "pairUniverse": ["BTC-ETH", "ETH-LINK", "BTC-LTC"],
        "main": {
            "hedgeWindow": 90,
            "zWindow": 120,
            "entryZ": 2.0,
            "exitZ": 0.5,
            "stopZ": 3.5,
            "maximumHoldBars": 60,
            "entryReference": "next_bar_open_both_legs",
        },
        "diagnosticSensitivity": {"hedgeWindow": 180, "zWindow": 180},
        "benchmark": "static_hedge_ratio_residual_reversion",
        "targetRGateMode": "advisory",
        "minimumTargetR": None,
        "initialStopMayWiden": False,
    }
    return {**core, "definitionHash": stable_hash(core, prefix="v43_dynamic_pair")}

