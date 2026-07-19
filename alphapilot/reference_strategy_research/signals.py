"""Causal signal and Advisory-R replay for selected reference hypotheses."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import numpy as np
import pandas as pd

from alphapilot.exit_policy import ExitCosts, exit_execution_to_dict, replay_exit_policy
from alphapilot.research_screening.campaign_contract import CandidateSpec
from alphapilot.research_screening.campaign_signals import atr_series


def _costs(payload: dict[str, float]) -> ExitCosts:
    return ExitCosts(
        feeBpsPerSide=float(payload.get("feeBpsPerSide", 0.0)),
        slippageBpsPerSide=float(payload.get("slippageBpsPerSide", 0.0)),
        spreadBpsPerSide=float(payload.get("spreadProxyBpsPerSide", 0.0)),
    )


def _valid_atr(atr: pd.Series, position: int) -> float | None:
    value = float(atr.iloc[position])
    return value if np.isfinite(value) and value > 0 else None


def _session_signals(
    candidate: CandidateSpec,
    frame: pd.DataFrame,
    atr: pd.Series,
) -> Iterable[tuple[int, float, pd.Series]]:
    definition = candidate.eventDefinition
    range_bars = int(definition["rangeBars"])
    breakout_window = int(definition["breakoutWindowBars"])
    anchor_hour = int(definition["sessionAnchorUtcHour"])
    timestamps = pd.to_datetime(frame["date"], utc=True)
    anchor_positions = np.flatnonzero(timestamps.dt.hour.eq(anchor_hour).to_numpy())
    for anchor in anchor_positions:
        if anchor < range_bars or anchor >= len(frame) - 1:
            continue
        atr_value = _valid_atr(atr, int(anchor))
        if atr_value is None:
            continue
        frozen = frame.iloc[anchor - range_bars : anchor]
        range_high = float(frozen["high"].max())
        range_low = float(frozen["low"].min())
        width_atr = (range_high - range_low) / atr_value
        if not float(definition["minimumRangeAtr"]) <= width_atr <= float(
            definition["maximumRangeAtr"]
        ):
            continue
        buffer = float(definition["breakoutBufferAtr"]) * atr_value
        final = min(len(frame) - 2, int(anchor) + breakout_window - 1)
        for position in range(int(anchor), final + 1):
            close = float(frame.iloc[position]["close"])
            matched = (
                close > range_high + buffer
                if candidate.direction == "long"
                else close < range_low - buffer
            )
            if not matched:
                continue
            entry = float(frame.iloc[position + 1]["open"])
            maximum_risk = float(definition["maximumStopAtr"]) * atr_value
            stop = (
                max(range_low, entry - maximum_risk)
                if candidate.direction == "long"
                else min(range_high, entry + maximum_risk)
            )
            risk = entry - stop if candidate.direction == "long" else stop - entry
            if not np.isfinite(risk) or risk <= 0 or stop <= 0:
                break
            midpoint = (range_high + range_low) / 2.0
            structure = (
                pd.to_numeric(frame["close"], errors="coerce").le(midpoint)
                if candidate.direction == "long"
                else pd.to_numeric(frame["close"], errors="coerce").ge(midpoint)
            )
            yield position, float(risk), structure.fillna(False).astype(bool)
            break


def _second_entry_signals(
    candidate: CandidateSpec,
    frame: pd.DataFrame,
    atr: pd.Series,
) -> Iterable[tuple[int, float, None]]:
    definition = candidate.eventDefinition
    window = int(definition["boundaryWindowBars"])
    failure_window = int(definition["failureWindowBars"])
    retest_window = int(definition["retestWindowBars"])
    for first_break in range(window, len(frame) - 2):
        atr_value = _valid_atr(atr, first_break)
        if atr_value is None:
            continue
        prior = frame.iloc[first_break - window : first_break]
        boundary = (
            float(prior["low"].min())
            if candidate.direction == "long"
            else float(prior["high"].max())
        )
        row = frame.iloc[first_break]
        excursion = (
            boundary - float(row["low"])
            if candidate.direction == "long"
            else float(row["high"]) - boundary
        )
        closes_outside = (
            float(row["close"]) < boundary
            if candidate.direction == "long"
            else float(row["close"]) > boundary
        )
        if excursion <= 0 or not closes_outside:
            continue
        if excursion > float(definition["maximumFirstBreakAtr"]) * atr_value:
            continue

        failure_position: int | None = None
        for position in range(first_break + 1, min(len(frame) - 1, first_break + failure_window) + 1):
            reclaimed = (
                float(frame.iloc[position]["close"]) > boundary
                if candidate.direction == "long"
                else float(frame.iloc[position]["close"]) < boundary
            )
            if reclaimed:
                failure_position = position
                break
        if failure_position is None:
            continue

        final_retest = min(len(frame) - 2, failure_position + retest_window)
        for signal_position in range(failure_position + 1, final_retest + 1):
            signal_row = frame.iloc[signal_position]
            tolerance = float(definition["retestToleranceAtr"]) * atr_value
            matched = (
                float(signal_row["low"]) <= boundary + tolerance
                and float(signal_row["close"]) > boundary
                and float(signal_row["close"]) > float(signal_row["open"])
                if candidate.direction == "long"
                else float(signal_row["high"]) >= boundary - tolerance
                and float(signal_row["close"]) < boundary
                and float(signal_row["close"]) < float(signal_row["open"])
            )
            if not matched:
                continue
            entry = float(frame.iloc[signal_position + 1]["open"])
            segment = frame.iloc[first_break : signal_position + 1]
            stop_buffer = float(definition["stopBufferAtr"]) * atr_value
            structural_stop = (
                float(segment["low"].min()) - stop_buffer
                if candidate.direction == "long"
                else float(segment["high"].max()) + stop_buffer
            )
            cap = float(definition["maximumStopAtr"]) * atr_value
            stop = (
                max(structural_stop, entry - cap)
                if candidate.direction == "long"
                else min(structural_stop, entry + cap)
            )
            risk = entry - stop if candidate.direction == "long" else stop - entry
            if np.isfinite(risk) and risk > 0 and stop > 0:
                yield signal_position, float(risk), None
            break


def replay_reference_candidate_events(
    *,
    candidate: CandidateSpec,
    frame: pd.DataFrame,
    costs: dict[str, float],
    funding_rate: pd.Series | None = None,
) -> list[dict[str, Any]]:
    """Replay selected hypotheses without using any future bar for signal creation."""

    if candidate.exitPolicy is None:
        raise ValueError("reference candidates require a preregistered exit policy")
    ordered = (
        frame.sort_values("date")
        .drop_duplicates("date", keep="last")
        .reset_index(drop=True)
        .copy()
    )
    required = {"date", "open", "high", "low", "close", "volume"}
    missing = required - set(ordered)
    if missing:
        raise ValueError(f"frame is missing columns: {sorted(missing)}")
    atr = atr_series(ordered, window=int(candidate.eventDefinition.get("atrWindow", 20)))
    if candidate.marketMechanismId == "reference_utc_session_range_breakout":
        signals = _session_signals(candidate, ordered, atr)
    elif candidate.marketMechanismId == "reference_breakout_failure_second_entry":
        signals = _second_entry_signals(candidate, ordered, atr)
    else:
        raise ValueError(f"unsupported reference mechanism: {candidate.marketMechanismId}")

    events: list[dict[str, Any]] = []
    next_allowed = 0
    for signal_position, risk_distance, structure_mask in signals:
        if signal_position < next_allowed:
            continue
        result = replay_exit_policy(
            frame=ordered,
            signalPosition=int(signal_position),
            direction=candidate.direction,
            riskDistance=float(risk_distance),
            policy=candidate.exitPolicy,
            costs=_costs(costs),
            atrValues=atr,
            structureExitMask=structure_mask,
            fundingRate=funding_rate,
        )
        event = exit_execution_to_dict(result)
        events.append(event)
        next_allowed = int(event["exitPosition"]) + 1
    return events
