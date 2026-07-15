"""Causal signal generation and fixed-risk event replay for Phase 3C."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .campaign_contract import CandidateSpec


def atr_series(frame: pd.DataFrame, window: int = 14) -> pd.Series:
    previous_close = frame["close"].shift(1)
    true_range = pd.concat(
        [
            frame["high"].sub(frame["low"]),
            frame["high"].sub(previous_close).abs(),
            frame["low"].sub(previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return true_range.rolling(window, min_periods=window).mean()


def align_funding_to_bars(frame: pd.DataFrame, funding: pd.DataFrame | None) -> pd.Series:
    if funding is None or funding.empty:
        return pd.Series(np.nan, index=frame.index, dtype=float)
    left = pd.DataFrame({"date": pd.to_datetime(frame["date"], utc=True)}).sort_values("date")
    right = funding[["timestampUtc", "fundingRate"]].copy()
    right["timestampUtc"] = pd.to_datetime(right["timestampUtc"], utc=True)
    right = right.dropna().drop_duplicates("timestampUtc", keep="last").sort_values("timestampUtc")
    aligned = pd.merge_asof(
        left,
        right,
        left_on="date",
        right_on="timestampUtc",
        direction="backward",
        allow_exact_matches=True,
    )
    return pd.Series(aligned["fundingRate"].to_numpy(dtype=float), index=left.index)


def build_signal_mask(
    *,
    candidate: CandidateSpec,
    frame: pd.DataFrame,
    benchmark_close: pd.Series | None = None,
    funding_rate: pd.Series | None = None,
) -> pd.Series:
    ordered = frame.reset_index(drop=True)
    close = pd.to_numeric(ordered["close"], errors="coerce")
    open_ = pd.to_numeric(ordered["open"], errors="coerce")
    volume = pd.to_numeric(ordered["volume"], errors="coerce")
    atr = atr_series(ordered)
    definition = candidate.eventDefinition
    if candidate.marketMechanismId == "volatility_compression_breakout":
        lookback = int(definition.get("breakoutBars", 20))
        quantile_window = int(definition.get("quantileWindow", 240))
        quantile = float(definition.get("compressionQuantile", 0.25))
        atr_pct = atr.div(close.replace(0, np.nan))
        threshold = atr_pct.rolling(quantile_window, min_periods=max(60, lookback * 3)).quantile(quantile)
        recently_compressed = atr_pct.le(threshold).shift(1).rolling(3, min_periods=1).max().fillna(False).astype(bool)
        prior_high = ordered["high"].shift(1).rolling(lookback, min_periods=lookback).max()
        prior_low = ordered["low"].shift(1).rolling(lookback, min_periods=lookback).min()
        volume_ratio = volume.div(volume.shift(1).rolling(lookback, min_periods=lookback).mean())
        minimum_volume = float(definition.get("minimumVolumeRatio", 1.0))
        signal = (
            close.gt(prior_high) if candidate.direction == "long" else close.lt(prior_low)
        ) & recently_compressed & volume_ratio.ge(minimum_volume)
    elif candidate.marketMechanismId == "idiosyncratic_shock_reversion":
        if benchmark_close is None:
            raise ValueError("benchmark_close is required for idiosyncratic shock reversion")
        benchmark = pd.Series(benchmark_close).reset_index(drop=True).reindex(ordered.index)
        horizon = int(definition.get("shockBars", 3))
        residual = close.pct_change(horizon).sub(benchmark.pct_change(horizon))
        window = int(definition.get("zscoreWindow", 120))
        mean = residual.rolling(window, min_periods=max(30, window // 2)).mean()
        std = residual.rolling(window, min_periods=max(30, window // 2)).std(ddof=0).replace(0, np.nan)
        zscore = residual.sub(mean).div(std)
        threshold = float(definition.get("zscoreThreshold", 2.0))
        signal = (
            zscore.le(-threshold) & close.gt(open_)
            if candidate.direction == "long"
            else zscore.ge(threshold) & close.lt(open_)
        )
    elif candidate.marketMechanismId == "funding_crowding_reversal":
        if funding_rate is None:
            raise ValueError("funding_rate is required for funding crowding reversal")
        rates = pd.Series(funding_rate).reset_index(drop=True).reindex(ordered.index)
        window = int(definition.get("fundingWindow", 180))
        mean = rates.rolling(window, min_periods=max(45, window // 2)).mean()
        std = rates.rolling(window, min_periods=max(45, window // 2)).std(ddof=0).replace(0, np.nan)
        zscore = rates.sub(mean).div(std)
        threshold = float(definition.get("fundingZscore", 1.5))
        price_move = close.pct_change(int(definition.get("confirmationBars", 3)))
        signal = (
            zscore.le(-threshold) & price_move.le(0) & close.gt(open_)
            if candidate.direction == "long"
            else zscore.ge(threshold) & price_move.ge(0) & close.lt(open_)
        )
    else:
        raise ValueError(f"unsupported market mechanism: {candidate.marketMechanismId}")
    return signal.fillna(False).astype(bool)


def replay_signal(
    *,
    frame: pd.DataFrame,
    signal_position: int,
    candidate: CandidateSpec,
    atr_value: float,
    fee_bps_per_side: float,
    slippage_bps_per_side: float,
    spread_bps_per_side: float,
    funding_rate: pd.Series | None = None,
) -> dict[str, Any] | None:
    entry_position = signal_position + 1
    if entry_position >= len(frame) or not np.isfinite(atr_value) or atr_value <= 0:
        return None
    entry_price = float(frame.iloc[entry_position]["open"])
    risk_distance = float(candidate.stopAtr * atr_value)
    if not np.isfinite(entry_price) or entry_price <= 0 or risk_distance <= 0:
        return None
    direction = 1 if candidate.direction == "long" else -1
    stop_price = entry_price - direction * risk_distance
    target_price = entry_price + direction * candidate.targetR * risk_distance
    final_position = min(len(frame) - 1, entry_position + candidate.maximumHoldBars - 1)
    exit_position = final_position
    exit_price = float(frame.iloc[final_position]["close"])
    exit_reason = "maximum_hold"
    ambiguous = False
    for position in range(entry_position, final_position + 1):
        row = frame.iloc[position]
        high, low = float(row["high"]), float(row["low"])
        stop_hit = low <= stop_price if direction == 1 else high >= stop_price
        target_hit = high >= target_price if direction == 1 else low <= target_price
        if stop_hit and target_hit:
            ambiguous = True
            exit_position, exit_price, exit_reason = position, stop_price, "stop_loss"
            break
        if stop_hit:
            exit_position, exit_price, exit_reason = position, stop_price, "stop_loss"
            break
        if target_hit:
            exit_position, exit_price, exit_reason = position, target_price, "target"
            break
    gross_r = direction * (exit_price - entry_price) / risk_distance
    price_scale = (entry_price + abs(exit_price)) / risk_distance
    fees_r = price_scale * fee_bps_per_side / 10_000
    slippage_r = price_scale * slippage_bps_per_side / 10_000
    spread_r = price_scale * spread_bps_per_side / 10_000
    funding_r = 0.0
    if funding_rate is not None:
        rates = pd.to_numeric(funding_rate.iloc[entry_position : exit_position + 1], errors="coerce").dropna()
        funding_r = float(rates.sum()) * direction * entry_price / risk_distance
    net_r = gross_r - fees_r - slippage_r - spread_r - funding_r
    return {
        "signalTimestamp": pd.Timestamp(frame.iloc[signal_position]["date"]).isoformat(),
        "entryTimestamp": pd.Timestamp(frame.iloc[entry_position]["date"]).isoformat(),
        "exitTimestamp": pd.Timestamp(frame.iloc[exit_position]["date"]).isoformat(),
        "signalPosition": signal_position,
        "entryPosition": entry_position,
        "exitPosition": exit_position,
        "entryReference": "next_bar_open",
        "entryPrice": entry_price,
        "stopPrice": stop_price,
        "targetPrice": target_price,
        "targetR": candidate.targetR,
        "exitPrice": exit_price,
        "exitReason": exit_reason,
        "ambiguousPath": ambiguous,
        "grossR": round(float(gross_r), 10),
        "feesR": round(float(fees_r), 10),
        "slippageR": round(float(slippage_r), 10),
        "fundingR": round(float(funding_r), 10),
        "spreadProxyR": round(float(spread_r), 10),
        "netR": round(float(net_r), 10),
    }


def replay_candidate_events(
    *,
    candidate: CandidateSpec,
    frame: pd.DataFrame,
    benchmark_close: pd.Series | None,
    funding_rate: pd.Series | None,
    costs: dict[str, float],
) -> list[dict[str, Any]]:
    ordered = frame.sort_values("date").drop_duplicates("date", keep="last").reset_index(drop=True)
    aligned_funding = (
        pd.Series(funding_rate).reset_index(drop=True).reindex(ordered.index)
        if funding_rate is not None
        else None
    )
    mask = build_signal_mask(
        candidate=candidate,
        frame=ordered,
        benchmark_close=benchmark_close,
        funding_rate=aligned_funding,
    )
    atr = atr_series(ordered)
    events: list[dict[str, Any]] = []
    next_allowed_position = 0
    for position in np.flatnonzero(mask.to_numpy()):
        if position < next_allowed_position:
            continue
        event = replay_signal(
            frame=ordered,
            signal_position=int(position),
            candidate=candidate,
            atr_value=float(atr.iloc[position]),
            fee_bps_per_side=float(costs["feeBpsPerSide"]),
            slippage_bps_per_side=float(costs["slippageBpsPerSide"]),
            spread_bps_per_side=float(costs["spreadProxyBpsPerSide"]),
            funding_rate=aligned_funding,
        )
        if event is not None:
            events.append(event)
            next_allowed_position = int(event["exitPosition"]) + 1
    return events
