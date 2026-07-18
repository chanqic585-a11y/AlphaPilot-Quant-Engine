"""Frozen simple benchmark compiler for corrected Advisory-R diagnostics."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

from .signals import weak_signal_components


BENCHMARK_BY_VARIANT = {
    "S01": "same_event_fixed_12_bar_exit",
    "S02": "btc_impulse_next_6_bar_direction",
    "S03": "btc_impulse_contemporaneous_reversal",
    "S04": "pair_residual_zero_cross",
    "S05": "correlation_break_equal_hold",
    "S06": "correlation_break_next_6_bar_direction",
    "S07": "volatility_shock_fixed_6_bar",
    "S08": "same_hour_unconditional_direction",
    "S09": "equal_weight_representative_universe",
    "S10": "equal_weight_component_signals",
}


_FIXED_HOLD_BARS = {
    "S01": 12,
    "S02": 6,
    "S03": 1,
    "S06": 6,
    "S07": 6,
    "S08": 12,
}


def _profit_factor(values: Sequence[float]) -> float:
    wins = sum(value for value in values if value > 0)
    losses = abs(sum(value for value in values if value < 0))
    return wins / losses if losses else (999.0 if wins else 0.0)


def _cost(event: Mapping[str, Any]) -> float:
    return sum(
        float(event.get(name) or 0.0)
        for name in ("feesR", "slippageR", "spreadProxyR", "fundingR")
    )


def _fixed_hold_net_r(
    event: Mapping[str, Any],
    frame: pd.DataFrame,
    hold_bars: int,
) -> float:
    entry_index = int(event["entryIndex"])
    exit_index = min(entry_index + hold_bars, len(frame) - 1)
    entry_price = float(event["entryPrice"])
    exit_price = float(frame.iloc[exit_index]["open"])
    risk = float(event["riskDistance"])
    direction = 1.0 if str(event["side"]) == "long" else -1.0
    gross = direction * (exit_price - entry_price) / risk
    return gross - _cost(event)


def _candidate_values(events: Sequence[Mapping[str, Any]]) -> list[float]:
    return [float(row.get("netR") or row.get("realizedNetR") or 0.0) for row in events]


def _equal_weight_price(frames: Mapping[str, pd.DataFrame]) -> pd.Series:
    series = []
    for symbol, raw in sorted(frames.items()):
        frame = raw.copy()
        frame["date"] = pd.to_datetime(frame["date"], utc=True)
        if "confirmed" in frame:
            frame = frame[pd.to_numeric(frame["confirmed"], errors="coerce") == 1]
        close = pd.to_numeric(frame["close"], errors="coerce")
        normalized = pd.DataFrame({"date": frame["date"], "close": close}).dropna()
        normalized = normalized.sort_values("date").drop_duplicates("date", keep="last")
        series.append(normalized.set_index("date")["close"].rename(symbol))
    closes = pd.concat(series, axis=1, join="inner").sort_index()
    normalized = closes / closes.iloc[0]
    return normalized.mean(axis=1) * 100.0


def _equal_weight_event_values(
    events: Sequence[Mapping[str, Any]],
    frames: Mapping[str, pd.DataFrame],
) -> list[float]:
    synthetic = _equal_weight_price(frames).reset_index(drop=True)
    values = []
    for event in events:
        entry_index = int(event["entryIndex"])
        exit_index = min(int(event["exitIndex"]), len(synthetic) - 1)
        entry_price = float(synthetic.iloc[entry_index])
        exit_price = float(synthetic.iloc[exit_index])
        candidate_risk_fraction = float(event["riskDistance"]) / float(event["entryPrice"])
        risk = entry_price * candidate_risk_fraction
        direction = 1.0 if str(event["side"]) == "long" else -1.0
        gross = direction * (exit_price - entry_price) / risk
        values.append(gross - _cost(event))
    return values


def _ordered_frame(raw: pd.DataFrame) -> pd.DataFrame:
    frame = raw.copy()
    frame["date"] = pd.to_datetime(frame["date"], utc=True)
    if "confirmed" in frame:
        frame = frame[pd.to_numeric(frame["confirmed"], errors="coerce") == 1]
    for column in ("open", "high", "low", "close", "volume"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return (
        frame.dropna(subset=["date", "open", "high", "low", "close", "volume"])
        .sort_values("date")
        .drop_duplicates("date", keep="last")
        .reset_index(drop=True)
    )


def _market_close(frames: Mapping[str, pd.DataFrame]) -> pd.Series:
    panel = pd.concat(
        {
            symbol: frame.set_index("date")["close"]
            for symbol, frame in sorted(frames.items())
            if not frame.empty
        },
        axis=1,
    ).sort_index()
    return panel.median(axis=1, skipna=True)


def _equal_weight_component_values(
    candidate: Mapping[str, Any],
    events: Sequence[Mapping[str, Any]],
    frames: Mapping[str, pd.DataFrame],
) -> list[float]:
    ordered = {symbol: _ordered_frame(frame) for symbol, frame in frames.items()}
    market_close = _market_close(ordered)
    components_by_symbol = {
        symbol: weak_signal_components(candidate, frame, market_close=market_close)
        for symbol, frame in ordered.items()
    }
    values = []
    for event in events:
        symbol = str(event["symbol"])
        frame = ordered.get(symbol)
        components = components_by_symbol.get(symbol)
        if frame is None or components is None:
            continue
        signal_index = int(event["signalIndex"])
        entry_index = int(event["entryIndex"])
        exit_index = min(int(event["exitIndex"]), len(frame) - 1)
        if max(signal_index, entry_index, exit_index) >= len(frame):
            continue
        directions = pd.to_numeric(components.iloc[signal_index], errors="coerce").fillna(0.0)
        equal_weight_direction = float(directions.mean())
        active_fraction = float(np.abs(directions).mean())
        entry_price = float(event["entryPrice"])
        exit_price = float(frame.iloc[exit_index]["open"])
        risk = float(event["riskDistance"])
        gross = equal_weight_direction * (exit_price - entry_price) / risk
        values.append(gross - _cost(event) * active_fraction)
    return values


def _benchmark_values(
    candidate: Mapping[str, Any],
    events: Sequence[Mapping[str, Any]],
    frames: Mapping[str, pd.DataFrame],
) -> tuple[list[float], str]:
    variant = str(candidate["variantId"])
    if variant in _FIXED_HOLD_BARS:
        values = []
        for event in events:
            symbol = str(event["symbol"])
            frame = frames.get(symbol)
            if frame is None:
                continue
            values.append(_fixed_hold_net_r(event, frame, _FIXED_HOLD_BARS[variant]))
        return values, f"same signal/direction/cost/risk; next-open after {_FIXED_HOLD_BARS[variant]} bars"
    if variant in {"S04", "S05"}:
        missing = [
            str(event.get("symbol") or "unknown")
            for event in events
            if event.get("simpleBenchmarkNetR") is None
        ]
        if missing:
            raise RuntimeError(
                f"{variant} pair benchmark evidence missing for: " + ", ".join(missing)
            )
        values = [float(event["simpleBenchmarkNetR"]) for event in events]
        name = "zero-cross" if variant == "S04" else "equal-hold"
        return values, f"same two-leg signal, direction, cost, risk, capital competition; independent {name} exit"
    if variant == "S09":
        return (
            _equal_weight_event_values(events, frames),
            "equal-weight representative universe over the same entry/exit window, risk, cost, and capital competition",
        )
    if variant == "S10":
        return (
            _equal_weight_component_values(candidate, events, frames),
            "equal-weight three frozen component signals at the same event time, exit window, risk, cost, and capital competition",
        )
    raise RuntimeError(f"unsupported simple benchmark variant: {variant}")


def build_benchmark_comparison(
    candidates: Sequence[Mapping[str, Any]],
    events_by_candidate: Mapping[str, Sequence[Mapping[str, Any]]],
    frames_by_timeframe: Mapping[str, Mapping[str, pd.DataFrame]],
) -> list[dict[str, Any]]:
    rows = []
    for candidate in candidates:
        variant = str(candidate["variantId"])
        expected_name = BENCHMARK_BY_VARIANT[variant]
        if str(candidate["simpleBenchmark"]) != expected_name:
            raise RuntimeError(f"frozen benchmark mismatch for {variant}")
        events = list(events_by_candidate.get(str(candidate["candidateId"]), []))
        candidate_values = _candidate_values(events)
        benchmark_values, method = _benchmark_values(
            candidate,
            events,
            frames_by_timeframe[str(candidate.get("timeframe") or "1h")],
        )
        candidate_net = sum(candidate_values)
        benchmark_net = sum(benchmark_values)
        rows.append(
            {
                "candidateId": candidate["candidateId"],
                "variantId": variant,
                "benchmarkName": expected_name,
                "candidateNetR": candidate_net,
                "benchmarkNetR": benchmark_net,
                "incrementalNetR": candidate_net - benchmark_net,
                "candidatePF": _profit_factor(candidate_values),
                "benchmarkPF": _profit_factor(benchmark_values),
                "candidateEventCount": len(candidate_values),
                "benchmarkObservationCount": len(benchmark_values),
                "method": method,
                "diagnosticOnly": True,
                "addedAsHardGate": False,
            }
        )
    return rows


def simple_benchmark_report(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "schemaVersion": "advisory_r_simple_benchmarks_v2",
        "benchmarkCount": len(rows),
        "diagnosticOnly": True,
        "hardGateChanges": 0,
        "benchmarks": [dict(row) for row in rows],
    }
