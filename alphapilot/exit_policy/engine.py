"""Causal candle replay for preregistered Advisory-R exit policies."""

from __future__ import annotations

import math
from typing import Iterable

import numpy as np
import pandas as pd

from .canonical import exit_policy_hash
from .exit_legs import ExitCosts, ExitExecutionResult, ExitLeg
from .models import ExitPolicy, ExitPolicyMode
from .validation import validate_exit_policy


def _timestamp(frame: pd.DataFrame, position: int) -> str:
    return pd.Timestamp(frame.iloc[position]["date"]).isoformat()


def _series(
    value: pd.Series | Iterable[float] | None,
    *,
    length: int,
    name: str,
) -> pd.Series | None:
    if value is None:
        return None
    result = pd.Series(value).reset_index(drop=True)
    if len(result) != length:
        raise ValueError(f"{name} must align one-to-one with frame rows")
    return result


def _validate_costs(costs: ExitCosts) -> None:
    for name, value in (
        ("feeBpsPerSide", costs.feeBpsPerSide),
        ("slippageBpsPerSide", costs.slippageBpsPerSide),
        ("spreadBpsPerSide", costs.spreadBpsPerSide),
    ):
        if not math.isfinite(value) or value < 0:
            raise ValueError(f"{name} must be a finite non-negative number")


def _leg(
    *,
    frame: pd.DataFrame,
    entry_position: int,
    entry_price: float,
    risk_distance: float,
    direction_sign: int,
    fraction: float,
    reason: str,
    trigger_position: int,
    execution_position: int,
    price: float,
    costs: ExitCosts,
    funding_rate: pd.Series | None,
    is_gap_fill: bool = False,
    ambiguous_path: bool = False,
) -> ExitLeg:
    gross_r = direction_sign * (price - entry_price) / risk_distance * fraction
    price_scale = (entry_price + abs(price)) / risk_distance * fraction
    fees_r = price_scale * costs.feeBpsPerSide / 10_000
    slippage_r = price_scale * costs.slippageBpsPerSide / 10_000
    spread_r = price_scale * costs.spreadBpsPerSide / 10_000
    funding_r = 0.0
    if funding_rate is not None:
        rates = pd.to_numeric(
            funding_rate.iloc[entry_position : execution_position + 1],
            errors="coerce",
        ).dropna()
        funding_r = (
            float(rates.sum())
            * direction_sign
            * entry_price
            / risk_distance
            * fraction
        )
    net_r = gross_r - fees_r - slippage_r - spread_r - funding_r
    return ExitLeg(
        fraction=float(fraction),
        reason=reason,
        triggerPosition=trigger_position,
        executionPosition=execution_position,
        triggerTimestamp=_timestamp(frame, trigger_position),
        executionTimestamp=_timestamp(frame, execution_position),
        price=float(price),
        grossR=float(gross_r),
        feesR=float(fees_r),
        slippageR=float(slippage_r),
        spreadProxyR=float(spread_r),
        fundingR=float(funding_r),
        netR=float(net_r),
        isGapFill=is_gap_fill,
        ambiguousPath=ambiguous_path,
    )


def _target_price(entry: float, sign: int, risk: float, target_r: float) -> float:
    return entry + sign * risk * target_r


def replay_exit_policy(
    *,
    frame: pd.DataFrame,
    signalPosition: int,
    direction: str,
    riskDistance: float,
    policy: ExitPolicy,
    costs: ExitCosts,
    atrValues: pd.Series | Iterable[float] | None = None,
    structureExitMask: pd.Series | Iterable[bool] | None = None,
    fundingRate: pd.Series | Iterable[float] | None = None,
) -> ExitExecutionResult:
    validate_exit_policy(policy)
    _validate_costs(costs)
    if direction not in {"long", "short"}:
        raise ValueError("direction must be long or short")
    if not math.isfinite(riskDistance) or riskDistance <= 0:
        raise ValueError("riskDistance must be positive")
    required_columns = {"date", "open", "high", "low", "close"}
    missing = required_columns - set(frame.columns)
    if missing:
        raise ValueError(f"frame is missing columns: {sorted(missing)}")
    if not 0 <= signalPosition < len(frame) - 1:
        raise ValueError("signalPosition must have a following entry bar")

    ordered = frame.reset_index(drop=True)
    atr = _series(atrValues, length=len(ordered), name="atrValues")
    structure = _series(
        structureExitMask,
        length=len(ordered),
        name="structureExitMask",
    )
    funding = _series(fundingRate, length=len(ordered), name="fundingRate")
    if policy.mode in {ExitPolicyMode.PARTIAL_THEN_TRAILING} or (
        policy.mode is ExitPolicyMode.HYBRID
        and policy.parameters.get("remainderMode") == "trailing"
    ):
        if atr is None:
            raise ValueError("atrValues are required for trailing policies")
    if policy.mode is ExitPolicyMode.STRUCTURE_OR_TIME or (
        policy.mode is ExitPolicyMode.HYBRID
        and policy.parameters.get("remainderMode") == "structure"
    ):
        if structure is None:
            raise ValueError("structureExitMask is required for structure policies")

    entry_position = signalPosition + 1
    entry_price = float(ordered.iloc[entry_position]["open"])
    if not math.isfinite(entry_price) or entry_price <= 0:
        raise ValueError("entry price must be positive")
    direction_sign = 1 if direction == "long" else -1
    initial_stop = entry_price - direction_sign * riskDistance
    if initial_stop <= 0:
        raise ValueError("initial stop price must be positive")

    parameters = policy.parameters
    fixed_target = (
        _target_price(entry_price, direction_sign, riskDistance, float(parameters["targetR"]))
        if policy.mode is ExitPolicyMode.FIXED_R
        else None
    )
    has_partial = policy.mode in {
        ExitPolicyMode.PARTIAL_THEN_TRAILING,
        ExitPolicyMode.HYBRID,
    }
    partial_target = (
        _target_price(
            entry_price,
            direction_sign,
            riskDistance,
            float(parameters["partialAtR"]),
        )
        if has_partial
        else None
    )
    trailing = policy.mode is ExitPolicyMode.PARTIAL_THEN_TRAILING or (
        policy.mode is ExitPolicyMode.HYBRID
        and parameters.get("remainderMode") == "trailing"
    )
    structure_mode = policy.mode is ExitPolicyMode.STRUCTURE_OR_TIME or (
        policy.mode is ExitPolicyMode.HYBRID
        and parameters.get("remainderMode") == "structure"
    )

    active_stop = initial_stop
    pending_stop: float | None = None
    stop_history = [initial_stop]
    remaining = 1.0
    partial_taken = False
    legs: list[ExitLeg] = []
    ambiguous_path = False
    observed_high = entry_price
    observed_low = entry_price
    final_observation_position = entry_position
    final_scan_position = min(
        len(ordered) - 1,
        entry_position + policy.maximumHoldBars - 1,
    )

    for position in range(entry_position, final_scan_position + 1):
        row = ordered.iloc[position]
        open_price = float(row["open"])
        high = float(row["high"])
        low = float(row["low"])
        close = float(row["close"])
        if not all(math.isfinite(value) for value in (open_price, high, low, close)):
            raise ValueError("OHLC values must be finite")
        if pending_stop is not None:
            active_stop = pending_stop
            pending_stop = None
            if active_stop != stop_history[-1]:
                stop_history.append(active_stop)

        observed_high = max(observed_high, high)
        observed_low = min(observed_low, low)
        final_observation_position = position

        stop_gap = open_price <= active_stop if direction_sign == 1 else open_price >= active_stop
        if stop_gap:
            trailing_gap = position > entry_position and active_stop != initial_stop
            legs.append(
                _leg(
                    frame=ordered,
                    entry_position=entry_position,
                    entry_price=entry_price,
                    risk_distance=riskDistance,
                    direction_sign=direction_sign,
                    fraction=remaining,
                    reason=(
                        "trailing_gap"
                        if trailing_gap
                        else "stop_gap" if position > entry_position else "stop_loss"
                    ),
                    trigger_position=position,
                    execution_position=position,
                    price=open_price,
                    costs=costs,
                    funding_rate=funding,
                    is_gap_fill=position > entry_position,
                )
            )
            remaining = 0.0
            break

        fixed_target_gap = fixed_target is not None and (
            open_price >= fixed_target if direction_sign == 1 else open_price <= fixed_target
        )
        if fixed_target_gap:
            legs.append(
                _leg(
                    frame=ordered,
                    entry_position=entry_position,
                    entry_price=entry_price,
                    risk_distance=riskDistance,
                    direction_sign=direction_sign,
                    fraction=remaining,
                    reason="target_gap",
                    trigger_position=position,
                    execution_position=position,
                    price=float(fixed_target),
                    costs=costs,
                    funding_rate=funding,
                    is_gap_fill=True,
                )
            )
            remaining = 0.0
            break

        partial_target_gap = (
            has_partial
            and not partial_taken
            and partial_target is not None
            and (open_price >= partial_target if direction_sign == 1 else open_price <= partial_target)
        )
        if partial_target_gap:
            fraction = float(parameters["partialFraction"])
            legs.append(
                _leg(
                    frame=ordered,
                    entry_position=entry_position,
                    entry_price=entry_price,
                    risk_distance=riskDistance,
                    direction_sign=direction_sign,
                    fraction=fraction,
                    reason="partial_gap",
                    trigger_position=position,
                    execution_position=position,
                    price=float(partial_target),
                    costs=costs,
                    funding_rate=funding,
                    is_gap_fill=True,
                )
            )
            remaining -= fraction
            partial_taken = True

        stop_hit = low <= active_stop if direction_sign == 1 else high >= active_stop
        target = fixed_target if fixed_target is not None else (
            partial_target if has_partial and not partial_taken else None
        )
        target_hit = False
        if target is not None:
            target_hit = high >= target if direction_sign == 1 else low <= target
        if stop_hit:
            ambiguous = bool(target_hit)
            ambiguous_path = ambiguous_path or ambiguous
            reason = "trailing_stop" if active_stop != initial_stop else "stop_loss"
            legs.append(
                _leg(
                    frame=ordered,
                    entry_position=entry_position,
                    entry_price=entry_price,
                    risk_distance=riskDistance,
                    direction_sign=direction_sign,
                    fraction=remaining,
                    reason=reason,
                    trigger_position=position,
                    execution_position=position,
                    price=active_stop,
                    costs=costs,
                    funding_rate=funding,
                    ambiguous_path=ambiguous,
                )
            )
            remaining = 0.0
            break

        if fixed_target is not None and target_hit:
            legs.append(
                _leg(
                    frame=ordered,
                    entry_position=entry_position,
                    entry_price=entry_price,
                    risk_distance=riskDistance,
                    direction_sign=direction_sign,
                    fraction=remaining,
                    reason="target",
                    trigger_position=position,
                    execution_position=position,
                    price=fixed_target,
                    costs=costs,
                    funding_rate=funding,
                )
            )
            remaining = 0.0
            break

        if has_partial and not partial_taken and target_hit:
            fraction = float(parameters["partialFraction"])
            legs.append(
                _leg(
                    frame=ordered,
                    entry_position=entry_position,
                    entry_price=entry_price,
                    risk_distance=riskDistance,
                    direction_sign=direction_sign,
                    fraction=fraction,
                    reason="partial_target",
                    trigger_position=position,
                    execution_position=position,
                    price=float(partial_target),
                    costs=costs,
                    funding_rate=funding,
                )
            )
            remaining -= fraction
            partial_taken = True

        if structure_mode and bool(structure.iloc[position]):
            execution_position = position + 1
            if execution_position < len(ordered):
                exit_price = float(ordered.iloc[execution_position]["open"])
            else:
                execution_position = position
                exit_price = close
            legs.append(
                _leg(
                    frame=ordered,
                    entry_position=entry_position,
                    entry_price=entry_price,
                    risk_distance=riskDistance,
                    direction_sign=direction_sign,
                    fraction=remaining,
                    reason="structure_exit",
                    trigger_position=position,
                    execution_position=execution_position,
                    price=exit_price,
                    costs=costs,
                    funding_rate=funding,
                )
            )
            remaining = 0.0
            break

        if trailing and partial_taken:
            atr_value = float(atr.iloc[position])
            if not math.isfinite(atr_value) or atr_value <= 0:
                raise ValueError("trailing ATR values must be finite and positive")
            multiple = float(parameters["trailingAtrMultiple"])
            proposed = close - direction_sign * atr_value * multiple
            tightened = max(active_stop, proposed) if direction_sign == 1 else min(active_stop, proposed)
            if direction_sign == 1:
                tightened = max(initial_stop, tightened)
            else:
                tightened = min(initial_stop, tightened)
            if tightened != active_stop:
                pending_stop = tightened

        if position == final_scan_position and remaining > 0:
            execution_position = position + 1
            if execution_position < len(ordered):
                exit_price = float(ordered.iloc[execution_position]["open"])
            else:
                execution_position = position
                exit_price = close
            legs.append(
                _leg(
                    frame=ordered,
                    entry_position=entry_position,
                    entry_price=entry_price,
                    risk_distance=riskDistance,
                    direction_sign=direction_sign,
                    fraction=remaining,
                    reason="maximum_hold",
                    trigger_position=position,
                    execution_position=execution_position,
                    price=exit_price,
                    costs=costs,
                    funding_rate=funding,
                )
            )
            remaining = 0.0

    if not legs or remaining > 1e-10:
        raise RuntimeError("exit policy did not close the full position")
    fraction_sum = sum(leg.fraction for leg in legs)
    if not math.isclose(fraction_sum, 1.0, rel_tol=0, abs_tol=1e-10):
        raise RuntimeError(f"exit leg fractions must sum to one, got {fraction_sum}")

    gross_r = sum(leg.grossR for leg in legs)
    fees_r = sum(leg.feesR for leg in legs)
    slippage_r = sum(leg.slippageR for leg in legs)
    spread_r = sum(leg.spreadProxyR for leg in legs)
    funding_r = sum(leg.fundingR for leg in legs)
    net_r = sum(leg.netR for leg in legs)
    mfe_r = (
        (observed_high - entry_price) / riskDistance
        if direction_sign == 1
        else (entry_price - observed_low) / riskDistance
    )
    mae_r = (
        (observed_low - entry_price) / riskDistance
        if direction_sign == 1
        else (entry_price - observed_high) / riskDistance
    )
    exit_position = legs[-1].executionPosition
    return ExitExecutionResult(
        signalTimestamp=_timestamp(ordered, signalPosition),
        entryTimestamp=_timestamp(ordered, entry_position),
        exitTimestamp=_timestamp(ordered, exit_position),
        signalPosition=signalPosition,
        entryPosition=entry_position,
        exitPosition=exit_position,
        entryReference="next_bar_open",
        direction=direction,
        entryPrice=entry_price,
        initialStopPrice=initial_stop,
        riskDistance=float(riskDistance),
        exitPolicy=policy,
        exitPolicyHash=exit_policy_hash(policy),
        legs=tuple(legs),
        stopHistory=tuple(float(value) for value in stop_history),
        ambiguousPath=ambiguous_path,
        grossR=float(gross_r),
        feesR=float(fees_r),
        slippageR=float(slippage_r),
        spreadProxyR=float(spread_r),
        fundingR=float(funding_r),
        netR=float(net_r),
        mfeR=float(mfe_r),
        maeR=float(mae_r),
        givebackR=float(max(0.0, mfe_r - gross_r)),
    )
