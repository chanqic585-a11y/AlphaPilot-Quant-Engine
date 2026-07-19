"""Independent oracle and audit helpers for frozen reference strategies."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

from alphapilot.research_screening.campaign_contract import CandidateSpec
from alphapilot.research_screening.campaign_metrics import evaluate_candidate_gates

from .signals import detect_reference_candidate_signals


def _ordered_frame(frame: pd.DataFrame) -> pd.DataFrame:
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
    return ordered


def _oracle_atr(frame: pd.DataFrame, window: int) -> pd.Series:
    previous_close = pd.to_numeric(frame["close"], errors="coerce").shift(1)
    true_range = pd.concat(
        [
            pd.to_numeric(frame["high"], errors="coerce")
            - pd.to_numeric(frame["low"], errors="coerce"),
            (pd.to_numeric(frame["high"], errors="coerce") - previous_close).abs(),
            (pd.to_numeric(frame["low"], errors="coerce") - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return true_range.rolling(window, min_periods=window).mean()


def _fingerprint(
    frame: pd.DataFrame,
    *,
    signal_position: int,
    entry_position: int,
    entry_price: float,
    risk_distance: float,
) -> dict[str, Any]:
    return {
        "signalPosition": int(signal_position),
        "signalTimestamp": pd.Timestamp(frame.iloc[signal_position]["date"]).isoformat(),
        "entryPosition": int(entry_position),
        "entryTimestamp": pd.Timestamp(frame.iloc[entry_position]["date"]).isoformat(),
        "entryPrice": round(float(entry_price), 12),
        "riskDistance": round(float(risk_distance), 12),
    }


def _oracle_session_signals(
    candidate: CandidateSpec,
    frame: pd.DataFrame,
    atr: pd.Series,
) -> Iterable[dict[str, Any]]:
    definition = candidate.eventDefinition
    range_bars = int(definition["rangeBars"])
    breakout_window = int(definition["breakoutWindowBars"])
    anchor_hour = int(definition["sessionAnchorUtcHour"])
    timestamps = pd.to_datetime(frame["date"], utc=True)
    for anchor_value in np.flatnonzero(timestamps.dt.hour.eq(anchor_hour).to_numpy()):
        anchor = int(anchor_value)
        if anchor < range_bars or anchor >= len(frame) - 1:
            continue
        atr_value = float(atr.iloc[anchor])
        if not math.isfinite(atr_value) or atr_value <= 0:
            continue
        frozen = frame.iloc[anchor - range_bars : anchor]
        range_high = float(frozen["high"].max())
        range_low = float(frozen["low"].min())
        width_atr = (range_high - range_low) / atr_value
        if not float(definition["minimumRangeAtr"]) <= width_atr <= float(
            definition["maximumRangeAtr"]
        ):
            continue
        threshold_buffer = float(definition["breakoutBufferAtr"]) * atr_value
        last_signal = min(len(frame) - 2, anchor + breakout_window - 1)
        for signal_position in range(anchor, last_signal + 1):
            close = float(frame.iloc[signal_position]["close"])
            if candidate.direction == "long":
                matched = close > range_high + threshold_buffer
            else:
                matched = close < range_low - threshold_buffer
            if not matched:
                continue
            entry_position = signal_position + 1
            entry_price = float(frame.iloc[entry_position]["open"])
            risk_cap = float(definition["maximumStopAtr"]) * atr_value
            if candidate.direction == "long":
                stop = max(range_low, entry_price - risk_cap)
                risk = entry_price - stop
            else:
                stop = min(range_high, entry_price + risk_cap)
                risk = stop - entry_price
            if math.isfinite(risk) and risk > 0 and stop > 0:
                yield _fingerprint(
                    frame,
                    signal_position=signal_position,
                    entry_position=entry_position,
                    entry_price=entry_price,
                    risk_distance=risk,
                )
            break


def _oracle_second_entry_signals(
    candidate: CandidateSpec,
    frame: pd.DataFrame,
    atr: pd.Series,
) -> Iterable[dict[str, Any]]:
    definition = candidate.eventDefinition
    boundary_window = int(definition["boundaryWindowBars"])
    failure_window = int(definition["failureWindowBars"])
    retest_window = int(definition["retestWindowBars"])
    for first_break in range(boundary_window, len(frame) - 2):
        atr_value = float(atr.iloc[first_break])
        if not math.isfinite(atr_value) or atr_value <= 0:
            continue
        prior = frame.iloc[first_break - boundary_window : first_break]
        boundary = (
            float(prior["low"].min())
            if candidate.direction == "long"
            else float(prior["high"].max())
        )
        row = frame.iloc[first_break]
        if candidate.direction == "long":
            excursion = boundary - float(row["low"])
            closes_outside = float(row["close"]) < boundary
        else:
            excursion = float(row["high"]) - boundary
            closes_outside = float(row["close"]) > boundary
        if excursion <= 0 or not closes_outside:
            continue
        if excursion > float(definition["maximumFirstBreakAtr"]) * atr_value:
            continue

        failure_position: int | None = None
        failure_end = min(len(frame) - 1, first_break + failure_window)
        for position in range(first_break + 1, failure_end + 1):
            close = float(frame.iloc[position]["close"])
            reclaimed = close > boundary if candidate.direction == "long" else close < boundary
            if reclaimed:
                failure_position = position
                break
        if failure_position is None:
            continue

        retest_end = min(len(frame) - 2, failure_position + retest_window)
        for signal_position in range(failure_position + 1, retest_end + 1):
            signal_row = frame.iloc[signal_position]
            tolerance = float(definition["retestToleranceAtr"]) * atr_value
            if candidate.direction == "long":
                matched = (
                    float(signal_row["low"]) <= boundary + tolerance
                    and float(signal_row["close"]) > boundary
                    and float(signal_row["close"]) > float(signal_row["open"])
                )
            else:
                matched = (
                    float(signal_row["high"]) >= boundary - tolerance
                    and float(signal_row["close"]) < boundary
                    and float(signal_row["close"]) < float(signal_row["open"])
                )
            if not matched:
                continue
            entry_position = signal_position + 1
            entry_price = float(frame.iloc[entry_position]["open"])
            segment = frame.iloc[first_break : signal_position + 1]
            stop_buffer = float(definition["stopBufferAtr"]) * atr_value
            risk_cap = float(definition["maximumStopAtr"]) * atr_value
            if candidate.direction == "long":
                structural_stop = float(segment["low"].min()) - stop_buffer
                stop = max(structural_stop, entry_price - risk_cap)
                risk = entry_price - stop
            else:
                structural_stop = float(segment["high"].max()) + stop_buffer
                stop = min(structural_stop, entry_price + risk_cap)
                risk = stop - entry_price
            if math.isfinite(risk) and risk > 0 and stop > 0:
                yield _fingerprint(
                    frame,
                    signal_position=signal_position,
                    entry_position=entry_position,
                    entry_price=entry_price,
                    risk_distance=risk,
                )
            break


def oracle_reference_candidate_signals(
    *,
    candidate: CandidateSpec,
    frame: pd.DataFrame,
) -> list[dict[str, Any]]:
    """Independently execute the frozen signal definition without production helpers."""

    ordered = _ordered_frame(frame)
    atr = _oracle_atr(ordered, int(candidate.eventDefinition.get("atrWindow", 20)))
    if candidate.marketMechanismId == "reference_utc_session_range_breakout":
        return list(_oracle_session_signals(candidate, ordered, atr))
    if candidate.marketMechanismId == "reference_breakout_failure_second_entry":
        return list(_oracle_second_entry_signals(candidate, ordered, atr))
    raise ValueError(f"unsupported reference mechanism: {candidate.marketMechanismId}")


def audit_signal_parity(
    *,
    candidate: CandidateSpec,
    frame: pd.DataFrame,
    fixture_id: str,
    provenance: dict[str, Any],
) -> dict[str, Any]:
    """Compare public production fingerprints with the independent oracle."""

    production = [
        signal.fingerprint()
        for signal in detect_reference_candidate_signals(candidate=candidate, frame=frame)
    ]
    oracle = oracle_reference_candidate_signals(candidate=candidate, frame=frame)
    mismatches: list[dict[str, Any]] = []
    if len(production) != len(oracle):
        mismatches.append(
            {
                "kind": "signal_count",
                "production": len(production),
                "oracle": len(oracle),
            }
        )
    numeric_fields = {"entryPrice", "riskDistance"}
    for index, (production_row, oracle_row) in enumerate(zip(production, oracle)):
        for field_name in production_row:
            left = production_row[field_name]
            right = oracle_row[field_name]
            equal = (
                math.isclose(float(left), float(right), rel_tol=1e-12, abs_tol=1e-12)
                if field_name in numeric_fields
                else left == right
            )
            if not equal:
                mismatches.append(
                    {
                        "kind": "field",
                        "signalIndex": index,
                        "field": field_name,
                        "production": left,
                        "oracle": right,
                    }
                )
    return {
        "schemaVersion": "reference_signal_parity_v1",
        "fixtureId": fixture_id,
        "candidateId": candidate.candidateId,
        "mechanismId": candidate.marketMechanismId,
        "direction": candidate.direction,
        "timeframe": candidate.timeframe,
        "provenance": dict(provenance),
        "productionSignalCount": len(production),
        "oracleSignalCount": len(oracle),
        "parityPassed": not mismatches,
        "mismatches": mismatches,
        "productionFingerprints": production,
        "oracleFingerprints": oracle,
    }


def audit_parquet_signal_parity(
    *,
    candidate: CandidateSpec,
    parquet_path: str | Path,
    fixture_id: str,
    provenance: dict[str, Any],
) -> dict[str, Any]:
    frame = pd.read_parquet(Path(parquet_path))
    return audit_signal_parity(
        candidate=candidate,
        frame=frame,
        fixture_id=fixture_id,
        provenance=provenance,
    )


def _positive_gate_event(
    *,
    index: int,
    timestamp: pd.Timestamp,
    split: str,
    fold_id: str,
) -> dict[str, Any]:
    net_r = -0.25 if index % 5 == 0 else 1.0
    fees_r = 0.01
    slippage_r = 0.01
    funding_r = 0.01
    spread_r = 0.01
    return {
        "netR": net_r,
        "grossR": net_r + fees_r + slippage_r + funding_r + spread_r,
        "feesR": fees_r,
        "slippageR": slippage_r,
        "fundingR": funding_r,
        "spreadProxyR": spread_r,
        "split": split,
        "foldId": fold_id,
        "symbol": ("BTC-USDT-SWAP", "ETH-USDT-SWAP", "SOL-USDT-SWAP", "XRP-USDT-SWAP")[
            index % 4
        ],
        "entryTimestamp": timestamp.isoformat(),
    }


def _known_positive_gate_events(
    preregistration: dict[str, Any],
    timeframe: str,
) -> list[dict[str, Any]]:
    sample_rule = preregistration["sampleGates"][timeframe]
    development_count = int(sample_rule["minimumEvents"])
    development_months = int(sample_rule["minimumMonths"])
    development_starts = pd.date_range(
        "2020-01-01T00:00:00Z", periods=development_months, freq="MS"
    )
    rows: list[dict[str, Any]] = []
    for index in range(development_count):
        month = development_starts[index % development_months]
        timestamp = month + pd.Timedelta(hours=index // development_months)
        rows.append(
            _positive_gate_event(
                index=index,
                timestamp=timestamp,
                split="development",
                fold_id="",
            )
        )

    oos_months = pd.date_range("2023-01-01T00:00:00Z", periods=12, freq="MS")
    for index in range(120):
        split = "walk_forward" if index < 100 else "holdout"
        fold_id = f"fold_{(index // 20) + 1:03d}" if split == "walk_forward" else ""
        month = oos_months[index % len(oos_months)]
        timestamp = month + pd.Timedelta(hours=index // len(oos_months))
        rows.append(
            _positive_gate_event(
                index=index + development_count,
                timestamp=timestamp,
                split=split,
                fold_id=fold_id,
            )
        )
    return rows


def build_gate_reachability_report(
    *,
    preregistration: dict[str, Any],
    timeframe: str,
) -> dict[str, Any]:
    """Prove the unchanged gate implementation accepts an explicit positive fixture."""

    events = _known_positive_gate_events(preregistration, timeframe)
    gates = evaluate_candidate_gates(
        events=events,
        timeframe=timeframe,
        preregistration=preregistration,
        holdout_access_before_final_evaluation=0,
    )
    gate_flags = {
        name: bool(gates[name])
        for name in ("samplePassed", "prescreenPassed", "basePassed", "formalPassed")
    }
    return {
        "schemaVersion": "reference_gate_reachability_v1",
        "timeframe": timeframe,
        "fixture": "deterministic_known_positive_cost_aware_events",
        "eventCount": len(events),
        "developmentEventCount": sum(row["split"] == "development" for row in events),
        "walkForwardEventCount": sum(row["split"] == "walk_forward" for row in events),
        "holdoutEventCount": sum(row["split"] == "holdout" for row in events),
        "allGatesReachable": all(gate_flags.values()),
        "gateFlags": gate_flags,
        "gates": gates,
    }
