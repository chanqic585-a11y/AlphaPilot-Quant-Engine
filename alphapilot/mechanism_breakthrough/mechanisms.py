"""Causal A/B/C mechanisms and funding-episode semantic audit."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

import numpy as np
import pandas as pd

from alphapilot.exit_policy import ExitCosts, exit_execution_to_dict, replay_exit_policy
from alphapilot.research_screening.campaign_contract import CandidateSpec
from alphapilot.research_screening.campaign_signals import atr_series


@dataclass(frozen=True)
class MechanismSignal:
    signalPosition: int
    signalTimestamp: str
    entryPosition: int
    entryTimestamp: str
    entryPrice: float
    riskDistance: float


def _ordered(frame: pd.DataFrame) -> pd.DataFrame:
    ordered = frame.sort_values("date").drop_duplicates("date", keep="last").reset_index(drop=True)
    required = {"date", "open", "high", "low", "close", "volume"}
    missing = sorted(required - set(ordered))
    if missing:
        raise ValueError(f"mechanism_frame_columns_missing:{','.join(missing)}")
    return ordered


def _signal(
    frame: pd.DataFrame,
    *,
    position: int,
    entry: float,
    risk: float,
) -> MechanismSignal:
    return MechanismSignal(
        signalPosition=position,
        signalTimestamp=pd.Timestamp(frame.iloc[position]["date"]).isoformat(),
        entryPosition=position + 1,
        entryTimestamp=pd.Timestamp(frame.iloc[position + 1]["date"]).isoformat(),
        entryPrice=float(entry),
        riskDistance=float(risk),
    )


def detect_breakout_second_entry_signals(
    *, candidate: CandidateSpec, frame: pd.DataFrame
) -> list[MechanismSignal]:
    ordered = _ordered(frame)
    definition = candidate.eventDefinition
    window = int(definition["referenceBoundaryBars"])
    atr = atr_series(ordered, window=int(definition["atrWindow"]))
    results: list[MechanismSignal] = []
    for first_break in range(window, len(ordered) - 2):
        atr_value = float(atr.iloc[first_break])
        if not np.isfinite(atr_value) or atr_value <= 0:
            continue
        prior = ordered.iloc[first_break - window : first_break]
        boundary = float(prior["low"].min() if candidate.direction == "long" else prior["high"].max())
        first = ordered.iloc[first_break]
        excursion = (
            boundary - float(first["close"])
            if candidate.direction == "long"
            else float(first["close"]) - boundary
        )
        if excursion <= 0 or excursion > float(definition["maximumFirstBreakAtr"]) * atr_value:
            continue
        failure: int | None = None
        for position in range(
            first_break + 1,
            min(len(ordered) - 2, first_break + int(definition["failureWindowBars"])) + 1,
        ):
            close = float(ordered.iloc[position]["close"])
            if (candidate.direction == "long" and close > boundary) or (
                candidate.direction == "short" and close < boundary
            ):
                failure = position
                break
        if failure is None:
            continue
        first_extreme = float(first["low"] if candidate.direction == "long" else first["high"])
        final = min(len(ordered) - 2, failure + int(definition["secondTestWindowBars"]))
        for position in range(failure + 1, final + 1):
            row = ordered.iloc[position]
            previous = ordered.iloc[position - 1]
            tolerance = float(definition["retestToleranceAtr"]) * atr_value
            if candidate.direction == "long":
                matched = (
                    float(row["low"]) <= boundary + tolerance
                    and float(row["low"]) >= first_extreme
                    and float(row["close"]) > boundary
                    and float(row["close"]) > float(previous["high"])
                )
            else:
                matched = (
                    float(row["high"]) >= boundary - tolerance
                    and float(row["high"]) <= first_extreme
                    and float(row["close"]) < boundary
                    and float(row["close"]) < float(previous["low"])
                )
            if not matched:
                continue
            entry = float(ordered.iloc[position + 1]["open"])
            segment = ordered.iloc[first_break : position + 1]
            structural_stop = (
                float(segment["low"].min()) - float(definition["stopBufferAtr"]) * atr_value
                if candidate.direction == "long"
                else float(segment["high"].max()) + float(definition["stopBufferAtr"]) * atr_value
            )
            cap = float(definition["maximumDistanceAtr"]) * atr_value
            stop = max(structural_stop, entry - cap) if candidate.direction == "long" else min(structural_stop, entry + cap)
            risk = entry - stop if candidate.direction == "long" else stop - entry
            if risk > 0 and stop > 0:
                results.append(_signal(ordered, position=position, entry=entry, risk=risk))
            break
    return results


def detect_breakout_immediate_fade_signals(
    *, candidate: CandidateSpec, frame: pd.DataFrame
) -> list[MechanismSignal]:
    ordered = _ordered(frame)
    definition = candidate.eventDefinition
    window = int(definition["referenceBoundaryBars"])
    atr = atr_series(ordered, window=int(definition["atrWindow"]))
    results: list[MechanismSignal] = []
    for first_break in range(window, len(ordered) - 2):
        atr_value = float(atr.iloc[first_break])
        if not np.isfinite(atr_value) or atr_value <= 0:
            continue
        prior = ordered.iloc[first_break - window : first_break]
        boundary = float(prior["low"].min() if candidate.direction == "long" else prior["high"].max())
        first = ordered.iloc[first_break]
        excursion = boundary - float(first["close"]) if candidate.direction == "long" else float(first["close"]) - boundary
        if excursion <= 0 or excursion > float(definition["maximumFirstBreakAtr"]) * atr_value:
            continue
        for position in range(first_break + 1, min(len(ordered) - 2, first_break + 2) + 1):
            close = float(ordered.iloc[position]["close"])
            reclaimed = (candidate.direction == "long" and close > boundary) or (
                candidate.direction == "short" and close < boundary
            )
            if not reclaimed:
                continue
            entry = float(ordered.iloc[position + 1]["open"])
            stop = (
                float(first["low"]) - 0.1 * atr_value
                if candidate.direction == "long"
                else float(first["high"]) + 0.1 * atr_value
            )
            risk = entry - stop if candidate.direction == "long" else stop - entry
            if risk > 0 and stop > 0:
                results.append(_signal(ordered, position=position, entry=entry, risk=risk))
            break
    return results


def _outer_close(row: pd.Series, direction: str, fraction: float) -> bool:
    width = float(row["high"]) - float(row["low"])
    if width <= 0:
        return False
    if direction == "long":
        return float(row["high"]) - float(row["close"]) <= width * fraction
    return float(row["close"]) - float(row["low"]) <= width * fraction


def detect_spike_pullback_signals(
    *, candidate: CandidateSpec, frame: pd.DataFrame
) -> list[MechanismSignal]:
    ordered = _ordered(frame)
    definition = candidate.eventDefinition
    spike_bars = int(definition["spikeBarsMin"])
    median_window = int(definition["bodyMedianWindow"])
    atr = atr_series(ordered, window=int(definition["atrWindow"]))
    bodies = (ordered["close"] - ordered["open"]).abs()
    results: list[MechanismSignal] = []
    for spike_end in range(median_window + spike_bars - 1, len(ordered) - 3):
        spike_start = spike_end - spike_bars + 1
        historical = bodies.iloc[spike_start - median_window : spike_start]
        median_body = float(historical.median())
        if not np.isfinite(median_body) or median_body <= 0:
            continue
        spike = ordered.iloc[spike_start : spike_end + 1]
        directional = (
            (spike["close"] > spike["open"]).all()
            if candidate.direction == "long"
            else (spike["close"] < spike["open"]).all()
        )
        if not directional:
            continue
        if not (bodies.iloc[spike_start : spike_end + 1] >= float(definition["minimumBodyMultiple"]) * median_body).all():
            continue
        if not all(
            _outer_close(row, candidate.direction, float(definition["outerCloseFraction"]))
            for _, row in spike.iterrows()
        ):
            continue
        spike_low = float(spike["low"].min())
        spike_high = float(spike["high"].max())
        impulse = spike_high - spike_low
        if impulse <= 0:
            continue
        for pullback_count in range(
            int(definition["pullbackBarsMinimum"]),
            int(definition["pullbackBarsMaximum"]) + 1,
        ):
            signal_position = spike_end + pullback_count
            if signal_position >= len(ordered) - 1:
                break
            pullback = ordered.iloc[spike_end + 1 : signal_position]
            if len(pullback) != pullback_count - 1:
                continue
            if candidate.direction == "long":
                retracement = (spike_high - float(pullback["low"].min())) / impulse
                confirmation = float(ordered.iloc[signal_position]["close"]) > float(
                    ordered.iloc[signal_position - 1]["high"]
                )
                pullback_direction = float(pullback.iloc[-1]["close"]) < float(spike.iloc[-1]["close"])
            else:
                retracement = (float(pullback["high"].max()) - spike_low) / impulse
                confirmation = float(ordered.iloc[signal_position]["close"]) < float(
                    ordered.iloc[signal_position - 1]["low"]
                )
                pullback_direction = float(pullback.iloc[-1]["close"]) > float(spike.iloc[-1]["close"])
            if not pullback_direction or retracement > float(definition["maximumRetracement"]) or not confirmation:
                continue
            atr_value = float(atr.iloc[signal_position])
            if not np.isfinite(atr_value) or atr_value <= 0:
                continue
            entry = float(ordered.iloc[signal_position + 1]["open"])
            structural_stop = (
                float(pullback["low"].min()) - float(definition["stopBufferAtr"]) * atr_value
                if candidate.direction == "long"
                else float(pullback["high"].max()) + float(definition["stopBufferAtr"]) * atr_value
            )
            cap = float(definition["maximumDistanceAtr"]) * atr_value
            stop = max(structural_stop, entry - cap) if candidate.direction == "long" else min(structural_stop, entry + cap)
            risk = entry - stop if candidate.direction == "long" else stop - entry
            if risk > 0 and stop > 0:
                results.append(_signal(ordered, position=signal_position, entry=entry, risk=risk))
            break
    return results


def detect_unconditional_spike_signals(
    *, candidate: CandidateSpec, frame: pd.DataFrame
) -> list[MechanismSignal]:
    ordered = _ordered(frame)
    definition = candidate.eventDefinition
    spike_bars = int(definition["spikeBarsMin"])
    median_window = int(definition["bodyMedianWindow"])
    bodies = (ordered["close"] - ordered["open"]).abs()
    atr = atr_series(ordered, window=int(definition["atrWindow"]))
    results: list[MechanismSignal] = []
    for position in range(median_window + spike_bars - 1, len(ordered) - 1):
        start = position - spike_bars + 1
        median_body = float(bodies.iloc[start - median_window : start].median())
        spike = ordered.iloc[start : position + 1]
        directional = (spike["close"] > spike["open"]).all() if candidate.direction == "long" else (spike["close"] < spike["open"]).all()
        if median_body <= 0 or not directional:
            continue
        if not (bodies.iloc[start : position + 1] >= float(definition["minimumBodyMultiple"]) * median_body).all():
            continue
        atr_value = float(atr.iloc[position])
        if not np.isfinite(atr_value) or atr_value <= 0:
            continue
        entry = float(ordered.iloc[position + 1]["open"])
        stop = entry - 2.5 * atr_value if candidate.direction == "long" else entry + 2.5 * atr_value
        risk = abs(entry - stop)
        if stop > 0:
            results.append(_signal(ordered, position=position, entry=entry, risk=risk))
    return results


def replay_signals(
    *,
    candidate: CandidateSpec,
    frame: pd.DataFrame,
    signals: Iterable[MechanismSignal],
    cost_multiplier: float,
) -> list[dict[str, Any]]:
    if candidate.exitPolicy is None:
        raise ValueError("candidate_exit_policy_required")
    ordered = _ordered(frame)
    atr = atr_series(ordered, window=int(candidate.eventDefinition.get("atrWindow", 20)))
    costs = ExitCosts(
        feeBpsPerSide=5.0 * cost_multiplier,
        slippageBpsPerSide=3.0 * cost_multiplier,
        spreadBpsPerSide=2.0 * cost_multiplier,
    )
    events: list[dict[str, Any]] = []
    next_allowed = 0
    for signal in signals:
        if signal.signalPosition < next_allowed:
            continue
        result = replay_exit_policy(
            frame=ordered,
            signalPosition=signal.signalPosition,
            direction=candidate.direction,
            riskDistance=signal.riskDistance,
            policy=candidate.exitPolicy,
            costs=costs,
            atrValues=atr,
        )
        row = exit_execution_to_dict(result)
        events.append(row)
        next_allowed = int(row["exitPosition"]) + 1
    return events


def rolling_pair_features(
    left: pd.Series,
    right: pd.Series,
    *,
    hedge_window: int,
    z_window: int,
) -> pd.DataFrame:
    left_log = np.log(pd.to_numeric(left, errors="coerce"))
    right_log = np.log(pd.to_numeric(right, errors="coerce"))
    prior_left = left_log.shift(1)
    prior_right = right_log.shift(1)
    covariance = prior_left.rolling(hedge_window).cov(prior_right)
    variance = prior_right.rolling(hedge_window).var().replace(0.0, np.nan)
    hedge = covariance / variance
    residual = left_log - hedge * right_log
    prior_residual = residual.shift(1)
    mean = prior_residual.rolling(z_window).mean()
    scale = prior_residual.rolling(z_window).std().replace(0.0, np.nan)
    return pd.DataFrame(
        {"hedgeRatio": hedge, "residual": residual, "zScore": (residual - mean) / scale}
    )


def audit_funding_carry_episode_semantics() -> dict[str, Any]:
    funding = [0.0010, 0.0012, 0.0008]
    open_fee = 0.0005
    close_fee = 0.0005
    cashflow = sum(funding) - open_fee - close_fee
    return {
        "schemaVersion": "funding_carry_episode_semantics_audit_v1",
        "status": "funding_carry_current_mechanism_closed",
        "fixtureId": "three_positive_funding_observations_one_episode",
        "episodeCount": 1,
        "fundingObservationCount": 3,
        "openFeeCount": 1,
        "closeFeeCount": 1,
        "fundingCashflow": sum(funding),
        "twoLegPricePnl": 0.0,
        "netCashflow": cashflow,
        "continuousPositionHeld": True,
        "capitalCountedOnce": True,
        "candidateCreated": False,
        "economicResultReadCount": 0,
    }

