"""Deterministic Development-only replay for executable V35 replications."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

from alphapilot.evolution.registry.hashing import stable_hash
from alphapilot.standard_replication import ReplicationSourceRegistry
from alphapilot.standard_replication.tsmom_engine import (
    SELECTED_TSMOM_TRIALS,
    base_tsmom_definition,
    scale_tsmom_definition,
)

from .contracts import V36ContractError
from .btc_downside_spillover import replay_btc_downside_spillover
from .intraday_session import replay_intraday_session


_SYMBOLS = ("BTC-USDT-SWAP", "ETH-USDT-SWAP", "SOL-USDT-SWAP")
_FIXED_CORE_SYMBOLS = (
    "BTC-USDT-SWAP",
    "ETH-USDT-SWAP",
    "BCH-USDT-SWAP",
    "LTC-USDT-SWAP",
    "ETC-USDT-SWAP",
    "XRP-USDT-SWAP",
    "LINK-USDT-SWAP",
    "YFI-USDT-SWAP",
    "NEO-USDT-SWAP",
    "ATOM-USDT-SWAP",
    "ADA-USDT-SWAP",
    "TRX-USDT-SWAP",
    "COMP-USDT-SWAP",
    "DOGE-USDT-SWAP",
    "SOL-USDT-SWAP",
    "AAVE-USDT-SWAP",
    "FIL-USDT-SWAP",
    "ALGO-USDT-SWAP",
    "AVAX-USDT-SWAP",
    "XTZ-USDT-SWAP",
)

# These are frozen research definitions, not optimized outputs. The three
# preregistered parameter scales are applied only inside the Development split.
_REPLAY_DEFINITIONS: dict[str, dict[str, Any]] = {
    "v36_6_btc_downside_spillover_source_replication": {
        "candidateId": "v36_6_btc_downside_spillover_source_replication",
        "familyId": "crypto_btc_downside_spillover_v1",
        "timeframe": "1h",
        "shockLookbackBars": 2160,
        "shockQuantile": 0.05,
        "minimumShockReturn": -0.02,
        "atrBars": 24,
        "stopAtr": 2.5,
        "maximumHoldBars": 3,
        "targetSymbols": ["ETH-USDT-SWAP", "XRP-USDT-SWAP", "LTC-USDT-SWAP"],
        "minimumEventCount": 30,
        "maximumConcentration": 0.45,
        "adaptation": False,
    },
    "v36_6_btc_downside_spillover_crypto_adaptation": {
        "candidateId": "v36_6_btc_downside_spillover_crypto_adaptation",
        "familyId": "crypto_btc_downside_spillover_v1",
        "timeframe": "1h",
        "shockLookbackBars": 2160,
        "shockQuantile": 0.05,
        "minimumShockReturn": -0.02,
        "atrBars": 24,
        "stopAtr": 2.5,
        "maximumHoldBars": 3,
        "targetSymbols": [
            symbol for symbol in _FIXED_CORE_SYMBOLS if symbol != "BTC-USDT-SWAP"
        ],
        "minimumEventCount": 150,
        "maximumConcentration": 0.12,
        "adaptation": True,
        "betaLookbackBars": 336,
        "minimumBeta": 0.5,
        "minimumVolumeRatio": 0.5,
        "maximumVolumeRatio": 3.0,
    },
    "v36_5_intraday_session_source_replication": {
        "candidateId": "v36_5_intraday_session_source_replication",
        "familyId": "crypto_intraday_session_predictability_v1",
        "timeframe": "1h",
        "sessionHours": 8,
        "lookbackSessions": 20,
        "minimumSessionMean": 0.001,
        "atrBars": 24,
        "stopAtr": 3.0,
        "maximumHoldBars": 7,
        "adaptation": False,
    },
    "v36_5_intraday_session_crypto_adaptation": {
        "candidateId": "v36_5_intraday_session_crypto_adaptation",
        "familyId": "crypto_intraday_session_predictability_v1",
        "timeframe": "1h",
        "sessionHours": 8,
        "lookbackSessions": 20,
        "minimumSessionMean": 0.001,
        "atrBars": 24,
        "stopAtr": 3.0,
        "maximumHoldBars": 7,
        "adaptation": True,
        "minimumVolumeRatio": 0.8,
        "maximumVolumeRatio": 2.5,
        "maximumRealizedVolatility": 0.04,
    },
    "v35_tsmom_source_replication": base_tsmom_definition(
        "v35_tsmom_source_replication"
    ),
    "v35_tsmom_crypto_adaptation": base_tsmom_definition(
        "v35_tsmom_crypto_adaptation"
    ),
    "v35_pair_rv_source_replication": {
        "familyId": "crypto_pair_relative_value_v1",
        "timeframe": "4h",
        "windowBars": 180,
        "entryZ": 2.0,
        "exitZ": 0.25,
        "minimumCorrelation": 0.70,
        "breakCorrelation": 0.45,
        "maximumHoldBars": 60,
    },
    "v35_pair_rv_crypto_adaptation": {
        "familyId": "crypto_pair_relative_value_v1",
        "timeframe": "1h",
        "windowBars": 336,
        "entryZ": 2.1,
        "exitZ": 0.30,
        "minimumCorrelation": 0.65,
        "breakCorrelation": 0.40,
        "maximumHoldBars": 96,
    },
    "v35_conditional_mr_source_replication": {
        "familyId": "crypto_conditional_mean_reversion_v1",
        "timeframe": "4h",
        "residualWindowBars": 168,
        "betaWindowBars": 168,
        "entryZ": 2.2,
        "exitZ": 0.30,
        "rangeEmaGapMaximum": 0.045,
        "stopAtr": 2.5,
        "maximumHoldBars": 42,
    },
    "v35_conditional_mr_crypto_adaptation": {
        "familyId": "crypto_conditional_mean_reversion_v1",
        "timeframe": "1h",
        "residualWindowBars": 336,
        "betaWindowBars": 336,
        "entryZ": 2.0,
        "exitZ": 0.25,
        "rangeEmaGapMaximum": 0.035,
        "stopAtr": 2.5,
        "maximumHoldBars": 72,
    },
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _utc(value: object, *, field: str) -> pd.Timestamp:
    try:
        timestamp = pd.Timestamp(value)
    except (TypeError, ValueError) as exc:
        raise V36ContractError(f"invalid_timestamp:{field}") from exc
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize("UTC")
    return timestamp.tz_convert("UTC")


def _normalize_frame(
    frame: pd.DataFrame,
    *,
    development_start: pd.Timestamp,
    development_end: pd.Timestamp,
) -> pd.DataFrame:
    result = frame.copy()
    if "date" not in result and "timestamp_ms" in result:
        result["date"] = pd.to_datetime(result["timestamp_ms"], unit="ms", utc=True)
    result["date"] = pd.to_datetime(result.get("date"), utc=True, errors="coerce")
    for column in ("open", "high", "low", "close"):
        if column not in result:
            raise V36ContractError(f"snapshot_partition_column_missing:{column}")
        result[column] = pd.to_numeric(result[column], errors="coerce")
    volume_source = next(
        (column for column in ("volCcyQuote", "volume", "volCcy", "vol") if column in result),
        None,
    )
    if volume_source is None:
        raise V36ContractError("snapshot_partition_column_missing:volume")
    result["volume"] = pd.to_numeric(result[volume_source], errors="coerce")
    if "confirm" in result:
        result = result[pd.to_numeric(result["confirm"], errors="coerce") == 1]
    elif "confirmed" in result:
        result = result[pd.to_numeric(result["confirmed"], errors="coerce") == 1]
    else:
        raise V36ContractError("snapshot_partition_confirmation_missing")
    if "availableAt" in result:
        available_at = pd.to_datetime(result["availableAt"], utc=True, errors="coerce")
        if available_at.isna().any():
            raise V36ContractError("snapshot_partition_available_at_invalid")
        result = result[available_at <= development_end]
    result = result[
        (result["date"] >= development_start) & (result["date"] < development_end)
    ]
    result = (
        result.dropna(subset=["date", "open", "high", "low", "close", "volume"])
        .sort_values("date")
        .drop_duplicates("date", keep="last")
        .reset_index(drop=True)
    )
    if result.empty:
        raise V36ContractError("snapshot_partition_development_window_empty")
    return result[["date", "open", "high", "low", "close", "volume"]]


def load_development_frames(
    *,
    manifest_path: Path,
    expected_snapshot_id: str,
    development_start: str,
    development_end: str,
    requirements: set[tuple[str, str]],
) -> tuple[dict[tuple[str, str], pd.DataFrame], dict[str, Any]]:
    """Load and hash-verify only the requested Development partitions."""

    path = Path(manifest_path).resolve()
    if not path.is_file():
        raise V36ContractError("snapshot_manifest_missing")
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if str(payload.get("snapshotId") or "") != str(expected_snapshot_id):
        raise V36ContractError("snapshot_identity_mismatch")
    if str(payload.get("status") or "") not in {
        "completed",
        "valid",
        "healthy",
        "immutable_data_snapshot",
    }:
        raise V36ContractError("snapshot_not_completed")
    start = _utc(development_start, field="developmentStart")
    end = _utc(development_end, field="developmentEnd")
    if start >= end:
        raise V36ContractError("development_window_invalid")

    partition_lookup: dict[tuple[str, str], Mapping[str, object]] = {}
    for raw in payload.get("partitions") or []:
        if not isinstance(raw, Mapping):
            raise V36ContractError("snapshot_partition_invalid")
        key = (str(raw.get("instrumentId") or ""), str(raw.get("timeframe") or ""))
        if key in partition_lookup:
            raise V36ContractError("snapshot_partition_duplicate")
        partition_lookup[key] = raw

    frames: dict[tuple[str, str], pd.DataFrame] = {}
    audit_rows: list[dict[str, Any]] = []
    for key in sorted(requirements):
        raw = partition_lookup.get(key)
        if raw is None:
            raise V36ContractError(f"snapshot_partition_missing:{key[0]}:{key[1]}")
        output_path = Path(str(raw.get("outputPath") or ""))
        expected_hash = str(raw.get("outputSha256") or "")
        if not output_path.is_file():
            raise V36ContractError(f"snapshot_partition_file_missing:{key[0]}:{key[1]}")
        actual_hash = _sha256(output_path)
        if not expected_hash or actual_hash != expected_hash:
            raise V36ContractError(f"snapshot_partition_hash_mismatch:{key[0]}:{key[1]}")
        frame = _normalize_frame(
            pd.read_parquet(output_path),
            development_start=start,
            development_end=end,
        )
        frames[key] = frame
        audit_rows.append(
            {
                "instrumentId": key[0],
                "timeframe": key[1],
                "outputPath": str(output_path.resolve()),
                "outputSha256": actual_hash,
                "rowCount": int(len(frame)),
                "firstTimestamp": frame["date"].iloc[0].isoformat(),
                "lastTimestamp": frame["date"].iloc[-1].isoformat(),
            }
        )
    audit = {
        "schemaVersion": "v36_development_snapshot_audit_v1",
        "snapshotId": str(expected_snapshot_id),
        "snapshotManifestPath": str(path),
        "snapshotManifestSha256": _sha256(path),
        "developmentStart": start.isoformat(),
        "developmentEnd": end.isoformat(),
        "verifiedPartitionCount": len(audit_rows),
        "partitions": audit_rows,
        "lockedOosReadCount": 0,
    }
    return frames, audit


def _requirements_for_registry(
    registry: ReplicationSourceRegistry,
) -> set[tuple[str, str]]:
    requirements: set[tuple[str, str]] = set()
    eligible_ids = {
        variant.candidate_id
        for family in registry.items
        if family.replication_state == "registered"
        for variant in family.variants
    }
    unknown = eligible_ids - set(_REPLAY_DEFINITIONS)
    if unknown:
        raise V36ContractError(f"development_replay_definition_missing:{sorted(unknown)[0]}")
    for candidate_id in sorted(eligible_ids):
        definition = _REPLAY_DEFINITIONS[candidate_id]
        timeframe = str(definition["timeframe"])
        family_id = str(definition["familyId"])
        if family_id == "crypto_pair_relative_value_v1":
            symbols = ("BTC-USDT-SWAP", "ETH-USDT-SWAP")
        elif family_id == "crypto_btc_downside_spillover_v1":
            symbols = tuple(
                dict.fromkeys(
                    ("BTC-USDT-SWAP",)
                    + tuple(str(value) for value in definition["targetSymbols"])
                )
            )
        else:
            symbols = _SYMBOLS
        requirements.update((symbol, timeframe) for symbol in symbols)
    return requirements


def _scaled_definition(candidate_id: str, scale: float) -> dict[str, Any]:
    if candidate_id not in _REPLAY_DEFINITIONS:
        raise V36ContractError(f"development_replay_definition_missing:{candidate_id}")
    if candidate_id in SELECTED_TSMOM_TRIALS:
        return scale_tsmom_definition(
            candidate_id,
            parameter_scale=float(scale),
        )
    result = dict(_REPLAY_DEFINITIONS[candidate_id])
    for key in (
        "lookbackBars",
        "entryDonchianBars",
        "exitDonchianBars",
        "windowBars",
        "residualWindowBars",
        "betaWindowBars",
        "lookbackSessions",
        "shockLookbackBars",
        "betaLookbackBars",
    ):
        if key in result:
            result[key] = max(8, int(round(float(result[key]) * scale)))
    for key in ("minimumMomentum", "entryZ"):
        if key in result:
            result[key] = float(result[key]) * scale
    if "minimumSessionMean" in result:
        result["minimumSessionMean"] = float(result["minimumSessionMean"]) * scale
    if "minimumShockReturn" in result:
        result["minimumShockReturn"] = float(result["minimumShockReturn"]) * scale
    result["parameterScale"] = float(scale)
    result["definitionHash"] = stable_hash(result, prefix="v36_replay_definition")
    return result


def _atr(frame: pd.DataFrame, window: int) -> pd.Series:
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


def _rolling_z(values: pd.Series, window: int) -> pd.Series:
    mean = values.rolling(window, min_periods=window).mean()
    std = values.rolling(window, min_periods=window).std(ddof=0).replace(0.0, np.nan)
    return (values - mean) / std


def _drawdown(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    equity = np.cumsum(np.asarray(values, dtype=float))
    peaks = np.maximum.accumulate(np.concatenate(([0.0], equity)))[:-1]
    return float(np.max(peaks - equity))


def _profit_factor(values: Sequence[float]) -> float:
    positive = sum(value for value in values if value > 0)
    negative = abs(sum(value for value in values if value < 0))
    if negative > 0:
        return float(positive / negative)
    return 10.0 if positive > 0 else 0.0


def _simulate_directional_trade(
    *,
    frame: pd.DataFrame,
    signal_index: int,
    side: int,
    atr_value: float,
    stop_atr: float,
    maximum_hold_bars: int,
    round_trip_cost_rate: float,
    exit_signal: pd.Series | None = None,
    regime: pd.Series | None = None,
) -> tuple[dict[str, Any] | None, int]:
    entry_index = signal_index + 1
    if entry_index >= len(frame) - 1 or not np.isfinite(atr_value) or atr_value <= 0:
        return None, signal_index + 1
    entry_price = float(frame.iloc[entry_index]["open"])
    risk_distance = float(atr_value * stop_atr)
    if risk_distance <= 0 or risk_distance / entry_price > 0.25:
        return None, entry_index + 1
    stop_price = entry_price - side * risk_distance
    last_index = min(len(frame) - 1, entry_index + maximum_hold_bars)
    exit_index = last_index
    exit_price = float(frame.iloc[last_index]["close"])
    exit_reason = "maximum_hold"
    maximum_favorable = 0.0
    maximum_adverse = 0.0

    for position in range(entry_index, last_index + 1):
        row = frame.iloc[position]
        favorable = (
            float(row["high"]) - entry_price
            if side > 0
            else entry_price - float(row["low"])
        )
        adverse = (
            float(row["low"]) - entry_price
            if side > 0
            else entry_price - float(row["high"])
        )
        maximum_favorable = max(maximum_favorable, favorable / risk_distance)
        maximum_adverse = min(maximum_adverse, adverse / risk_distance)
        stopped = float(row["low"]) <= stop_price if side > 0 else float(row["high"]) >= stop_price
        if stopped:
            exit_index = position
            exit_price = stop_price
            exit_reason = "initial_stop"
            break
        should_exit = bool(exit_signal.iloc[position]) if exit_signal is not None else False
        regime_break = regime is not None and not bool(regime.iloc[position])
        if should_exit or regime_break:
            execution_index = min(position + 1, len(frame) - 1)
            exit_index = execution_index
            exit_price = float(frame.iloc[execution_index]["open"])
            exit_reason = "signal_exit" if should_exit else "regime_break"
            break

    gross_r = side * (exit_price - entry_price) / risk_distance
    cost_r = round_trip_cost_rate * entry_price / risk_distance
    return (
        {
            "entryTimestampMs": int(frame.iloc[entry_index]["date"].timestamp() * 1000),
            "exitTimestampMs": int(frame.iloc[exit_index]["date"].timestamp() * 1000),
            "direction": "long" if side > 0 else "short",
            "grossR": float(gross_r),
            "costR": float(cost_r),
            "netR": float(gross_r - cost_r),
            "mfeR": float(maximum_favorable),
            "maeR": float(maximum_adverse),
            "exitReason": exit_reason,
        },
        exit_index + 1,
    )


def _directional_metrics(events: Sequence[Mapping[str, object]]) -> dict[str, Any]:
    values = [float(row["netR"]) for row in events]
    symbols: dict[str, int] = {}
    for row in events:
        symbol = str(row["instrumentId"])
        symbols[symbol] = symbols.get(symbol, 0) + 1
    event_count = len(events)
    average_net_r = float(np.mean(values)) if values else 0.0
    return {
        "eventCount": event_count,
        "profitFactor": _profit_factor(values),
        "averageNetR": average_net_r,
        "totalNetR": float(sum(values)),
        "mfe": float(np.mean([float(row["mfeR"]) for row in events])) if events else 0.0,
        "mae": float(np.mean([float(row["maeR"]) for row in events])) if events else 0.0,
        "totalCostR": float(sum(float(row["costR"]) for row in events)),
        "benchmarkIncrementNetR": average_net_r,
        "maxDrawdownR": _drawdown(values),
        "concentration": max(symbols.values()) / event_count if event_count else 1.0,
    }


def _replay_tsmom(
    *,
    frames: Mapping[tuple[str, str], pd.DataFrame],
    definition: Mapping[str, Any],
    round_trip_cost_rate: float,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    timeframe = str(definition["timeframe"])
    events: list[dict[str, Any]] = []
    for symbol in _SYMBOLS:
        frame = frames[(symbol, timeframe)].copy()
        lookback = int(definition["lookbackBars"])
        entry_bars = int(definition["entryDonchianBars"])
        exit_bars = int(definition["exitDonchianBars"])
        momentum = frame["close"] / frame["close"].shift(lookback) - 1.0
        upper = frame["high"].rolling(entry_bars, min_periods=entry_bars).max().shift(1)
        lower = frame["low"].rolling(entry_bars, min_periods=entry_bars).min().shift(1)
        exit_upper = frame["high"].rolling(exit_bars, min_periods=exit_bars).max().shift(1)
        exit_lower = frame["low"].rolling(exit_bars, min_periods=exit_bars).min().shift(1)
        long_signal = (momentum >= float(definition["minimumMomentum"])) & (frame["close"] > upper)
        short_signal = (momentum <= -float(definition["minimumMomentum"])) & (frame["close"] < lower)
        atr = _atr(frame, int(definition["atrBars"]))
        next_available = 0
        for signal_index in np.flatnonzero((long_signal | short_signal).fillna(False).to_numpy()):
            signal_index = int(signal_index)
            if signal_index < next_available:
                continue
            side = 1 if bool(long_signal.iloc[signal_index]) else -1
            exit_signal = frame["close"] < exit_lower if side > 0 else frame["close"] > exit_upper
            event, next_available = _simulate_directional_trade(
                frame=frame,
                signal_index=signal_index,
                side=side,
                atr_value=float(atr.iloc[signal_index]),
                stop_atr=float(definition["stopAtr"]),
                maximum_hold_bars=int(definition["maximumHoldBars"]),
                round_trip_cost_rate=round_trip_cost_rate,
                exit_signal=exit_signal.fillna(False),
            )
            if event is not None:
                event.update({"instrumentId": symbol, "setupName": "tsmom_turtle"})
                events.append(event)
    return _directional_metrics(events), events


def _aligned_pair(first: pd.DataFrame, second: pd.DataFrame) -> pd.DataFrame:
    columns = ["date", "open", "high", "low", "close", "volume"]
    return (
        first[columns]
        .merge(second[columns], on="date", suffixes=("A", "B"), how="inner")
        .sort_values("date")
        .reset_index(drop=True)
    )


def _half_life(residual: pd.Series) -> float:
    clean = pd.DataFrame({"lag": residual.shift(1), "delta": residual.diff()}).dropna()
    if len(clean) < 20 or float(clean["lag"].var()) <= 0:
        return 9999.0
    slope = float(clean["lag"].cov(clean["delta"]) / clean["lag"].var())
    return float(-math.log(2) / slope) if slope < 0 else 9999.0


def _replay_pair(
    *,
    frames: Mapping[tuple[str, str], pd.DataFrame],
    definition: Mapping[str, Any],
    round_trip_cost_rate: float,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    timeframe = str(definition["timeframe"])
    pair = _aligned_pair(
        frames[("ETH-USDT-SWAP", timeframe)],
        frames[("BTC-USDT-SWAP", timeframe)],
    )
    window = int(definition["windowBars"])
    return_a = pair["closeA"].pct_change()
    return_b = pair["closeB"].pct_change()
    variance_b = return_b.rolling(window, min_periods=window).var().replace(0.0, np.nan)
    beta = return_a.rolling(window, min_periods=window).cov(return_b) / variance_b
    residual_return = return_a - beta * return_b
    residual_level = residual_return.rolling(max(4, window // 8), min_periods=max(4, window // 8)).sum()
    zscore = _rolling_z(residual_level, window)
    correlation = return_a.rolling(window, min_periods=window).corr(return_b)
    signals = (zscore.abs() >= float(definition["entryZ"])) & (
        correlation >= float(definition["minimumCorrelation"])
    )
    events: list[dict[str, Any]] = []
    next_available = 0
    for signal_index in np.flatnonzero(signals.fillna(False).to_numpy()):
        signal_index = int(signal_index)
        if signal_index < next_available or signal_index + 1 >= len(pair):
            continue
        side = -1 if float(zscore.iloc[signal_index]) > 0 else 1
        entry_index = signal_index + 1
        entry_a = float(pair.iloc[entry_index]["openA"])
        entry_b = float(pair.iloc[entry_index]["openB"])
        hedge_beta = float(beta.iloc[signal_index])
        if not np.isfinite(hedge_beta) or hedge_beta <= 0:
            continue
        last_index = min(len(pair) - 1, entry_index + int(definition["maximumHoldBars"]))
        exit_index = last_index
        exit_reason = "maximum_hold"
        for position in range(entry_index, last_index + 1):
            current_z = float(zscore.iloc[position])
            current_correlation = float(correlation.iloc[position])
            if np.isfinite(current_z) and abs(current_z) <= float(definition["exitZ"]):
                exit_index = min(position + 1, len(pair) - 1)
                exit_reason = "residual_mean_cross"
                break
            if np.isfinite(current_correlation) and current_correlation < float(
                definition["breakCorrelation"]
            ):
                exit_index = min(position + 1, len(pair) - 1)
                exit_reason = "structural_break"
                break
        exit_a = float(pair.iloc[exit_index]["openA"])
        exit_b = float(pair.iloc[exit_index]["openB"])
        gross_return = side * ((exit_a / entry_a - 1.0) - hedge_beta * (exit_b / entry_b - 1.0))
        cost = round_trip_cost_rate * (1.0 + abs(hedge_beta))
        events.append(
            {
                "instrumentId": "ETH-USDT-SWAP/BTC-USDT-SWAP",
                "entryTimestampMs": int(pair.iloc[entry_index]["date"].timestamp() * 1000),
                "exitTimestampMs": int(pair.iloc[exit_index]["date"].timestamp() * 1000),
                "direction": "long_spread" if side > 0 else "short_spread",
                "grossReturn": float(gross_return),
                "costReturn": float(cost),
                "netReturn": float(gross_return - cost),
                "hedgeBeta": hedge_beta,
                "exitReason": exit_reason,
            }
        )
        next_available = exit_index + 1

    gross_values = [float(row["grossReturn"]) for row in events]
    net_values = [float(row["netReturn"]) for row in events]
    average_cost = float(np.mean([float(row["costReturn"]) for row in events])) if events else 0.0
    residual_stability = float((correlation >= float(definition["minimumCorrelation"])).mean())
    half_life = _half_life(residual_level)
    passive_pair_return = float(
        (pair["closeA"].iloc[-1] / pair["closeA"].iloc[0] - 1.0)
        - (pair["closeB"].iloc[-1] / pair["closeB"].iloc[0] - 1.0)
    )
    capacity = float(pair[["volumeA", "volumeB"]].min(axis=1).median())
    metrics = {
        "spreadReturn": float(np.mean(gross_values)) if gross_values else 0.0,
        "dualLegCostR": average_cost,
        "residualStability": residual_stability,
        "halfLife": half_life,
        "structuralBreakDetected": bool(
            (correlation < float(definition["breakCorrelation"])).fillna(False).any()
        ),
        "grossExposure": 1.0 + float(np.nanmedian(beta.to_numpy())) if beta.notna().any() else 2.0,
        "netExposure": abs(1.0 - float(np.nanmedian(beta.to_numpy()))) if beta.notna().any() else 0.0,
        "dualLegCapacity": capacity,
        "pairBenchmarkIncrement": (float(np.mean(net_values)) if net_values else 0.0) - passive_pair_return,
        "maxDrawdownR": _drawdown(net_values),
        "eventCount": len(events),
        "profitFactor": _profit_factor(net_values),
    }
    return metrics, events


def _market_residual_context(
    alt: pd.DataFrame,
    btc: pd.DataFrame,
    *,
    beta_window: int,
    residual_window: int,
    range_gap_maximum: float,
) -> tuple[pd.DataFrame, pd.Series, pd.Series]:
    pair = _aligned_pair(alt, btc)
    alt_return = pair["closeA"].pct_change()
    btc_return = pair["closeB"].pct_change()
    btc_variance = btc_return.rolling(beta_window, min_periods=beta_window).var().replace(0.0, np.nan)
    beta = alt_return.rolling(beta_window, min_periods=beta_window).cov(btc_return) / btc_variance
    residual = alt_return - beta * btc_return
    residual_excursion = residual.rolling(max(3, residual_window // 12), min_periods=max(3, residual_window // 12)).sum()
    residual_z = _rolling_z(residual_excursion, residual_window)
    btc_fast = pair["closeB"].ewm(span=50, adjust=False, min_periods=50).mean()
    btc_slow = pair["closeB"].ewm(span=200, adjust=False, min_periods=200).mean()
    range_regime = ((btc_fast / btc_slow - 1.0).abs() <= range_gap_maximum).fillna(False)
    normalized = pd.DataFrame(
        {
            "date": pair["date"],
            "open": pair["openA"],
            "high": pair["highA"],
            "low": pair["lowA"],
            "close": pair["closeA"],
            "volume": pair["volumeA"],
        }
    )
    return normalized, residual_z, range_regime


def _replay_conditional_mean_reversion(
    *,
    frames: Mapping[tuple[str, str], pd.DataFrame],
    definition: Mapping[str, Any],
    round_trip_cost_rate: float,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    timeframe = str(definition["timeframe"])
    btc = frames[("BTC-USDT-SWAP", timeframe)]
    events: list[dict[str, Any]] = []
    for symbol in ("ETH-USDT-SWAP", "SOL-USDT-SWAP"):
        frame, residual_z, range_regime = _market_residual_context(
            frames[(symbol, timeframe)],
            btc,
            beta_window=int(definition["betaWindowBars"]),
            residual_window=int(definition["residualWindowBars"]),
            range_gap_maximum=float(definition["rangeEmaGapMaximum"]),
        )
        signals = (residual_z.abs() >= float(definition["entryZ"])) & range_regime
        atr = _atr(frame, 20)
        next_available = 0
        for signal_index in np.flatnonzero(signals.fillna(False).to_numpy()):
            signal_index = int(signal_index)
            if signal_index < next_available:
                continue
            side = -1 if float(residual_z.iloc[signal_index]) > 0 else 1
            exit_signal = residual_z.abs() <= float(definition["exitZ"])
            event, next_available = _simulate_directional_trade(
                frame=frame,
                signal_index=signal_index,
                side=side,
                atr_value=float(atr.iloc[signal_index]),
                stop_atr=float(definition["stopAtr"]),
                maximum_hold_bars=int(definition["maximumHoldBars"]),
                round_trip_cost_rate=round_trip_cost_rate,
                exit_signal=exit_signal.fillna(False),
                regime=range_regime,
            )
            if event is not None:
                event.update(
                    {"instrumentId": symbol, "setupName": "conditional_residual_mean_reversion"}
                )
                events.append(event)
    return _directional_metrics(events), events


def build_development_evidence(
    *,
    registry: ReplicationSourceRegistry,
    preregistration: Mapping[str, Any],
    comparison_panel: Mapping[str, object],
    replay_config: Mapping[str, object],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Generate all real Development evidence from one frozen public snapshot."""

    manifest_path = Path(str(replay_config.get("snapshotManifestPath") or ""))
    cost_rate = float(replay_config.get("roundTripCostRate") or 0.0)
    if not 0.0 <= cost_rate <= 0.05:
        raise V36ContractError("round_trip_cost_rate_out_of_bounds")
    frames, snapshot_audit = load_development_frames(
        manifest_path=manifest_path,
        expected_snapshot_id=str(comparison_panel.get("dataSnapshotId") or ""),
        development_start=str(comparison_panel.get("developmentStart") or ""),
        development_end=str(comparison_panel.get("developmentEnd") or ""),
        requirements=_requirements_for_registry(registry),
    )
    family_by_candidate = {
        variant.candidate_id: family
        for family in registry.items
        for variant in family.variants
    }
    evidence: list[dict[str, Any]] = []
    trial_audit: list[dict[str, Any]] = []
    for candidate_id in sorted(preregistration.get("trialsByCandidate") or {}):
        family = family_by_candidate.get(candidate_id)
        if family is None:
            raise V36ContractError(f"candidate_not_registered:{candidate_id}")
        for trial in preregistration["trialsByCandidate"][candidate_id]:
            definition = _scaled_definition(candidate_id, float(trial["parameterScale"]))
            family_id = str(family.family_id)
            prefilter: dict[str, Any] | None = None
            if family_id == "crypto_tsmom_turtle_v1":
                metrics, events = _replay_tsmom(
                    frames=frames,
                    definition=definition,
                    round_trip_cost_rate=cost_rate,
                )
            elif family_id == "crypto_pair_relative_value_v1":
                metrics, events = _replay_pair(
                    frames=frames,
                    definition=definition,
                    round_trip_cost_rate=cost_rate,
                )
            elif family_id == "crypto_conditional_mean_reversion_v1":
                metrics, events = _replay_conditional_mean_reversion(
                    frames=frames,
                    definition=definition,
                    round_trip_cost_rate=cost_rate,
                )
            elif family_id == "crypto_intraday_session_predictability_v1":
                metrics, events, prefilter = replay_intraday_session(
                    frames=frames,
                    definition=definition,
                    round_trip_cost_rate=cost_rate,
                )
            elif family_id == "crypto_btc_downside_spillover_v1":
                metrics, events, prefilter = replay_btc_downside_spillover(
                    frames=frames,
                    definition=definition,
                    round_trip_cost_rate=cost_rate,
                )
            else:
                raise V36ContractError(f"development_replay_family_unsupported:{family_id}")
            evidence_row = {
                "candidateId": candidate_id,
                "trialId": trial["trialId"],
                "trialIndex": trial["trialIndex"],
                "strategyType": trial["strategyType"],
                "split": "development",
                "metrics": metrics,
                "definitionHash": definition["definitionHash"],
                "eventEvidenceHash": stable_hash(
                    events, prefix="v36_development_events"
                ),
                "lockedOosReadCount": 0,
            }
            if prefilter is not None:
                evidence_row["prefilterPassed"] = bool(prefilter["passed"])
                evidence_row["prefilter"] = prefilter
            evidence.append(evidence_row)
            trial_audit.append(
                {
                    "candidateId": candidate_id,
                    "trialId": trial["trialId"],
                    "trialIndex": trial["trialIndex"],
                    "strategyType": trial["strategyType"],
                    "timeframe": definition["timeframe"],
                    "definitionHash": definition["definitionHash"],
                    "eventCount": int(metrics.get("eventCount") or 0),
                    "eventEvidenceHash": stable_hash(events, prefix="v36_development_events"),
                }
            )
    audit = {
        "schemaVersion": "v36_development_replay_audit_v1",
        "status": "completed",
        "campaignId": preregistration.get("campaignId"),
        "comparisonPanelHash": preregistration.get("comparisonPanelHash"),
        "evidenceCount": len(evidence),
        "trialAudit": trial_audit,
        "snapshotAudit": snapshot_audit,
        "formalRunCount": 0,
        "resultReadCount": 0,
        "lockedOosReadCount": 0,
        "releaseCount": 0,
        "approvalCount": 0,
        "demoArm": False,
        "orderCount": 0,
        "privateAccountReadUsed": False,
        "tradeApiUsed": False,
        "withdrawApiUsed": False,
    }
    audit["auditHash"] = stable_hash(audit, prefix="v36_development_replay_audit")
    return evidence, audit
