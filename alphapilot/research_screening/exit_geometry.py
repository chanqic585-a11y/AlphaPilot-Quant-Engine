"""Frozen-risk event exit geometry with no stop widening."""

from __future__ import annotations

from typing import Any


def build_event_exit_geometry(
    *,
    direction: str,
    entry_price: float,
    initial_stop_price: float,
    remaining_target_r: float,
    partial_at_one_r: bool,
) -> dict[str, Any]:
    if direction not in {"long", "short"}:
        raise ValueError("portfolio strategies cannot use a single-symbol R target")
    if entry_price <= 0 or initial_stop_price <= 0:
        raise ValueError("prices must be positive")
    if remaining_target_r <= 0:
        raise ValueError("remaining directional target must be positive in R units")
    if direction == "long" and initial_stop_price >= entry_price:
        raise ValueError("long stop must be below entry")
    if direction == "short" and initial_stop_price <= entry_price:
        raise ValueError("short stop must be above entry")
    risk_distance = abs(entry_price - initial_stop_price)
    sign = 1.0 if direction == "long" else -1.0
    return {
        "schemaVersion": "event_exit_geometry_v2",
        "direction": direction,
        "entryPrice": entry_price,
        "initialStopPrice": initial_stop_price,
        "riskDistance": risk_distance,
        "partialAtOneR": partial_at_one_r,
        "oneRPrice": entry_price + sign * risk_distance,
        "remainingTargetR": remaining_target_r,
        "remainingTargetPrice": entry_price + sign * risk_distance * remaining_target_r,
        "initialStopMayWiden": False,
    }


def position_size_for_frozen_risk(
    risk_amount: float,
    entry_price: float,
    initial_stop_price: float,
) -> float:
    distance = abs(entry_price - initial_stop_price)
    if risk_amount <= 0 or distance <= 0:
        raise ValueError("risk amount and stop distance must be positive")
    return risk_amount / distance


def validate_stop_update(direction: str, current_stop: float, proposed_stop: float) -> bool:
    if direction == "long" and proposed_stop < current_stop:
        raise ValueError("long stop update would widen initial risk")
    if direction == "short" and proposed_stop > current_stop:
        raise ValueError("short stop update would widen initial risk")
    if direction not in {"long", "short"}:
        raise ValueError("unknown event direction")
    return True
