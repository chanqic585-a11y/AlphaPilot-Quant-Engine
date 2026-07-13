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


@dataclass(frozen=True)
class PreparedFixedRExecutionPath:
    timestampsMs: np.ndarray
    opens: np.ndarray
    highs: np.ndarray
    lows: np.ndarray
    closes: np.ndarray
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


def _adverse_fill(reference: float, direction: str, *, entry: bool, rate: float) -> float:
    if direction == "long":
        multiplier = 1 + rate if entry else 1 - rate
    else:
        multiplier = 1 - rate if entry else 1 + rate
    return reference * multiplier


def _readonly(values: np.ndarray) -> np.ndarray:
    values.setflags(write=False)
    return values


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
    return PreparedFixedRExecutionPath(
        timestampsMs=_readonly(ordered["timestamp_ms"].to_numpy(dtype=np.int64)),
        opens=_readonly(ordered["open"].to_numpy(dtype=np.float64)),
        highs=_readonly(ordered["high"].to_numpy(dtype=np.float64)),
        lows=_readonly(ordered["low"].to_numpy(dtype=np.float64)),
        closes=_readonly(ordered["close"].to_numpy(dtype=np.float64)),
        fundingTimestampsMs=_readonly(funding_timestamps),
        fundingRatePrefix=_readonly(funding_prefix),
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
    entry_index = int(
        np.searchsorted(
            preparedPath.timestampsMs,
            int(signalTimestampMs),
            side="right",
        )
    ) + config.latencyBars
    if entry_index >= len(preparedPath.timestampsMs):
        raise ValueError("fixed_r_entry_bar_missing")
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
