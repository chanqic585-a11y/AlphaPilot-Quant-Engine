"""Whitelist and validation metadata for factor DSL operators."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OperatorSpec:
    name: str
    minArgs: int
    maxArgs: int
    resultType: str = "number"
    windowArgs: tuple[int, ...] = ()
    offsetArgs: tuple[int, ...] = ()
    domainRequirements: tuple[str, ...] = ()
    argumentTypes: tuple[str, ...] = ()


OPERATOR_SPECS: dict[str, OperatorSpec] = {
    "lag": OperatorSpec("lag", 2, 2, windowArgs=(1,), offsetArgs=(1,)),
    "delta": OperatorSpec("delta", 2, 2, windowArgs=(1,), offsetArgs=(1,)),
    "rolling_mean": OperatorSpec("rolling_mean", 2, 2, windowArgs=(1,)),
    "rolling_std": OperatorSpec("rolling_std", 2, 2, windowArgs=(1,)),
    "rolling_min": OperatorSpec("rolling_min", 2, 2, windowArgs=(1,)),
    "rolling_max": OperatorSpec("rolling_max", 2, 2, windowArgs=(1,)),
    "rolling_rank": OperatorSpec("rolling_rank", 2, 2, windowArgs=(1,)),
    "zscore": OperatorSpec("zscore", 2, 2, windowArgs=(1,), domainRequirements=("std_nonzero",)),
    "correlation": OperatorSpec("correlation", 3, 3, windowArgs=(2,)),
    "decay_linear": OperatorSpec("decay_linear", 2, 2, windowArgs=(1,)),
    "cross_sectional_rank": OperatorSpec("cross_sectional_rank", 1, 1),
    "group_neutralize": OperatorSpec(
        "group_neutralize", 2, 2, argumentTypes=("number", "group")
    ),
    "safe_add": OperatorSpec("safe_add", 2, 2),
    "safe_subtract": OperatorSpec("safe_subtract", 2, 2),
    "safe_multiply": OperatorSpec("safe_multiply", 2, 2),
    "safe_divide": OperatorSpec(
        "safe_divide", 2, 2, domainRequirements=("denominator_nonzero",)
    ),
    "safe_log": OperatorSpec("safe_log", 1, 1, domainRequirements=("log_input_positive",)),
    "safe_sqrt": OperatorSpec(
        "safe_sqrt", 1, 1, domainRequirements=("sqrt_input_nonnegative",)
    ),
    "where": OperatorSpec("where", 3, 3, argumentTypes=("bool", "number", "number")),
}

LEGACY_FUNCTION_ALIASES = {
    "ts_mean": "rolling_mean",
    "ts_std": "rolling_std",
    "ts_min": "rolling_min",
    "ts_max": "rolling_max",
    "rank": "cross_sectional_rank",
}

SPECIAL_LEGACY_FUNCTIONS = {"ts_return"}
PARSER_FUNCTION_NAMES = frozenset(OPERATOR_SPECS) | frozenset(LEGACY_FUNCTION_ALIASES) | SPECIAL_LEGACY_FUNCTIONS
COMMUTATIVE_FUNCTIONS = frozenset({"safe_add", "safe_multiply"})
