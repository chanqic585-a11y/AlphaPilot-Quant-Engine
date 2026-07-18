"""Frozen contracts for bounded V36 candidate research."""

from __future__ import annotations

from typing import Final


COMPARISON_PANEL_FIELDS: Final[tuple[str, ...]] = (
    "developmentStart",
    "developmentEnd",
    "dataSnapshotId",
    "costPolicyHash",
    "capitalPolicyHash",
    "benchmarkPolicyHash",
    "randomSeed",
)

TRIAL_SCALES: Final[tuple[float, ...]] = (0.9, 1.0, 1.1)

FAMILY_STRATEGY_TYPES: Final[dict[str, str]] = {
    "crypto_tsmom_turtle_v1": "directional",
    "crypto_pair_relative_value_v1": "pair",
    "crypto_conditional_mean_reversion_v1": "directional",
    "crypto_cross_sectional_factor_v1": "portfolio",
    "crypto_event_driven_v1": "event",
    "chan_structure_parser_v1": "context",
}

ELIGIBLE_REPLICATION_STATES: Final[frozenset[str]] = frozenset({"registered"})
BLOCKED_REPLICATION_STATES: Final[frozenset[str]] = frozenset({"data_blocked"})

FORMAL_OUTCOMES: Final[frozenset[str]] = frozenset(
    {
        "formal_pass",
        "research_pass_no_clean_holdout",
        "research_pass_funding_unavailable",
        "formal_economic_failed",
        "statistical_failed",
        "capital_infeasible",
        "data_blocked",
        "implementation_invalid",
    }
)

RELEASE_ELIGIBLE_OUTCOMES: Final[frozenset[str]] = frozenset({"formal_pass"})


class V36ContractError(ValueError):
    """Raised when a frozen V36 identity or evidence contract is invalid."""
