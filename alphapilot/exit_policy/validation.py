"""Strict validation for the declarative Advisory-R policy grammar."""

from __future__ import annotations

import math
from typing import Any, Mapping

from .models import ExitPolicy, ExitPolicyMode
from .schema import (
    MAXIMUM_ATR_MULTIPLE,
    MAXIMUM_HOLD_BARS,
    MAXIMUM_R_MULTIPLE,
    POLICY_VERSION,
    STRUCTURE_RULE_FIELDS,
)


def _number(value: Any, name: str, *, minimum: float, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite number")
    result = float(value)
    if not math.isfinite(result) or not minimum <= result <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return result


def _exact_fields(parameters: Mapping[str, Any], expected: set[str]) -> None:
    actual = set(parameters)
    missing = expected - actual
    unknown = actual - expected
    if missing:
        raise ValueError(f"missing exit-policy parameters: {sorted(missing)}")
    if unknown:
        raise ValueError(f"unknown exit-policy parameters: {sorted(unknown)}")


def _validate_structure_rule(value: Any) -> None:
    if not isinstance(value, Mapping):
        raise ValueError("structureRule must be a declarative object")
    kind = str(value.get("kind") or "")
    expected = STRUCTURE_RULE_FIELDS.get(kind)
    if expected is None:
        raise ValueError(f"unsupported structure rule: {kind or '<missing>'}")
    _exact_fields(value, set(expected))
    if kind == "residual_neutral_zone":
        _number(value["absoluteZscoreMaximum"], "absoluteZscoreMaximum", minimum=0.01, maximum=5.0)
    elif kind == "correlation_recovery":
        _number(value["minimumCorrelation"], "minimumCorrelation", minimum=-1.0, maximum=1.0)
    elif kind == "trend_invalidation":
        fast = int(_number(value["fastWindow"], "fastWindow", minimum=2, maximum=500))
        slow = int(_number(value["slowWindow"], "slowWindow", minimum=3, maximum=1_000))
        if fast >= slow:
            raise ValueError("fastWindow must be lower than slowWindow")
    elif kind == "session_end":
        hour = _number(value["utcHour"], "utcHour", minimum=0, maximum=23)
        if not hour.is_integer():
            raise ValueError("utcHour must be an integer")
    elif kind == "beta_rank_exit":
        _number(value["maximumRankPercentile"], "maximumRankPercentile", minimum=0.01, maximum=1.0)
    elif kind == "event_reversal":
        bars = _number(value["confirmationBars"], "confirmationBars", minimum=1, maximum=100)
        if not bars.is_integer():
            raise ValueError("confirmationBars must be an integer")


def _validate_partial(parameters: Mapping[str, Any]) -> None:
    _number(parameters["partialAtR"], "partialAtR", minimum=0.01, maximum=MAXIMUM_R_MULTIPLE)
    fraction = _number(parameters["partialFraction"], "partialFraction", minimum=0.000001, maximum=0.999999)
    if not 0.0 < fraction < 1.0:
        raise ValueError("partialFraction must be strictly between zero and one")


def validate_exit_policy(policy: ExitPolicy) -> ExitPolicy:
    if policy.version != POLICY_VERSION:
        raise ValueError(f"unsupported exit-policy version: {policy.version}")
    if policy.initialStopMayWiden:
        raise ValueError("initial stop may not widen")
    if not isinstance(policy.maximumHoldBars, int) or isinstance(policy.maximumHoldBars, bool):
        raise ValueError("maximumHoldBars must be an integer")
    if not 1 <= policy.maximumHoldBars <= MAXIMUM_HOLD_BARS:
        raise ValueError(f"maximumHoldBars must be between 1 and {MAXIMUM_HOLD_BARS}")
    if not isinstance(policy.parameters, Mapping):
        raise ValueError("parameters must be an object")

    parameters = policy.parameters
    if policy.mode is ExitPolicyMode.FIXED_R:
        _exact_fields(parameters, {"targetR"})
        _number(parameters["targetR"], "targetR", minimum=0.01, maximum=MAXIMUM_R_MULTIPLE)
    elif policy.mode is ExitPolicyMode.PARTIAL_THEN_TRAILING:
        _exact_fields(parameters, {"partialAtR", "partialFraction", "trailingAtrMultiple"})
        _validate_partial(parameters)
        _number(
            parameters["trailingAtrMultiple"],
            "trailingAtrMultiple",
            minimum=0.01,
            maximum=MAXIMUM_ATR_MULTIPLE,
        )
    elif policy.mode is ExitPolicyMode.STRUCTURE_OR_TIME:
        _exact_fields(parameters, {"structureRule"})
        _validate_structure_rule(parameters["structureRule"])
    elif policy.mode is ExitPolicyMode.HYBRID:
        remainder_mode = str(parameters.get("remainderMode") or "")
        if remainder_mode == "trailing":
            _exact_fields(
                parameters,
                {"partialAtR", "partialFraction", "remainderMode", "trailingAtrMultiple"},
            )
            _number(
                parameters["trailingAtrMultiple"],
                "trailingAtrMultiple",
                minimum=0.01,
                maximum=MAXIMUM_ATR_MULTIPLE,
            )
        elif remainder_mode == "structure":
            _exact_fields(
                parameters,
                {"partialAtR", "partialFraction", "remainderMode", "structureRule"},
            )
            _validate_structure_rule(parameters["structureRule"])
        else:
            raise ValueError("remainderMode must be trailing or structure")
        _validate_partial(parameters)
    else:
        raise ValueError(f"unsupported exit-policy mode: {policy.mode}")
    return policy

