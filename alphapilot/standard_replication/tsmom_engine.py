"""Deterministic TSMOM definitions and reference replay for V36 Formal."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

from alphapilot.evolution.registry.hashing import stable_hash


TSMOM_SYMBOLS = ("BTC-USDT-SWAP", "ETH-USDT-SWAP", "SOL-USDT-SWAP")

SELECTED_TSMOM_TRIALS = {
    "v35_tsmom_crypto_adaptation": (
        "v36_trial_43b2c0f5804b1f0596bc6d5691d79013699a5e1b3db0a07e7a3332ac3f6f0599"
    ),
    "v35_tsmom_source_replication": (
        "v36_trial_ec2562d73795444e90789e7f77a3e129030b7d92c0f3614cf3f33375fdaf41c0"
    ),
}

_BASE_DEFINITIONS: dict[str, dict[str, Any]] = {
    "v35_tsmom_source_replication": {
        "familyId": "crypto_tsmom_turtle_v1",
        "timeframe": "1dutc",
        "lookbackBars": 120,
        "entryDonchianBars": 55,
        "exitDonchianBars": 20,
        "atrBars": 20,
        "stopAtr": 2.5,
        "minimumMomentum": 0.04,
        "maximumHoldBars": 180,
    },
    "v35_tsmom_crypto_adaptation": {
        "familyId": "crypto_tsmom_turtle_v1",
        "timeframe": "4h",
        "lookbackBars": 180,
        "entryDonchianBars": 60,
        "exitDonchianBars": 24,
        "atrBars": 20,
        "stopAtr": 2.5,
        "minimumMomentum": 0.025,
        "maximumHoldBars": 180,
    },
}


class TsmomReplayError(RuntimeError):
    """Raised when a frozen TSMOM replay input is incomplete or inconsistent."""


def base_tsmom_definition(candidate_id: str) -> dict[str, Any]:
    """Return one immutable base definition without trial-scale metadata."""

    if candidate_id not in _BASE_DEFINITIONS:
        raise KeyError(f"tsmom_candidate_not_selected:{candidate_id}")
    return dict(_BASE_DEFINITIONS[candidate_id])


def scale_tsmom_definition(
    candidate_id: str,
    *,
    parameter_scale: float = 1.0,
) -> dict[str, Any]:
    """Build the exact Development-selected definition and preserve its hash."""

    result = base_tsmom_definition(candidate_id)
    for key in ("lookbackBars", "entryDonchianBars", "exitDonchianBars"):
        result[key] = max(8, int(round(float(result[key]) * parameter_scale)))
    result["minimumMomentum"] = (
        float(result["minimumMomentum"]) * parameter_scale
    )
    result["parameterScale"] = float(parameter_scale)
    result["definitionHash"] = stable_hash(
        result,
        prefix="v36_replay_definition",
    )
    return result


def build_tsmom_candidate_spec(candidate_id: str) -> dict[str, Any]:
    """Return the frozen executable identity for one selected TSMOM candidate."""

    definition = scale_tsmom_definition(candidate_id)
    exit_policy = {
        "policyId": "tsmom_donchian_stop_max_hold_v1",
        "initialStop": {
            "type": "atr_multiple",
            "atrBars": int(definition["atrBars"]),
            "atrMultiple": float(definition["stopAtr"]),
        },
        "signalExit": {
            "type": "donchian_reversal",
            "bars": int(definition["exitDonchianBars"]),
            "execution": "next_bar_open",
        },
        "maximumHoldBars": int(definition["maximumHoldBars"]),
        "fundingTreatment": "observed_per_bar_required",
    }
    return {
        "candidateId": candidate_id,
        "familyId": str(definition["familyId"]),
        "selectedTrialId": SELECTED_TSMOM_TRIALS[candidate_id],
        "parameterScale": 1.0,
        "timeframe": str(definition["timeframe"]),
        "universe": list(TSMOM_SYMBOLS),
        "definition": definition,
        "exitPolicy": exit_policy,
        "strategyDefinitionHash": str(definition["definitionHash"]),
        "exitPolicyHash": stable_hash(
            exit_policy,
            prefix="v36_tsmom_exit_policy",
        ),
        "fundingEvidenceRequired": True,
    }


def normalize_tsmom_frame(frame: pd.DataFrame, *, symbol: str) -> pd.DataFrame:
    """Normalize one immutable OHLCV+funding partition without filling evidence."""

    result = frame.copy()
    if "date" not in result and "timestamp_ms" in result:
        result["date"] = pd.to_datetime(
            result["timestamp_ms"], unit="ms", utc=True
        )
    result["date"] = pd.to_datetime(result.get("date"), utc=True, errors="coerce")
    for column in ("open", "high", "low", "close", "volume"):
        if column not in result:
            raise TsmomReplayError(f"market_column_missing:{symbol}:{column}")
        result[column] = pd.to_numeric(result[column], errors="coerce")

    funding_column = next(
        (
            name
            for name in ("fundingRate", "funding_rate")
            if name in result.columns
        ),
        None,
    )
    if funding_column is None:
        raise TsmomReplayError(f"funding_evidence_missing:{symbol}")
    result["fundingRate"] = pd.to_numeric(
        result[funding_column], errors="coerce"
    )
    required = [
        "date",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "fundingRate",
    ]
    if result[required].isna().any().any():
        raise TsmomReplayError(f"market_or_funding_value_invalid:{symbol}")
    return (
        result.sort_values("date")
        .drop_duplicates("date", keep="last")
        .reset_index(drop=True)
    )


def atr(frame: pd.DataFrame, window: int) -> pd.Series:
    previous = frame["close"].shift(1)
    true_range = pd.concat(
        [
            frame["high"] - frame["low"],
            (frame["high"] - previous).abs(),
            (frame["low"] - previous).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return true_range.rolling(window, min_periods=window).mean()


def _iso(value: object) -> str:
    return pd.Timestamp(value).isoformat()


def _simulate_trade(
    *,
    candidate: Mapping[str, Any],
    frame: pd.DataFrame,
    symbol: str,
    signal_index: int,
    side: int,
    atr_value: float,
    exit_signal: pd.Series,
    round_trip_cost_rate: float,
) -> tuple[dict[str, Any] | None, int]:
    definition = dict(candidate["definition"])
    entry_index = signal_index + 1
    if entry_index >= len(frame) - 1 or not np.isfinite(atr_value) or atr_value <= 0:
        return None, signal_index + 1
    entry_price = float(frame.at[entry_index, "open"])
    risk_distance = atr_value * float(definition["stopAtr"])
    if risk_distance <= 0 or risk_distance / entry_price > 0.25:
        return None, entry_index + 1

    stop_price = entry_price - side * risk_distance
    final_index = min(
        len(frame) - 1,
        entry_index + int(definition["maximumHoldBars"]),
    )
    exit_index = final_index
    exit_trigger_index = final_index
    exit_price = float(frame.at[final_index, "close"])
    exit_reason = "maximum_hold"
    maximum_favorable = 0.0
    maximum_adverse = 0.0

    for position in range(entry_index, final_index + 1):
        high = float(frame.at[position, "high"])
        low = float(frame.at[position, "low"])
        favorable = high - entry_price if side > 0 else entry_price - low
        adverse = low - entry_price if side > 0 else entry_price - high
        maximum_favorable = max(maximum_favorable, favorable / risk_distance)
        maximum_adverse = min(maximum_adverse, adverse / risk_distance)
        stopped = low <= stop_price if side > 0 else high >= stop_price
        if stopped:
            exit_index = position
            exit_trigger_index = position
            exit_price = stop_price
            exit_reason = "initial_stop"
            break
        if bool(exit_signal.iloc[position]):
            exit_trigger_index = position
            exit_index = min(position + 1, len(frame) - 1)
            exit_price = float(frame.at[exit_index, "open"])
            exit_reason = "donchian_reversal"
            break

    gross_r = side * (exit_price - entry_price) / risk_distance
    transaction_cost_r = round_trip_cost_rate * entry_price / risk_distance
    observed_funding = float(
        frame.loc[entry_index:exit_index, "fundingRate"].sum()
    )
    funding_r = -side * observed_funding * entry_price / risk_distance
    signal_timestamp = _iso(frame.at[signal_index, "date"])
    entry_timestamp = _iso(frame.at[entry_index, "date"])
    exit_timestamp = _iso(frame.at[exit_index, "date"])
    return (
        {
            "candidateId": str(candidate["candidateId"]),
            "instrumentId": symbol,
            "symbol": symbol,
            "direction": "long" if side > 0 else "short",
            "signalTimestamp": signal_timestamp,
            "signalIndex": int(signal_index),
            "entryTimestamp": entry_timestamp,
            "entryIndex": int(entry_index),
            "expectedEntryTimestamp": entry_timestamp,
            "exitTriggerTimestamp": _iso(frame.at[exit_trigger_index, "date"]),
            "exitTimestamp": exit_timestamp,
            "exitIndex": int(exit_index),
            "entryPrice": entry_price,
            "exitPrice": exit_price,
            "riskDistance": float(risk_distance),
            "initialStop": stop_price,
            "initialStopPrice": stop_price,
            "stopPrice": stop_price,
            "grossR": float(gross_r),
            "costR": float(transaction_cost_r),
            "fundingR": float(funding_r),
            "netR": float(gross_r - transaction_cost_r + funding_r),
            "mfeR": float(maximum_favorable),
            "maeR": float(maximum_adverse),
            "exitReason": exit_reason,
            "signalBarIndex": int(signal_index),
            "setupId": "tsmom_turtle",
            "exitPolicyHash": str(candidate["exitPolicyHash"]),
        },
        exit_index + 1,
    )


def replay_tsmom_events(
    *,
    candidate: Mapping[str, Any],
    frames: Mapping[str, pd.DataFrame],
    round_trip_cost_rate: float,
) -> Sequence[Mapping[str, Any]]:
    """Replay a frozen TSMOM candidate with next-bar execution and observed funding."""

    candidate_id = str(candidate.get("candidateId") or "")
    if candidate_id not in SELECTED_TSMOM_TRIALS:
        raise TsmomReplayError(f"tsmom_candidate_not_selected:{candidate_id}")
    if not np.isfinite(round_trip_cost_rate) or round_trip_cost_rate < 0:
        raise TsmomReplayError("round_trip_cost_invalid")
    definition = dict(candidate["definition"])
    expected_symbols = tuple(str(value) for value in candidate["universe"])
    missing = sorted(set(expected_symbols) - set(frames))
    if missing:
        raise TsmomReplayError(f"market_frame_missing:{missing[0]}")

    events: list[dict[str, Any]] = []
    for symbol in expected_symbols:
        frame = normalize_tsmom_frame(frames[symbol], symbol=symbol)
        lookback = int(definition["lookbackBars"])
        entry_bars = int(definition["entryDonchianBars"])
        exit_bars = int(definition["exitDonchianBars"])
        momentum = frame["close"] / frame["close"].shift(lookback) - 1.0
        upper = frame["high"].rolling(entry_bars, min_periods=entry_bars).max().shift(1)
        lower = frame["low"].rolling(entry_bars, min_periods=entry_bars).min().shift(1)
        exit_upper = frame["high"].rolling(exit_bars, min_periods=exit_bars).max().shift(1)
        exit_lower = frame["low"].rolling(exit_bars, min_periods=exit_bars).min().shift(1)
        long_signal = (
            (momentum >= float(definition["minimumMomentum"]))
            & (frame["close"] > upper)
        ).fillna(False)
        short_signal = (
            (momentum <= -float(definition["minimumMomentum"]))
            & (frame["close"] < lower)
        ).fillna(False)
        atr_values = atr(frame, int(definition["atrBars"]))
        next_available = 0
        signal_positions = np.flatnonzero((long_signal | short_signal).to_numpy())
        for raw_index in signal_positions:
            signal_index = int(raw_index)
            if signal_index < next_available:
                continue
            side = 1 if bool(long_signal.iloc[signal_index]) else -1
            exit_signal = (
                frame["close"] < exit_lower
                if side > 0
                else frame["close"] > exit_upper
            ).fillna(False)
            event, next_available = _simulate_trade(
                candidate=candidate,
                frame=frame,
                symbol=symbol,
                signal_index=signal_index,
                side=side,
                atr_value=float(atr_values.iloc[signal_index]),
                exit_signal=exit_signal,
                round_trip_cost_rate=float(round_trip_cost_rate),
            )
            if event is not None:
                events.append(event)
    return sorted(
        events,
        key=lambda row: (
            str(row["signalTimestamp"]),
            str(row["symbol"]),
            str(row["direction"]),
        ),
    )


__all__ = [
    "atr",
    "base_tsmom_definition",
    "build_tsmom_candidate_spec",
    "normalize_tsmom_frame",
    "replay_tsmom_events",
    "scale_tsmom_definition",
    "SELECTED_TSMOM_TRIALS",
    "TSMOM_SYMBOLS",
    "TsmomReplayError",
]
