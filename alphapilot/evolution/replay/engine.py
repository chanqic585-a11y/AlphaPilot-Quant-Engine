"""No-lookahead next-bar replay with persistent position intervals."""

from __future__ import annotations

import math
from typing import Mapping, Sequence

import pandas as pd

from .types import ReplayConfig, ReplayResult, ReplaySignal, ReplayTrade, SkippedReplaySignal


def _validate_bars(frame: pd.DataFrame, instrument_id: str) -> pd.DataFrame:
    required = {"timestamp_ms", "open", "high", "low", "close"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"Missing replay fields for {instrument_id}: {', '.join(missing)}")
    result = frame.copy().sort_values("timestamp_ms").reset_index(drop=True)
    if result["timestamp_ms"].duplicated().any():
        raise ValueError(f"Duplicate replay timestamps for {instrument_id}")
    for column in ("timestamp_ms", "open", "high", "low", "close"):
        result[column] = pd.to_numeric(result[column], errors="coerce")
    if result[list(required)].isna().any().any():
        raise ValueError(f"Non-numeric replay bars for {instrument_id}")
    if "funding_rate" in result.columns:
        result["funding_rate"] = pd.to_numeric(result["funding_rate"], errors="coerce")
    return result


def _exit_fill(price: float, *, direction: str, slippage_rate: float) -> float:
    return price * (1 - slippage_rate) if direction == "long" else price * (1 + slippage_rate)


def _simulate_trade(
    signal: ReplaySignal,
    frame: pd.DataFrame,
    *,
    config: ReplayConfig,
) -> ReplayTrade | str:
    timestamp_to_index = {
        int(timestamp): index for index, timestamp in enumerate(frame["timestamp_ms"].tolist())
    }
    decision_index = timestamp_to_index.get(int(signal.decisionTimestampMs))
    if decision_index is None:
        return "decision_timestamp_missing"
    entry_index = decision_index + 1
    final_index = entry_index + config.maxHoldingBars - 1
    if final_index >= len(frame):
        return "incomplete_future_path"
    if signal.direction not in {"long", "short"}:
        return "invalid_direction"
    if not math.isfinite(signal.riskDistance) or signal.riskDistance <= 0:
        return "invalid_risk_distance"
    entry_base = float(frame.at[entry_index, "open"])
    entry_fill = entry_base * (
        1 + config.slippageRate if signal.direction == "long" else 1 - config.slippageRate
    )
    one_r = signal.riskDistance * config.stopLossR
    target_distance = one_r * (config.takeProfitR / config.stopLossR)
    if signal.direction == "long":
        stop_price = entry_fill - one_r
        target_price = entry_fill + target_distance
    else:
        stop_price = entry_fill + one_r
        target_price = entry_fill - target_distance
    if min(stop_price, target_price, entry_fill) <= 0:
        return "invalid_price_boundary"

    exit_index = final_index
    exit_base = float(frame.at[final_index, "close"])
    exit_reason = "timeout"
    ambiguous = False
    path = frame.iloc[entry_index : final_index + 1]
    for index, row in path.iterrows():
        if signal.direction == "long":
            stop_touched = float(row["low"]) <= stop_price
            target_touched = float(row["high"]) >= target_price
        else:
            stop_touched = float(row["high"]) >= stop_price
            target_touched = float(row["low"]) <= target_price
        if stop_touched:
            exit_index = int(index)
            exit_base = stop_price
            exit_reason = "stop"
            ambiguous = bool(target_touched)
            break
        if target_touched:
            exit_index = int(index)
            exit_base = target_price
            exit_reason = "target"
            break
    exit_fill = _exit_fill(
        exit_base, direction=signal.direction, slippage_rate=config.slippageRate
    )
    direction_sign = 1 if signal.direction == "long" else -1
    gross_amount = direction_sign * (exit_fill - entry_fill)
    fee_paid = (entry_fill + exit_fill) * config.feeRate
    slippage_paid = abs(entry_fill - entry_base) + abs(exit_fill - exit_base)
    funding_available = "funding_rate" in frame.columns and bool(
        frame.loc[entry_index:exit_index, "funding_rate"].notna().all()
    )
    funding_pnl = 0.0
    if funding_available:
        funding_sum = float(frame.loc[entry_index:exit_index, "funding_rate"].sum())
        funding_pnl = -direction_sign * entry_fill * funding_sum
    net_amount = gross_amount - fee_paid + funding_pnl
    observed = frame.iloc[entry_index : exit_index + 1]
    if signal.direction == "long":
        mfe_r = (float(observed["high"].max()) - entry_fill) / one_r
        mae_r = (entry_fill - float(observed["low"].min())) / one_r
    else:
        mfe_r = (entry_fill - float(observed["low"].min())) / one_r
        mae_r = (float(observed["high"].max()) - entry_fill) / one_r
    return ReplayTrade(
        signalId=signal.signalId,
        instrumentId=signal.instrumentId,
        timeframe=signal.timeframe,
        direction=signal.direction,
        decisionTimestampMs=int(signal.decisionTimestampMs),
        entryTimestampMs=int(frame.at[entry_index, "timestamp_ms"]),
        exitTimestampMs=int(frame.at[exit_index, "timestamp_ms"]),
        entryBasePrice=entry_base,
        entryFillPrice=entry_fill,
        exitBasePrice=exit_base,
        exitFillPrice=exit_fill,
        stopPrice=stop_price,
        targetPrice=target_price,
        exitReason=exit_reason,
        holdingBars=exit_index - entry_index + 1,
        grossR=gross_amount / one_r,
        netR=net_amount / one_r,
        grossReturn=gross_amount / entry_fill,
        netReturn=net_amount / entry_fill,
        feePaid=fee_paid,
        slippagePaid=slippage_paid,
        fundingPnl=funding_pnl,
        fundingDataAvailable=funding_available,
        mfeR=max(0.0, mfe_r),
        maeR=max(0.0, mae_r),
        sameBarAmbiguous=ambiguous,
        sourceEntityId=signal.sourceEntityId,
        strategyCandidateId=signal.strategyCandidateId,
    )


def _overlaps(left: ReplayTrade, right: ReplayTrade) -> bool:
    return left.entryTimestampMs <= right.exitTimestampMs and right.entryTimestampMs <= left.exitTimestampMs


def run_historical_replay(
    signals: Sequence[ReplaySignal],
    *,
    bars_by_instrument: Mapping[str, pd.DataFrame],
    config: ReplayConfig | None = None,
) -> ReplayResult:
    settings = config or ReplayConfig()
    settings.validate()
    bars = {
        instrument.upper(): _validate_bars(frame, instrument.upper())
        for instrument, frame in bars_by_instrument.items()
    }
    trades: list[ReplayTrade] = []
    skipped: list[SkippedReplaySignal] = []
    for signal in sorted(signals, key=lambda item: (item.decisionTimestampMs, item.signalId)):
        frame = bars.get(signal.instrumentId.upper())
        if frame is None:
            skipped.append(
                SkippedReplaySignal(
                    signal.signalId,
                    signal.instrumentId,
                    signal.decisionTimestampMs,
                    "instrument_bars_missing",
                )
            )
            continue
        simulated = _simulate_trade(signal, frame, config=settings)
        if isinstance(simulated, str):
            skipped.append(
                SkippedReplaySignal(
                    signal.signalId,
                    signal.instrumentId,
                    signal.decisionTimestampMs,
                    simulated,
                )
            )
            continue
        if any(
            trade.instrumentId == simulated.instrumentId and _overlaps(trade, simulated)
            for trade in trades
        ):
            skipped.append(
                SkippedReplaySignal(
                    signal.signalId,
                    signal.instrumentId,
                    signal.decisionTimestampMs,
                    "instrument_position_already_open",
                )
            )
            continue
        active_at_entry = sum(
            trade.entryTimestampMs <= simulated.entryTimestampMs <= trade.exitTimestampMs
            for trade in trades
        )
        if active_at_entry >= settings.maxConcurrentPositions:
            skipped.append(
                SkippedReplaySignal(
                    signal.signalId,
                    signal.instrumentId,
                    signal.decisionTimestampMs,
                    "portfolio_concurrency_limit",
                )
            )
            continue
        trades.append(simulated)
    return ReplayResult(settings, tuple(trades), tuple(skipped))
