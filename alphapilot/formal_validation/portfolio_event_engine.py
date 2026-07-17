"""Canonical same-timestamp portfolio event ordering for Capital Policy V2."""

from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

from .capacity_model import evaluate_capacity_v1
from .executable_capital_policy import ACCEPTANCE_SEQUENCE, accept_signal_batch_v2


EVENT_ORDER = ["exit", "funding", "mark_and_equity", "entry"]


def _instrument(row: Mapping[str, Any]) -> str:
    return str(row.get("instrumentId") or row.get("symbol") or "")


def _finite(value: object, label: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{label} must be finite")
    return number


def process_portfolio_timestamp_v2(
    *,
    timestamp: str,
    current_equity: float,
    open_positions: Sequence[Mapping[str, Any]],
    exits: Sequence[Mapping[str, Any]],
    funding: Sequence[Mapping[str, Any]],
    marks: Sequence[Mapping[str, Any]],
    entry_signals: Sequence[Mapping[str, Any]],
    policy: Mapping[str, Any],
) -> dict[str, Any]:
    """Apply all state changes in the frozen order, then size and rank entries."""

    equity = _finite(current_equity, "current_equity")
    if equity <= 0.0:
        raise ValueError("current_equity must be positive")
    positions = [dict(row) for row in open_positions]
    closed: list[dict[str, Any]] = []

    for event in sorted(exits, key=lambda row: _instrument(row)):
        instrument = _instrument(event)
        matches = [row for row in positions if _instrument(row) == instrument]
        if len(matches) != 1:
            raise ValueError(f"Exit must match exactly one open position: {instrument}")
        position = matches[0]
        remaining_before = _finite(
            position.get("remainingFraction", 1.0), "remainingFraction"
        )
        leg_fraction = _finite(
            event.get("legFraction", remaining_before), "exit legFraction"
        )
        if remaining_before <= 0.0 or leg_fraction <= 0.0:
            raise ValueError("Exit fractions must be positive")
        if leg_fraction > remaining_before + 1e-12:
            raise ValueError(
                f"Exit fraction exceeds remaining position: {instrument}"
            )
        remaining_after = max(0.0, remaining_before - leg_fraction)
        marked_unrealized = _finite(
            position.get("unrealizedPnl", 0.0), "position unrealizedPnl"
        )
        allocated_unrealized = marked_unrealized * leg_fraction / remaining_before
        equity += (
            _finite(event.get("netPnl"), "exit netPnl") - allocated_unrealized
        )
        position_closed = remaining_after <= 1e-12
        if position_closed:
            positions.remove(position)
        else:
            scale = remaining_after / remaining_before
            position["remainingFraction"] = remaining_after
            for field in (
                "riskAmount",
                "markNotional",
                "actualNotional",
                "quantity",
                "unrealizedPnl",
            ):
                if field in position:
                    position[field] = _finite(position[field], field) * scale
        closed.append(
            {
                **dict(event),
                "instrumentId": instrument,
                "positionClosed": position_closed,
                "remainingFractionBefore": remaining_before,
                "remainingFractionAfter": remaining_after,
                "replacedMarkedUnrealizedPnl": allocated_unrealized,
            }
        )

    for event in funding:
        equity += _finite(event.get("amount"), "funding amount")

    for event in marks:
        instrument = _instrument(event)
        if not instrument:
            equity += _finite(event.get("equityDelta"), "mark equityDelta")
            continue
        matches = [row for row in positions if _instrument(row) == instrument]
        if len(matches) != 1:
            raise ValueError(f"Mark must match exactly one open position: {instrument}")
        position = matches[0]
        previous_unrealized = _finite(
            position.get("unrealizedPnl", 0.0), "position unrealizedPnl"
        )
        if event.get("unrealizedPnl") is not None:
            new_unrealized = _finite(
                event.get("unrealizedPnl"), "mark unrealizedPnl"
            )
            equity_delta = new_unrealized - previous_unrealized
        else:
            equity_delta = _finite(event.get("equityDelta"), "mark equityDelta")
            new_unrealized = previous_unrealized + equity_delta
        equity += equity_delta
        position["unrealizedPnl"] = new_unrealized
        position["markNotional"] = _finite(
            event.get("markNotional"), "mark markNotional"
        )

    prepared: list[dict[str, Any]] = []
    pre_rejected: list[dict[str, Any]] = []
    required = ("entryPrice", "stopPrice", "dailyLiquidity")
    for raw in entry_signals:
        row = dict(raw)
        if any(key not in row for key in required):
            pre_rejected.append({**row, "reason": "missing_capacity_input"})
            continue
        capacity = evaluate_capacity_v1(
            current_equity=equity,
            entry_price=row["entryPrice"],
            stop_price=row["stopPrice"],
            entry_timestamp=timestamp,
            daily_liquidity=row["dailyLiquidity"],
            instrument_meta=row.get("instrumentMeta") or {},
        )
        prepared.append({**row, **capacity})

    acceptance = accept_signal_batch_v2(
        prepared,
        open_positions=positions,
        current_equity=equity,
        policy=policy,
    )
    accepted = [dict(row) for row in acceptance["accepted"]]
    positions.extend(accepted)
    return {
        "schemaVersion": "s01_portfolio_timestamp_engine_v2",
        "timestamp": timestamp,
        "currentEquity": equity,
        "closedPositions": closed,
        "acceptedEntries": accepted,
        "rejectedEntries": [*pre_rejected, *acceptance["rejected"]],
        "openPositions": positions,
        "eventOrder": list(EVENT_ORDER),
        "audit": {
            "sameTimestampOrder": list(EVENT_ORDER),
            "entryAcceptanceSequence": list(ACCEPTANCE_SEQUENCE),
            "capacitySizedAfterPriorStateUpdates": True,
            "lookaheadReadCount": 0,
        },
    }
