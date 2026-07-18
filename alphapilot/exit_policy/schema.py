"""Versioned bounds for preregistered Advisory-R exit policies."""

from __future__ import annotations

POLICY_VERSION = "advisory_r_exit_policy_v1"
MAXIMUM_HOLD_BARS = 10_000
MAXIMUM_R_MULTIPLE = 20.0
MAXIMUM_ATR_MULTIPLE = 20.0

STRUCTURE_RULE_FIELDS: dict[str, frozenset[str]] = {
    "residual_neutral_zone": frozenset({"kind", "absoluteZscoreMaximum"}),
    "correlation_recovery": frozenset({"kind", "minimumCorrelation"}),
    "trend_invalidation": frozenset({"kind", "fastWindow", "slowWindow"}),
    "session_end": frozenset({"kind", "utcHour"}),
    "beta_rank_exit": frozenset({"kind", "maximumRankPercentile"}),
    "event_reversal": frozenset({"kind", "confirmationBars"}),
}

