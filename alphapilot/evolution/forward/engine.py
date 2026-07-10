"""Deterministic next-bar virtual accounting for real-time local forward bars."""

from __future__ import annotations

import math
from dataclasses import asdict, replace
from typing import Any

from alphapilot.evolution.registry.hashing import stable_hash

from .types import (
    TIMEFRAME_MILLISECONDS,
    ForwardBar,
    ForwardDecision,
    ForwardRiskEnvelope,
    ForwardState,
    ForwardTransition,
    PendingForwardSignal,
    VirtualForwardPosition,
)


def _event(event_type: str, bar: ForwardBar, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "eventType": event_type,
        "instrumentId": bar.instrumentId,
        "observedAtMs": bar.timestampMs,
        "payload": payload,
    }


def _validate_bar(bar: ForwardBar) -> None:
    if bar.timeframe not in TIMEFRAME_MILLISECONDS:
        raise ValueError(f"Unsupported forward timeframe: {bar.timeframe}")
    values = (bar.open, bar.high, bar.low, bar.close, bar.volume)
    if not all(math.isfinite(value) for value in values):
        raise ValueError("Forward bar contains non-finite values")
    if min(bar.open, bar.high, bar.low, bar.close) <= 0 or bar.volume < 0:
        raise ValueError("Forward bar prices must be positive and volume non-negative")
    if bar.high < max(bar.open, bar.close) or bar.low > min(bar.open, bar.close):
        raise ValueError("Forward OHLC bounds are invalid")


def _mark_equity(state: ForwardState) -> None:
    unrealized = 0.0
    for position in state.openPositions.values():
        sign = 1.0 if position.direction == "long" else -1.0
        unrealized += sign * (position.markPrice - position.entryFillPrice) * position.quantity
    state.equity = state.cashBalance + unrealized
    state.peakEquity = max(state.peakEquity, state.equity)
    if state.peakEquity > 0:
        drawdown = (state.peakEquity - state.equity) / state.peakEquity * 100.0
        state.maxDrawdownPercent = max(state.maxDrawdownPercent, drawdown)


def _open_pending(
    state: ForwardState,
    pending: PendingForwardSignal,
    bar: ForwardBar,
    envelope: ForwardRiskEnvelope,
) -> tuple[VirtualForwardPosition | None, dict[str, Any]]:
    direction_sign = 1.0 if pending.direction == "long" else -1.0
    entry_fill = bar.open * (1.0 + direction_sign * envelope.slippageRate)
    risk_budget = state.equity * envelope.riskPerTradePercent / 100.0
    quantity_by_risk = risk_budget / pending.riskDistance
    quantity_by_notional = envelope.maxOrderNotionalUsdt / entry_fill
    quantity = min(quantity_by_risk, quantity_by_notional)
    if not math.isfinite(quantity) or quantity <= 0:
        return None, {"reason": "invalid_virtual_quantity", "signalId": pending.signalId}
    risk_amount = pending.riskDistance * quantity
    current_open_risk = sum(position.riskAmountUsdt for position in state.openPositions.values())
    max_open_risk = state.equity * envelope.maxOpenRiskPercent / 100.0
    if current_open_risk + risk_amount > max_open_risk + 1e-9:
        return None, {"reason": "virtual_open_risk_limit", "signalId": pending.signalId}
    entry_fee = entry_fill * quantity * envelope.feeRate
    entry_slippage = abs(entry_fill - bar.open) * quantity
    state.cashBalance -= entry_fee
    state.totalFeesPaid += entry_fee
    state.totalSlippagePaid += entry_slippage
    position = VirtualForwardPosition(
        positionId=stable_hash(
            {"session": state.forwardSessionId, "signal": pending.signalId, "entry": bar.timestampMs},
            prefix="forward_position",
        ),
        signalId=pending.signalId,
        instrumentId=pending.instrumentId,
        timeframe=pending.timeframe,
        direction=pending.direction,
        decisionTimestampMs=pending.decisionTimestampMs,
        entryTimestampMs=bar.timestampMs,
        entryBasePrice=bar.open,
        entryFillPrice=entry_fill,
        quantity=quantity,
        riskDistance=pending.riskDistance,
        riskAmountUsdt=risk_amount,
        stopPrice=entry_fill - direction_sign * pending.riskDistance,
        targetPrice=entry_fill + direction_sign * pending.riskDistance * envelope.rewardRiskRatio,
        entryFeePaid=entry_fee,
        entrySlippagePaid=entry_slippage,
        markPrice=bar.close,
        factorContext=pending.factorContext,
    )
    return position, {"position": asdict(position), "createsOrder": False}


def _exit_position(
    state: ForwardState,
    position: VirtualForwardPosition,
    bar: ForwardBar,
    envelope: ForwardRiskEnvelope,
) -> tuple[VirtualForwardPosition | None, dict[str, Any] | None]:
    if position.direction == "long":
        stop_touched = bar.low <= position.stopPrice
        target_touched = bar.high >= position.targetPrice
    else:
        stop_touched = bar.high >= position.stopPrice
        target_touched = bar.low <= position.targetPrice
    if not stop_touched and not target_touched:
        return replace(position, markPrice=bar.close), None
    same_bar_ambiguous = stop_touched and target_touched
    exit_reason = "stop" if stop_touched else "target"
    exit_base = position.stopPrice if stop_touched else position.targetPrice
    direction_sign = 1.0 if position.direction == "long" else -1.0
    exit_fill = exit_base * (1.0 - direction_sign * envelope.slippageRate)
    gross_pnl = direction_sign * (exit_fill - position.entryFillPrice) * position.quantity
    exit_fee = exit_fill * position.quantity * envelope.feeRate
    exit_slippage = abs(exit_fill - exit_base) * position.quantity
    net_pnl = gross_pnl - position.entryFeePaid - exit_fee
    state.cashBalance += gross_pnl - exit_fee
    state.realizedPnl += net_pnl
    state.totalFeesPaid += exit_fee
    state.totalSlippagePaid += exit_slippage
    state.closedOutcomeCount += 1
    outcome = {
        "schemaVersion": "realtime_local_forward_outcome_v1",
        "evidenceClass": "realtime_local_forward",
        "positionId": position.positionId,
        "signalId": position.signalId,
        "instrumentId": position.instrumentId,
        "timeframe": position.timeframe,
        "direction": position.direction,
        "decisionTimestampMs": position.decisionTimestampMs,
        "entryTimestampMs": position.entryTimestampMs,
        "exitTimestampMs": bar.timestampMs,
        "entryBasePrice": position.entryBasePrice,
        "entryFillPrice": position.entryFillPrice,
        "exitBasePrice": exit_base,
        "exitFillPrice": exit_fill,
        "quantity": position.quantity,
        "riskAmountUsdt": position.riskAmountUsdt,
        "grossPnlUsdt": gross_pnl,
        "netPnlUsdt": net_pnl,
        "netR": net_pnl / position.riskAmountUsdt,
        "entryFeePaid": position.entryFeePaid,
        "exitFeePaid": exit_fee,
        "slippagePaid": position.entrySlippagePaid + exit_slippage,
        "exitReason": exit_reason,
        "sameBarAmbiguousStopFirst": same_bar_ambiguous,
        "factorContext": position.factorContext,
        "publicMarketOnly": True,
        "createsOrder": False,
    }
    return None, outcome


def process_completed_bar(
    state: ForwardState,
    bar: ForwardBar,
    *,
    envelope: ForwardRiskEnvelope | None = None,
    decision: ForwardDecision | None = None,
) -> ForwardTransition:
    """Advance one instrument using only the newly observed completed bar."""

    settings = envelope or ForwardRiskEnvelope()
    settings.validate()
    _validate_bar(bar)
    working = ForwardState.from_dict(state.to_dict())
    events: list[dict[str, Any]] = []
    outcomes: list[dict[str, Any]] = []
    last_observed = working.lastObservedByInstrument.get(bar.instrumentId)
    if last_observed is not None and bar.timestampMs <= last_observed:
        events.append(
            _event(
                "bar_rejected",
                bar,
                {"reason": "duplicate_or_out_of_order_bar", "lastObservedMs": last_observed},
            )
        )
        return ForwardTransition(working, tuple(events), ())
    interval = TIMEFRAME_MILLISECONDS[bar.timeframe]
    if last_observed is not None and bar.timestampMs > last_observed + interval:
        missing_bars = (bar.timestampMs - last_observed) // interval - 1
        events.append(
            _event(
                "collection_gap",
                bar,
                {
                    "gapStartExclusiveMs": last_observed,
                    "gapEndExclusiveMs": bar.timestampMs,
                    "missingBars": int(missing_bars),
                    "backfilledAsForwardEvidence": False,
                },
            )
        )

    pending = working.pendingSignals.pop(bar.instrumentId, None)
    if pending is not None:
        if bar.instrumentId in working.openPositions:
            events.append(_event("signal_rejected", bar, {"reason": "position_already_open"}))
        elif len(working.openPositions) >= settings.maxConcurrentPositions:
            events.append(_event("signal_rejected", bar, {"reason": "concurrency_limit"}))
        else:
            opened, payload = _open_pending(working, pending, bar, settings)
            if opened is None:
                events.append(_event("signal_rejected", bar, payload))
            else:
                working.openPositions[bar.instrumentId] = opened
                events.append(_event("position_opened", bar, payload))

    position = working.openPositions.get(bar.instrumentId)
    if position is not None:
        marked, outcome = _exit_position(working, position, bar, settings)
        if marked is None:
            del working.openPositions[bar.instrumentId]
            assert outcome is not None
            outcomes.append(outcome)
            events.append(_event("position_closed", bar, outcome))
        else:
            working.openPositions[bar.instrumentId] = marked
            events.append(
                _event(
                    "position_marked",
                    bar,
                    {"positionId": marked.positionId, "markPrice": marked.markPrice},
                )
            )

    if decision is not None:
        if decision.direction not in {"long", "short"}:
            events.append(_event("signal_rejected", bar, {"reason": "invalid_direction"}))
        elif not math.isfinite(decision.riskDistance) or decision.riskDistance <= 0:
            events.append(_event("signal_rejected", bar, {"reason": "invalid_risk_distance"}))
        elif bar.instrumentId in working.openPositions or bar.instrumentId in working.pendingSignals:
            events.append(_event("signal_rejected", bar, {"reason": "instrument_busy"}))
        else:
            pending_signal = PendingForwardSignal(
                signalId=decision.signalId,
                instrumentId=bar.instrumentId,
                timeframe=bar.timeframe,
                direction=decision.direction,
                decisionTimestampMs=bar.timestampMs,
                riskDistance=decision.riskDistance,
                factorContext=decision.factorContext,
            )
            working.pendingSignals[bar.instrumentId] = pending_signal
            events.append(
                _event(
                    "signal_observed",
                    bar,
                    {"signal": asdict(pending_signal), "nextBarVirtualFillOnly": True},
                )
            )
    else:
        events.append(_event("decision_observed", bar, {"signal": False}))

    working.lastObservedByInstrument[bar.instrumentId] = bar.timestampMs
    _mark_equity(working)
    events.append(
        _event(
            "bar_observed",
            bar,
            {
                "close": bar.close,
                "equity": working.equity,
                "openPositionCount": len(working.openPositions),
                "pendingSignalCount": len(working.pendingSignals),
                "publicMarketOnly": True,
            },
        )
    )
    return ForwardTransition(working, tuple(events), tuple(outcomes))
