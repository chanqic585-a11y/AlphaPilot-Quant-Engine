"""Evaluate a frozen, restricted factor-threshold policy at a completed bar."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import pandas as pd

from alphapilot.evolution.factor_dsl import parse_expression, validate_factor_expression
from alphapilot.evolution.factor_runs.definitions import DEFAULT_FACTOR_SPECS, FACTOR_FIELD_TYPES
from alphapilot.evolution.factor_runs.evaluator import evaluate_factor_expression
from alphapilot.evolution.registry.hashing import stable_hash

from .types import ForwardDecision


_OPERATORS = {
    "lt": lambda value, threshold: value < threshold,
    "lte": lambda value, threshold: value <= threshold,
    "gt": lambda value, threshold: value > threshold,
    "gte": lambda value, threshold: value >= threshold,
}


@dataclass(frozen=True)
class ForwardPolicyEvaluation:
    decision: ForwardDecision | None
    status: str
    context: dict[str, Any]


def materialize_latest_factors(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, float]]:
    required = {"timestamp_ms", "open", "high", "low", "close", "volume"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"Forward factor frame is missing: {', '.join(missing)}")
    ordered = frame.sort_values("timestamp_ms").drop_duplicates("timestamp_ms", keep="last").copy()
    for column in required:
        ordered[column] = pd.to_numeric(ordered[column], errors="coerce")
    if ordered[list(required)].isna().any().any():
        raise ValueError("Forward factor frame contains invalid numeric values")
    latest: dict[str, float] = {}
    for spec in DEFAULT_FACTOR_SPECS:
        expression = parse_expression(spec.expression)
        validation = validate_factor_expression(expression, field_types=FACTOR_FIELD_TYPES)
        if not validation.valid:
            raise ValueError(f"Invalid built-in factor expression: {spec.factorId}")
        column = f"factor_{spec.factorId}"
        ordered[column] = evaluate_factor_expression(expression, ordered)
        value = float(ordered[column].iloc[-1])
        latest[spec.factorId] = value
    return ordered, latest


def evaluate_frozen_policy(
    frame: pd.DataFrame,
    *,
    policy: dict[str, Any],
    release_id: str,
    instrument_id: str,
) -> ForwardPolicyEvaluation:
    direction = str(policy.get("direction", ""))
    rules = policy.get("rules")
    if direction not in {"long", "short"} or not isinstance(rules, list) or not rules:
        return ForwardPolicyEvaluation(None, "invalid_frozen_policy", {})
    ordered, factors = materialize_latest_factors(frame)
    evaluations: list[dict[str, Any]] = []
    passed = True
    for rule in rules:
        if not isinstance(rule, dict):
            return ForwardPolicyEvaluation(None, "invalid_frozen_policy", {})
        factor_id = str(rule.get("factorId", ""))
        operator = str(rule.get("operator", ""))
        if factor_id not in factors or operator not in _OPERATORS:
            return ForwardPolicyEvaluation(None, "invalid_frozen_policy", {})
        try:
            threshold = float(rule.get("threshold"))
        except (TypeError, ValueError):
            return ForwardPolicyEvaluation(None, "invalid_frozen_policy", {})
        value = factors[factor_id]
        matched = math.isfinite(value) and math.isfinite(threshold) and _OPERATORS[operator](
            value, threshold
        )
        evaluations.append(
            {
                "factorId": factor_id,
                "operator": operator,
                "threshold": threshold,
                "value": value if math.isfinite(value) else None,
                "matched": bool(matched),
            }
        )
        passed = passed and bool(matched)
    latest = ordered.iloc[-1]
    atr_pct = factors.get("atr_pct_14")
    context = {
        "timestampMs": int(latest["timestamp_ms"]),
        "rules": evaluations,
        "factorValues": {key: value if math.isfinite(value) else None for key, value in factors.items()},
    }
    if not passed:
        return ForwardPolicyEvaluation(None, "conditions_not_met", context)
    if atr_pct is None or not math.isfinite(atr_pct) or atr_pct <= 0:
        return ForwardPolicyEvaluation(None, "risk_distance_unavailable", context)
    risk_distance = float(latest["close"]) * atr_pct
    signal_id = stable_hash(
        {
            "forwardReleaseId": release_id,
            "instrumentId": instrument_id,
            "timestampMs": int(latest["timestamp_ms"]),
            "direction": direction,
            "rules": evaluations,
        },
        prefix="forward_signal",
    )
    return ForwardPolicyEvaluation(
        ForwardDecision(signal_id, direction, risk_distance, context),
        "signal",
        context,
    )
