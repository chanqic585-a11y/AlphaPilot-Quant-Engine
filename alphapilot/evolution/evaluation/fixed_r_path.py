"""Conservative actual-candle path evaluation for fixed reward/risk research."""

from __future__ import annotations

from dataclasses import dataclass

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


def evaluate_fixed_r_path(
    *,
    signalTimestampMs: int,
    direction: str,
    executionFrame: pd.DataFrame,
    config: FixedRPathConfig,
    fundingFrame: pd.DataFrame | None = None,
) -> FixedRPathResult:
    """Evaluate one signal after its timestamp without using future signal features."""

    _validate_config(config)
    if direction not in {"long", "short"}:
        raise ValueError(f"fixed_r_direction_invalid:{direction}")
    required = {"timestamp_ms", "open", "high", "low", "close"}
    missing = sorted(required - set(executionFrame.columns))
    if missing:
        raise ValueError(f"fixed_r_execution_columns_missing:{','.join(missing)}")
    ordered = executionFrame.copy().sort_values("timestamp_ms").reset_index(drop=True)
    for column in ("timestamp_ms", "open", "high", "low", "close"):
        ordered[column] = pd.to_numeric(ordered[column], errors="coerce")
    ordered = ordered.dropna(subset=list(required))
    eligible = ordered[ordered["timestamp_ms"] > int(signalTimestampMs)].reset_index(drop=True)
    if len(eligible) <= config.latencyBars:
        raise ValueError("fixed_r_entry_bar_missing")
    path = eligible.iloc[
        config.latencyBars : config.latencyBars + config.horizonBars
    ].reset_index(drop=True)
    if path.empty:
        raise ValueError("fixed_r_path_empty")

    slip_rate = config.slippageRate * config.slippageMultiplier
    entry_reference = float(path.iloc[0]["open"])
    if entry_reference <= 0:
        raise ValueError("fixed_r_entry_price_invalid")
    risk_value = entry_reference * config.stopLossPct
    if direction == "long":
        stop_price = entry_reference - risk_value
        target_price = entry_reference + risk_value * config.targetR
    else:
        stop_price = entry_reference + risk_value
        target_price = entry_reference - risk_value * config.targetR

    exit_reference = float(path.iloc[-1]["close"])
    exit_reason = "time"
    exit_index = len(path) - 1
    ambiguous = False
    for index, row in path.iterrows():
        open_price = float(row["open"])
        high = float(row["high"])
        low = float(row["low"])
        if direction == "long":
            if open_price <= stop_price:
                exit_reference, exit_reason, exit_index = open_price, "stop_gap", index
                break
            if open_price >= target_price:
                exit_reference, exit_reason, exit_index = target_price, "target_gap", index
                break
            stop_hit = low <= stop_price
            target_hit = high >= target_price
        else:
            if open_price >= stop_price:
                exit_reference, exit_reason, exit_index = open_price, "stop_gap", index
                break
            if open_price <= target_price:
                exit_reference, exit_reason, exit_index = target_price, "target_gap", index
                break
            stop_hit = high >= stop_price
            target_hit = low <= target_price
        if stop_hit and target_hit:
            ambiguous = True
            exit_reference, exit_reason, exit_index = (
                stop_price,
                "stop_both_hit",
                index,
            )
            break
        if stop_hit:
            exit_reference, exit_reason, exit_index = stop_price, "stop", index
            break
        if target_hit:
            exit_reference, exit_reason, exit_index = target_price, "target", index
            break

    used_path = path.iloc[: exit_index + 1]
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
    if fundingFrame is not None and not fundingFrame.empty:
        funding = fundingFrame.copy()
        if {"timestamp_ms", "funding_rate"}.issubset(funding.columns):
            funding["timestamp_ms"] = pd.to_numeric(
                funding["timestamp_ms"], errors="coerce"
            )
            funding["funding_rate"] = pd.to_numeric(
                funding["funding_rate"], errors="coerce"
            )
            entry_time = int(path.iloc[0]["timestamp_ms"])
            exit_time = int(path.iloc[exit_index]["timestamp_ms"])
            held = funding[
                funding["timestamp_ms"].between(entry_time, exit_time)
            ]
            funding_r = (
                direction_sign
                * float(held["funding_rate"].dropna().sum())
                * entry_reference
                / risk_value
            )
    if direction == "long":
        mfe_r = (float(used_path["high"].max()) - entry_reference) / risk_value
        mae_r = (float(used_path["low"].min()) - entry_reference) / risk_value
    else:
        mfe_r = (entry_reference - float(used_path["low"].min())) / risk_value
        mae_r = (entry_reference - float(used_path["high"].max())) / risk_value
    net_r = gross_r - fee_r - slippage_r - funding_r
    return FixedRPathResult(
        direction=direction,
        entryTimestampMs=int(path.iloc[0]["timestamp_ms"]),
        exitTimestampMs=int(path.iloc[exit_index]["timestamp_ms"]),
        entryReferencePrice=entry_reference,
        entryPrice=entry_fill,
        exitReferencePrice=exit_reference,
        exitPrice=exit_fill,
        stopPrice=stop_price,
        targetPrice=target_price,
        exitReason=exit_reason,
        holdingBars=exit_index + 1,
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
