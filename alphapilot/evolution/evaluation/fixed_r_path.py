"""Conservative actual-candle path evaluation for fixed reward/risk research."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class FixedRPathConfig:
    stopLossPct: float
    targetR: float
    horizonBars: int
    feeRate: float
    slippageRate: float
    latencyBars: int = 0
    slippageMultiplier: float = 1.0
    exitPolicy: str = "fixed_target_full_exit_v1"
    partialTargetFraction: float = 0.5
    runnerAtrMultiplier: float = 2.5
    runnerLockR: float = 1.0


@dataclass(frozen=True)
class FixedRPathResult:
    direction: str
    entryTimestampMs: int
    exitTimestampMs: int
    entryReferencePrice: float
    entryPrice: float
    exitReferencePrice: float
    exitPrice: float
    stopPrice: float
    targetPrice: float
    exitReason: str
    holdingBars: int
    grossR: float
    feeR: float
    slippageR: float
    fundingR: float
    netR: float
    mfeR: float
    maeR: float
    ambiguousPath: bool
    latencyBars: int
    slippageMultiplier: float
    exitPolicy: str = "fixed_target_full_exit_v1"
    plannedTargetR: float = 2.0
    partialExitFraction: float = 0.0
    partialExitTimestampMs: int | None = None
    partialExitReferencePrice: float | None = None
    partialExitPrice: float | None = None
    runnerStopPrice: float | None = None


@dataclass(frozen=True)
class PreparedFixedRExecutionPath:
    timestampsMs: np.ndarray
    opens: np.ndarray
    highs: np.ndarray
    lows: np.ndarray
    closes: np.ndarray
    atr14: np.ndarray
    fundingTimestampsMs: np.ndarray
    fundingRatePrefix: np.ndarray


def _validate_config(config: FixedRPathConfig) -> None:
    if not 0 < config.stopLossPct < 1:
        raise ValueError("fixed_r_stop_loss_pct_invalid")
    if config.targetR < 2:
        raise ValueError("fixed_r_target_below_2")
    if config.horizonBars < 1:
        raise ValueError("fixed_r_horizon_invalid")
    if config.feeRate < 0 or config.slippageRate < 0:
        raise ValueError("fixed_r_cost_invalid")
    if config.latencyBars < 0 or config.slippageMultiplier < 1:
        raise ValueError("fixed_r_stress_invalid")
    if config.exitPolicy not in {
        "fixed_target_full_exit_v1",
        "two_r_half_atr_runner_v1",
    }:
        raise ValueError(f"fixed_r_exit_policy_invalid:{config.exitPolicy}")
    if not 0 < config.partialTargetFraction < 1:
        raise ValueError("fixed_r_partial_fraction_invalid")
    if config.runnerAtrMultiplier <= 0 or config.runnerLockR < 0:
        raise ValueError("fixed_r_runner_invalid")


def _adverse_fill(reference: float, direction: str, *, entry: bool, rate: float) -> float:
    if direction == "long":
        multiplier = 1 + rate if entry else 1 - rate
    else:
        multiplier = 1 - rate if entry else 1 + rate
    return reference * multiplier


def _readonly(values: np.ndarray) -> np.ndarray:
    values.setflags(write=False)
    return values


def _wilder_atr(
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    window: int = 14,
) -> np.ndarray:
    result = np.full(len(closes), np.nan, dtype=np.float64)
    if not len(closes):
        return result
    previous = np.concatenate(([closes[0]], closes[:-1]))
    true_range = np.maximum(
        highs - lows,
        np.maximum(np.abs(highs - previous), np.abs(lows - previous)),
    )
    if len(true_range) < window:
        return result
    result[window - 1] = float(np.mean(true_range[:window]))
    for index in range(window, len(true_range)):
        result[index] = (
            result[index - 1] * (window - 1) + true_range[index]
        ) / window
    return result


def prepare_fixed_r_execution_path(
    executionFrame: pd.DataFrame,
    fundingFrame: pd.DataFrame | None = None,
) -> PreparedFixedRExecutionPath:
    required = {"timestamp_ms", "open", "high", "low", "close"}
    missing = sorted(required - set(executionFrame.columns))
    if missing:
        raise ValueError(f"fixed_r_execution_columns_missing:{','.join(missing)}")
    ordered = executionFrame.copy().sort_values("timestamp_ms").reset_index(drop=True)
    for column in ("timestamp_ms", "open", "high", "low", "close"):
        ordered[column] = pd.to_numeric(ordered[column], errors="coerce")
    ordered = ordered.dropna(subset=list(required))

    funding_timestamps = np.empty(0, dtype=np.int64)
    funding_rates = np.empty(0, dtype=np.float64)
    if fundingFrame is not None and not fundingFrame.empty:
        funding = fundingFrame.copy()
        if {"timestamp_ms", "funding_rate"}.issubset(funding.columns):
            funding["timestamp_ms"] = pd.to_numeric(
                funding["timestamp_ms"], errors="coerce"
            )
            funding["funding_rate"] = pd.to_numeric(
                funding["funding_rate"], errors="coerce"
            )
            funding = funding.dropna(subset=["timestamp_ms", "funding_rate"])
            funding = funding.sort_values("timestamp_ms")
            funding_timestamps = funding["timestamp_ms"].to_numpy(dtype=np.int64)
            funding_rates = funding["funding_rate"].to_numpy(dtype=np.float64)
    funding_prefix = np.concatenate(
        (np.zeros(1, dtype=np.float64), np.cumsum(funding_rates, dtype=np.float64))
    )
    timestamps = ordered["timestamp_ms"].to_numpy(dtype=np.int64)
    opens = ordered["open"].to_numpy(dtype=np.float64)
    highs = ordered["high"].to_numpy(dtype=np.float64)
    lows = ordered["low"].to_numpy(dtype=np.float64)
    closes = ordered["close"].to_numpy(dtype=np.float64)
    return PreparedFixedRExecutionPath(
        timestampsMs=_readonly(timestamps),
        opens=_readonly(opens),
        highs=_readonly(highs),
        lows=_readonly(lows),
        closes=_readonly(closes),
        atr14=_readonly(_wilder_atr(highs, lows, closes)),
        fundingTimestampsMs=_readonly(funding_timestamps),
        fundingRatePrefix=_readonly(funding_prefix),
    )


def _entry_index(
    signal_timestamp_ms: int,
    prepared_path: PreparedFixedRExecutionPath,
    config: FixedRPathConfig,
) -> int:
    index = int(
        np.searchsorted(
            prepared_path.timestampsMs,
            int(signal_timestamp_ms),
            side="right",
        )
    ) + config.latencyBars
    if index >= len(prepared_path.timestampsMs):
        raise ValueError("fixed_r_entry_bar_missing")
    return index


def _funding_cost_r(
    *,
    prepared_path: PreparedFixedRExecutionPath,
    entry_index: int,
    exit_index: int,
    partial_index: int | None,
    remaining_fraction: float,
    direction_sign: float,
    entry_reference: float,
    risk_value: float,
) -> float:
    if not len(prepared_path.fundingTimestampsMs):
        return 0.0
    entry_time = int(prepared_path.timestampsMs[entry_index])
    exit_time = int(prepared_path.timestampsMs[exit_index])
    start = int(np.searchsorted(prepared_path.fundingTimestampsMs, entry_time, side="left"))
    end = int(np.searchsorted(prepared_path.fundingTimestampsMs, exit_time, side="right"))
    if start >= end:
        return 0.0
    rates = np.diff(prepared_path.fundingRatePrefix)[start:end]
    timestamps = prepared_path.fundingTimestampsMs[start:end]
    if partial_index is None:
        weighted_sum = float(np.sum(rates))
    else:
        partial_time = int(prepared_path.timestampsMs[partial_index])
        weights = np.where(timestamps <= partial_time, 1.0, remaining_fraction)
        weighted_sum = float(np.sum(rates * weights))
    return direction_sign * weighted_sum * entry_reference / risk_value


def _evaluate_two_r_half_atr_runner(
    *,
    signal_timestamp_ms: int,
    direction: str,
    prepared_path: PreparedFixedRExecutionPath,
    config: FixedRPathConfig,
) -> FixedRPathResult:
    entry_index = _entry_index(signal_timestamp_ms, prepared_path, config)
    path_end = min(entry_index + config.horizonBars, len(prepared_path.timestampsMs))
    if path_end <= entry_index:
        raise ValueError("fixed_r_path_empty")

    slip_rate = config.slippageRate * config.slippageMultiplier
    entry_reference = float(prepared_path.opens[entry_index])
    if entry_reference <= 0:
        raise ValueError("fixed_r_entry_price_invalid")
    risk_value = entry_reference * config.stopLossPct
    direction_sign = 1.0 if direction == "long" else -1.0
    stop_price = entry_reference - direction_sign * risk_value
    target_price = entry_reference + direction_sign * risk_value * config.targetR
    lock_price = entry_reference + direction_sign * risk_value * config.runnerLockR

    partial_fraction = config.partialTargetFraction
    remaining_fraction = 1.0 - partial_fraction
    partial_index: int | None = None
    partial_reference: float | None = None
    runner_stop: float | None = None
    highest_close = entry_reference
    lowest_close = entry_reference
    exit_index = path_end - 1
    exit_reference = float(prepared_path.closes[exit_index])
    exit_reason = "time"
    ambiguous = False

    for absolute_index in range(entry_index, path_end):
        open_price = float(prepared_path.opens[absolute_index])
        high = float(prepared_path.highs[absolute_index])
        low = float(prepared_path.lows[absolute_index])
        active_stop = runner_stop if partial_index is not None and runner_stop is not None else stop_price
        if direction == "long":
            open_stop_hit = open_price <= active_stop
            open_target_hit = partial_index is None and open_price >= target_price
            stop_hit = low <= active_stop
            target_hit = partial_index is None and high >= target_price
        else:
            open_stop_hit = open_price >= active_stop
            open_target_hit = partial_index is None and open_price <= target_price
            stop_hit = high >= active_stop
            target_hit = partial_index is None and low <= target_price

        if open_stop_hit:
            exit_reference = open_price
            exit_reason = "runner_stop_gap" if partial_index is not None else "stop_gap"
            exit_index = absolute_index
            break
        if partial_index is None and not open_target_hit and stop_hit and target_hit:
            ambiguous = True
            exit_reference = stop_price
            exit_reason = "stop_both_hit"
            exit_index = absolute_index
            break
        if partial_index is None and stop_hit and not open_target_hit:
            exit_reference = stop_price
            exit_reason = "stop"
            exit_index = absolute_index
            break
        if partial_index is not None and stop_hit:
            exit_reference = active_stop
            exit_reason = "runner_stop"
            exit_index = absolute_index
            break
        if partial_index is None and (open_target_hit or target_hit):
            partial_index = absolute_index
            partial_reference = target_price

        close_price = float(prepared_path.closes[absolute_index])
        highest_close = max(highest_close, close_price)
        lowest_close = min(lowest_close, close_price)
        if partial_index is not None:
            atr = float(prepared_path.atr14[absolute_index])
            if direction == "long":
                candidate = lock_price
                if np.isfinite(atr):
                    candidate = max(candidate, highest_close - config.runnerAtrMultiplier * atr)
                runner_stop = max(runner_stop if runner_stop is not None else candidate, candidate)
            else:
                candidate = lock_price
                if np.isfinite(atr):
                    candidate = min(candidate, lowest_close + config.runnerAtrMultiplier * atr)
                runner_stop = min(runner_stop if runner_stop is not None else candidate, candidate)

    if partial_index is not None and exit_reason == "time":
        exit_reason = "runner_time"

    entry_fill = _adverse_fill(entry_reference, direction, entry=True, rate=slip_rate)
    tranches = (
        [(partial_fraction, float(partial_reference), int(partial_index))]
        if partial_index is not None and partial_reference is not None
        else []
    )
    tranches.append((remaining_fraction if partial_index is not None else 1.0, exit_reference, exit_index))
    filled_tranches = [
        (fraction, reference, index, _adverse_fill(reference, direction, entry=False, rate=slip_rate))
        for fraction, reference, index in tranches
    ]
    gross_r = sum(
        fraction * direction_sign * (reference - entry_reference) / risk_value
        for fraction, reference, _index, _fill in filled_tranches
    )
    slippage_quote = abs(entry_fill - entry_reference) + sum(
        fraction * abs(fill - reference)
        for fraction, reference, _index, fill in filled_tranches
    )
    slippage_r = slippage_quote / risk_value
    fee_r = (
        entry_fill + sum(fraction * fill for fraction, _reference, _index, fill in filled_tranches)
    ) * config.feeRate / risk_value
    funding_r = _funding_cost_r(
        prepared_path=prepared_path,
        entry_index=entry_index,
        exit_index=exit_index,
        partial_index=partial_index,
        remaining_fraction=remaining_fraction,
        direction_sign=direction_sign,
        entry_reference=entry_reference,
        risk_value=risk_value,
    )
    used_slice = slice(entry_index, exit_index + 1)
    if direction == "long":
        mfe_r = (float(np.max(prepared_path.highs[used_slice])) - entry_reference) / risk_value
        mae_r = (float(np.min(prepared_path.lows[used_slice])) - entry_reference) / risk_value
    else:
        mfe_r = (entry_reference - float(np.min(prepared_path.lows[used_slice]))) / risk_value
        mae_r = (entry_reference - float(np.max(prepared_path.highs[used_slice]))) / risk_value
    final_fill = filled_tranches[-1][3]
    partial_fill = filled_tranches[0][3] if partial_index is not None else None
    net_r = gross_r - fee_r - slippage_r - funding_r
    return FixedRPathResult(
        direction=direction,
        entryTimestampMs=int(prepared_path.timestampsMs[entry_index]),
        exitTimestampMs=int(prepared_path.timestampsMs[exit_index]),
        entryReferencePrice=entry_reference,
        entryPrice=entry_fill,
        exitReferencePrice=exit_reference,
        exitPrice=final_fill,
        stopPrice=stop_price,
        targetPrice=target_price,
        exitReason=exit_reason,
        holdingBars=exit_index - entry_index + 1,
        grossR=gross_r,
        feeR=fee_r,
        slippageR=slippage_r,
        fundingR=funding_r,
        netR=net_r,
        mfeR=mfe_r,
        maeR=mae_r,
        ambiguousPath=ambiguous,
        latencyBars=config.latencyBars,
        slippageMultiplier=config.slippageMultiplier,
        exitPolicy=config.exitPolicy,
        plannedTargetR=config.targetR,
        partialExitFraction=partial_fraction if partial_index is not None else 0.0,
        partialExitTimestampMs=(
            int(prepared_path.timestampsMs[partial_index])
            if partial_index is not None
            else None
        ),
        partialExitReferencePrice=partial_reference,
        partialExitPrice=partial_fill,
        runnerStopPrice=runner_stop,
    )


def evaluate_prepared_fixed_r_path(
    *,
    signalTimestampMs: int,
    direction: str,
    preparedPath: PreparedFixedRExecutionPath,
    config: FixedRPathConfig,
) -> FixedRPathResult:
    """Evaluate one signal against a prepared immutable candle path."""

    _validate_config(config)
    if direction not in {"long", "short"}:
        raise ValueError(f"fixed_r_direction_invalid:{direction}")
    if config.exitPolicy == "two_r_half_atr_runner_v1":
        return _evaluate_two_r_half_atr_runner(
            signal_timestamp_ms=signalTimestampMs,
            direction=direction,
            prepared_path=preparedPath,
            config=config,
        )
    entry_index = _entry_index(signalTimestampMs, preparedPath, config)
    path_end = min(entry_index + config.horizonBars, len(preparedPath.timestampsMs))
    if path_end <= entry_index:
        raise ValueError("fixed_r_path_empty")

    slip_rate = config.slippageRate * config.slippageMultiplier
    entry_reference = float(preparedPath.opens[entry_index])
    if entry_reference <= 0:
        raise ValueError("fixed_r_entry_price_invalid")
    risk_value = entry_reference * config.stopLossPct
    if direction == "long":
        stop_price = entry_reference - risk_value
        target_price = entry_reference + risk_value * config.targetR
    else:
        stop_price = entry_reference + risk_value
        target_price = entry_reference - risk_value * config.targetR

    exit_absolute_index = path_end - 1
    exit_reference = float(preparedPath.closes[exit_absolute_index])
    exit_reason = "time"
    ambiguous = False
    for absolute_index in range(entry_index, path_end):
        open_price = float(preparedPath.opens[absolute_index])
        high = float(preparedPath.highs[absolute_index])
        low = float(preparedPath.lows[absolute_index])
        if direction == "long":
            if open_price <= stop_price:
                exit_reference = open_price
                exit_reason = "stop_gap"
                exit_absolute_index = absolute_index
                break
            if open_price >= target_price:
                exit_reference = target_price
                exit_reason = "target_gap"
                exit_absolute_index = absolute_index
                break
            stop_hit = low <= stop_price
            target_hit = high >= target_price
        else:
            if open_price >= stop_price:
                exit_reference = open_price
                exit_reason = "stop_gap"
                exit_absolute_index = absolute_index
                break
            if open_price <= target_price:
                exit_reference = target_price
                exit_reason = "target_gap"
                exit_absolute_index = absolute_index
                break
            stop_hit = high >= stop_price
            target_hit = low <= target_price
        if stop_hit and target_hit:
            ambiguous = True
            exit_reference = stop_price
            exit_reason = "stop_both_hit"
            exit_absolute_index = absolute_index
            break
        if stop_hit:
            exit_reference = stop_price
            exit_reason = "stop"
            exit_absolute_index = absolute_index
            break
        if target_hit:
            exit_reference = target_price
            exit_reason = "target"
            exit_absolute_index = absolute_index
            break

    entry_fill = _adverse_fill(
        entry_reference, direction, entry=True, rate=slip_rate
    )
    exit_fill = _adverse_fill(
        exit_reference, direction, entry=False, rate=slip_rate
    )
    direction_sign = 1.0 if direction == "long" else -1.0
    gross_r = direction_sign * (exit_reference - entry_reference) / risk_value
    slippage_quote = abs(entry_fill - entry_reference) + abs(
        exit_fill - exit_reference
    )
    slippage_r = slippage_quote / risk_value
    fee_r = ((entry_fill + exit_fill) * config.feeRate) / risk_value
    funding_r = 0.0
    if len(preparedPath.fundingTimestampsMs):
        entry_time = int(preparedPath.timestampsMs[entry_index])
        exit_time = int(preparedPath.timestampsMs[exit_absolute_index])
        funding_start = int(
            np.searchsorted(
                preparedPath.fundingTimestampsMs, entry_time, side="left"
            )
        )
        funding_end = int(
            np.searchsorted(
                preparedPath.fundingTimestampsMs, exit_time, side="right"
            )
        )
        funding_sum = float(
            preparedPath.fundingRatePrefix[funding_end]
            - preparedPath.fundingRatePrefix[funding_start]
        )
        funding_r = direction_sign * funding_sum * entry_reference / risk_value
    used_slice = slice(entry_index, exit_absolute_index + 1)
    if direction == "long":
        mfe_r = (
            float(np.max(preparedPath.highs[used_slice])) - entry_reference
        ) / risk_value
        mae_r = (
            float(np.min(preparedPath.lows[used_slice])) - entry_reference
        ) / risk_value
    else:
        mfe_r = (
            entry_reference - float(np.min(preparedPath.lows[used_slice]))
        ) / risk_value
        mae_r = (
            entry_reference - float(np.max(preparedPath.highs[used_slice]))
        ) / risk_value
    net_r = gross_r - fee_r - slippage_r - funding_r
    return FixedRPathResult(
        direction=direction,
        entryTimestampMs=int(preparedPath.timestampsMs[entry_index]),
        exitTimestampMs=int(preparedPath.timestampsMs[exit_absolute_index]),
        entryReferencePrice=entry_reference,
        entryPrice=entry_fill,
        exitReferencePrice=exit_reference,
        exitPrice=exit_fill,
        stopPrice=stop_price,
        targetPrice=target_price,
        exitReason=exit_reason,
        holdingBars=exit_absolute_index - entry_index + 1,
        grossR=gross_r,
        feeR=fee_r,
        slippageR=slippage_r,
        fundingR=funding_r,
        netR=net_r,
        mfeR=mfe_r,
        maeR=mae_r,
        ambiguousPath=ambiguous,
        latencyBars=config.latencyBars,
        slippageMultiplier=config.slippageMultiplier,
        exitPolicy=config.exitPolicy,
        plannedTargetR=config.targetR,
    )


def evaluate_fixed_r_path(
    *,
    signalTimestampMs: int,
    direction: str,
    executionFrame: pd.DataFrame,
    config: FixedRPathConfig,
    fundingFrame: pd.DataFrame | None = None,
) -> FixedRPathResult:
    """Evaluate one signal after its timestamp without using future signal features."""
    prepared = prepare_fixed_r_execution_path(executionFrame, fundingFrame)
    return evaluate_prepared_fixed_r_path(
        signalTimestampMs=signalTimestampMs,
        direction=direction,
        preparedPath=prepared,
        config=config,
    )
