"""Batch research candidate factory for low-frequency AlphaPilot strategies.

This module is report-only. It reads local public OHLCV files and replays
deterministic candidate rules. It does not download data, call exchange APIs,
read accounts or positions, create orders, enter exchange Dry-run, or automate
trading.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from alphapilot.factors.ohlcv_loader import discover_ohlcv_files
from alphapilot.low_frequency.factor_confluence_backtest import (
    FactorConfluenceBacktestConfig,
    _align_btc_context,
    _baseline_comparison,
    _build_btc_regime_proxy,
    _group_metrics,
    _iso,
    _load_frames,
    _metrics,
    _prepare_indicators,
    _round,
    _walk_forward_metrics,
)


DEFAULT_DATA_PATH = Path("user_data/data/okx/futures")
DEFAULT_TIMERANGE = "20200101-"
DEFAULT_TIMEFRAMES = ("4h", "1d")
DEFAULT_REWARD_RISK = 2.0
DEFAULT_FEE_RATE = 0.0005
DEFAULT_SLIPPAGE_RATE = 0.0005


@dataclass(frozen=True)
class StrategyCandidateSpec:
    candidate_id: str
    display_name: str
    family: str
    timeframe: str
    btc_regimes: tuple[str, ...]
    atr_multiplier: float
    max_hold_bars: int
    min_volume_ratio: float
    rsi_min: float | None = None
    rsi_max: float | None = None
    pullback_low: float = 0.98
    pullback_high: float = 1.02
    breakout_multiplier: float = 1.0
    bb_width_multiplier: float = 1.35
    momentum_return_min: float = 0.0
    mean_reversion_low_multiplier: float = 1.01
    ema200_floor_multiplier: float = 0.92
    btc_return_24h_min_pct: float = -8.0
    btc_return_3d_min_pct: float = -10.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidateId": self.candidate_id,
            "displayName": self.display_name,
            "family": self.family,
            "timeframe": self.timeframe,
            "btcRegimes": list(self.btc_regimes),
            "atrMultiplier": self.atr_multiplier,
            "targetRewardRiskRatio": DEFAULT_REWARD_RISK,
            "maxHoldBars": self.max_hold_bars,
            "minVolumeRatio": self.min_volume_ratio,
            "rsiMin": self.rsi_min,
            "rsiMax": self.rsi_max,
            "pullbackLow": self.pullback_low,
            "pullbackHigh": self.pullback_high,
            "breakoutMultiplier": self.breakout_multiplier,
            "bbWidthMultiplier": self.bb_width_multiplier,
            "momentumReturnMin": self.momentum_return_min,
            "meanReversionLowMultiplier": self.mean_reversion_low_multiplier,
            "ema200FloorMultiplier": self.ema200_floor_multiplier,
            "btcReturn24hMinPct": self.btc_return_24h_min_pct,
            "btcReturn3dMinPct": self.btc_return_3d_min_pct,
        }


def _finite(value: Any) -> bool:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    return not (math.isnan(number) or math.isinf(number))


def _prepare_candidate_frame(frame: pd.DataFrame, btc_regime: pd.DataFrame) -> pd.DataFrame:
    data = _align_btc_context(_prepare_indicators(frame), btc_regime)
    close = data["close"].astype(float)
    data["hh20"] = close.rolling(20, min_periods=20).max().shift(1)
    data["hh55"] = close.rolling(55, min_periods=55).max().shift(1)
    data["ll20"] = close.rolling(20, min_periods=20).min().shift(1)
    data["ret3"] = close.pct_change(3)
    data["ret6"] = close.pct_change(6)
    data["ema20Slope"] = data["ema20"] / data["ema20"].shift(3) - 1
    data["macdHistPrev"] = data["macdHist"].shift(1)
    data["wasBelowEma20"] = close.shift(1) < data["ema20"].shift(1)
    return data


def _load_prepared_frames(
    data_path: Path,
    timerange: str,
    timeframe: str,
) -> tuple[FactorConfluenceBacktestConfig, dict[str, pd.DataFrame], list[str]]:
    config = FactorConfluenceBacktestConfig(data_path=data_path, timerange=timerange, timeframe=timeframe)
    frames, warnings = _load_frames(config)
    btc = frames.get("BTC/USDT:USDT")
    if btc is None:
        warnings.append(f"BTC/USDT:USDT {timeframe} data is required for candidate factory regime gating.")
        return config, {}, warnings
    btc_regime = _build_btc_regime_proxy(btc)
    prepared: dict[str, pd.DataFrame] = {}
    for pair, frame in frames.items():
        if pair == "BTC/USDT:USDT":
            continue
        prepared[pair] = _prepare_candidate_frame(frame, btc_regime)
    return config, prepared, warnings


def _between(series: pd.Series, lower: float | None, upper: float | None) -> pd.Series:
    mask = pd.Series(True, index=series.index)
    if lower is not None:
        mask &= series >= lower
    if upper is not None:
        mask &= series <= upper
    return mask


def _base_mask(data: pd.DataFrame, spec: StrategyCandidateSpec) -> pd.Series:
    mask = pd.Series(True, index=data.index)
    mask &= data["btcPrimaryRegime"].isin(spec.btc_regimes)
    mask &= data["btcReturn24hPct"].isna() | (data["btcReturn24hPct"] > spec.btc_return_24h_min_pct)
    mask &= data["btcReturn3dPct"].isna() | (data["btcReturn3dPct"] > spec.btc_return_3d_min_pct)
    required = ["ema20", "ema50", "ema200", "rsi14", "macdHist", "atr14", "volumeRatio"]
    for column in required:
        mask &= data[column].notna()
    mask &= data["atr14"] > 0
    mask &= data["volumeRatio"] >= spec.min_volume_ratio
    mask &= _between(data["rsi14"], spec.rsi_min, spec.rsi_max)
    return mask


def _signal_mask(data: pd.DataFrame, spec: StrategyCandidateSpec) -> pd.Series:
    close = data["close"].astype(float)
    low = data["low"].astype(float)
    trend_up = (close > data["ema200"]) & (data["ema20"] > data["ema50"])
    trend_stack = trend_up & (data["ema50"] > data["ema200"])
    macd_improving = (data["macdHist"] > data["macdHistPrev"]) & data["macdHistPrev"].notna()
    macd_positive_or_improving = (data["macdHist"] > 0) | macd_improving
    bb_not_expanded = data["bbWidthPct"].notna() & data["bbWidthMedian120"].notna() & (
        data["bbWidthPct"] <= data["bbWidthMedian120"] * spec.bb_width_multiplier
    )

    mask = _base_mask(data, spec)
    if spec.family == "trend_pullback":
        return mask & trend_stack & macd_improving & bb_not_expanded & (
            low <= data["ema20"] * spec.pullback_high
        ) & (
            close >= data["ema20"] * spec.pullback_low
        )
    if spec.family == "breakout":
        return mask & trend_up & macd_positive_or_improving & data["hh20"].notna() & (
            close > data["hh20"] * spec.breakout_multiplier
        )
    if spec.family == "squeeze_breakout":
        return mask & trend_up & macd_positive_or_improving & bb_not_expanded & data["hh20"].notna() & (
            close > data["hh20"] * spec.breakout_multiplier
        )
    if spec.family == "continuation":
        return mask & trend_stack & macd_positive_or_improving & (close > data["ema20"]) & (
            data["ret3"] >= spec.momentum_return_min
        )
    if spec.family == "recovery_reclaim":
        return mask & (close > data["ema200"] * spec.ema200_floor_multiplier) & data["wasBelowEma20"] & (
            close > data["ema20"]
        ) & macd_improving
    if spec.family == "mean_reversion":
        return mask & (close > data["ema200"] * spec.ema200_floor_multiplier) & data["ll20"].notna() & (
            close <= data["ll20"] * spec.mean_reversion_low_multiplier
        )
    if spec.family == "low_vol_trend":
        return mask & trend_up & (data["ema20Slope"] > 0) & bb_not_expanded & (close > data["ema20"])
    raise ValueError(f"Unsupported candidate family: {spec.family}")


def _simulate_candidate(
    spec: StrategyCandidateSpec,
    prepared_frames: dict[str, pd.DataFrame],
) -> list[dict[str, Any]]:
    trades: list[dict[str, Any]] = []
    for pair, data in prepared_frames.items():
        signals = _signal_mask(data, spec).fillna(False).to_numpy()
        index = 201
        while index < len(data) - 2:
            if not signals[index]:
                index += 1
                continue
            row = data.iloc[index]
            if not _finite(row.atr14) or float(row.atr14) <= 0:
                index += 1
                continue

            entry_index = index + 1
            entry_row = data.iloc[entry_index]
            entry_base = float(entry_row.open)
            entry_price = entry_base * (1 + DEFAULT_SLIPPAGE_RATE)
            risk_per_unit = float(row.atr14) * spec.atr_multiplier
            if risk_per_unit <= 0 or entry_price <= risk_per_unit:
                index += 1
                continue

            stop_price = entry_price - risk_per_unit
            target_price = entry_price + risk_per_unit * DEFAULT_REWARD_RISK
            exit_index = min(entry_index + spec.max_hold_bars, len(data) - 1)
            exit_base = float(data.iloc[exit_index].close)
            exit_reason = "time_stop"

            for cursor in range(entry_index, min(entry_index + spec.max_hold_bars + 1, len(data))):
                candle = data.iloc[cursor]
                if float(candle.low) <= stop_price:
                    exit_index = cursor
                    exit_base = stop_price
                    exit_reason = "stop_loss"
                    break
                if float(candle.high) >= target_price:
                    exit_index = cursor
                    exit_base = target_price
                    exit_reason = "target_2r"
                    break

            exit_price = exit_base * (1 - DEFAULT_SLIPPAGE_RATE)
            gross_r = (exit_price - entry_price) / risk_per_unit
            fee_r = DEFAULT_FEE_RATE * (entry_price + exit_price) / risk_per_unit
            net_r = gross_r - fee_r
            trades.append(
                {
                    "candidateId": spec.candidate_id,
                    "pair": pair,
                    "entryTimestamp": _iso(entry_row.date),
                    "exitTimestamp": _iso(data.iloc[exit_index].date),
                    "entryPrice": _round(entry_price, 8),
                    "exitPrice": _round(exit_price, 8),
                    "stopPrice": _round(stop_price, 8),
                    "targetPrice": _round(target_price, 8),
                    "grossR": _round(gross_r, 6),
                    "feeR": _round(fee_r, 6),
                    "netR": _round(net_r, 6),
                    "exitReason": exit_reason,
                    "holdBars": int(exit_index - entry_index + 1),
                    "btcPrimaryRegime": row.btcPrimaryRegime,
                    "rsi14": _round(row.rsi14),
                    "macdHist": _round(row.macdHist, 8),
                    "volumeRatio": _round(row.volumeRatio),
                    "atrPct": _round(row.atrPct),
                    "bbWidthPct": _round(row.bbWidthPct),
                }
            )
            index = exit_index + 1
    return trades


def _split_pass(row: dict[str, Any], *, min_trades: int, min_pf: float) -> bool:
    return (
        row.get("tradeCount", 0) >= min_trades
        and row.get("totalReturnPct") is not None
        and row["totalReturnPct"] > 0
        and row.get("profitFactor") is not None
        and row["profitFactor"] >= min_pf
    )


def _approval(candidate: dict[str, Any]) -> dict[str, Any]:
    metrics = candidate["metrics"]
    splits = {row["splitId"]: row for row in candidate["walkForward"]}
    timeframe = candidate["spec"]["timeframe"]
    min_total = 60 if timeframe == "4h" else 25
    min_split_trades = 10 if timeframe == "4h" else 4
    checks = {
        "minTradeCount": metrics.get("tradeCount", 0) >= min_total,
        "targetRewardRiskRatio": metrics.get("targetRewardRiskRatio") == DEFAULT_REWARD_RISK,
        "minProfitFactor": metrics.get("profitFactor") is not None and metrics["profitFactor"] >= 1.15,
        "positiveReturn": metrics.get("totalReturnPct") is not None and metrics["totalReturnPct"] > 0,
        "maxDrawdownPct": metrics.get("maxDrawdownPct") is not None and metrics["maxDrawdownPct"] <= 30,
        "trainPositive": _split_pass(splits.get("train_2020_2022", {}), min_trades=min_split_trades, min_pf=1.0),
        "validationPositive": _split_pass(splits.get("validation_2023_2024", {}), min_trades=min_split_trades, min_pf=1.0),
        "testPositive": _split_pass(splits.get("test_2025_2026", {}), min_trades=min_split_trades, min_pf=1.0),
    }
    return {
        "gateId": "v13_7_20_five_strategy_research_gate",
        "checks": checks,
        "passed": all(checks.values()),
        "paperObservationApproved": all(checks.values()),
        "dryRunApproved": False,
        "liveTradingApproved": False,
    }


def _score(metrics: dict[str, Any], approval: dict[str, Any]) -> float:
    profit_factor = metrics.get("profitFactor") or 0
    total_return = metrics.get("totalReturnPct") or 0
    max_drawdown = metrics.get("maxDrawdownPct") or 0
    trade_count = min(metrics.get("tradeCount", 0), 200)
    bonus = 500 if approval.get("passed") else 0
    return round(bonus + profit_factor * 100 + total_return * 2 + trade_count * 0.15 - max_drawdown * 2, 4)


def _candidate_specs() -> list[StrategyCandidateSpec]:
    specs: list[StrategyCandidateSpec] = []
    counter = 1

    def add(display: str, family: str, timeframe: str, btc: tuple[str, ...], **kwargs: Any) -> None:
        nonlocal counter
        specs.append(
            StrategyCandidateSpec(
                candidate_id=f"lf_research_candidate_{counter:03d}",
                display_name=display,
                family=family,
                timeframe=timeframe,
                btc_regimes=btc,
                **kwargs,
            )
        )
        counter += 1

    btc_sets = {
        "sideways": ("sideways",),
        "trend": ("bull", "recovery"),
        "broad": ("sideways", "bull", "recovery"),
    }
    for timeframe in DEFAULT_TIMEFRAMES:
        is_4h = timeframe == "4h"
        pull_hold = 42 if is_4h else 18
        breakout_hold = 36 if is_4h else 16
        cont_hold = 30 if is_4h else 14
        mr_hold = 42 if is_4h else 18
        for btc_name, btc in btc_sets.items():
            for atr in (1.2, 1.5, 1.8):
                add(
                    f"{timeframe} {btc_name} trend pullback confluence ATR{atr}",
                    "trend_pullback",
                    timeframe,
                    btc,
                    atr_multiplier=atr,
                    max_hold_bars=pull_hold,
                    min_volume_ratio=1.0,
                    rsi_min=42,
                    rsi_max=66,
                    pullback_low=0.98,
                    pullback_high=1.02,
                    bb_width_multiplier=1.55,
                )
                add(
                    f"{timeframe} {btc_name} conservative pullback ATR{atr}",
                    "trend_pullback",
                    timeframe,
                    btc,
                    atr_multiplier=atr,
                    max_hold_bars=pull_hold,
                    min_volume_ratio=1.15,
                    rsi_min=48,
                    rsi_max=68,
                    pullback_low=0.99,
                    pullback_high=1.015,
                    bb_width_multiplier=1.25,
                )
            for atr in (1.2, 1.5, 2.0):
                add(
                    f"{timeframe} {btc_name} breakout confirmation ATR{atr}",
                    "breakout",
                    timeframe,
                    btc,
                    atr_multiplier=atr,
                    max_hold_bars=breakout_hold,
                    min_volume_ratio=1.2,
                    rsi_min=50,
                    rsi_max=76,
                    breakout_multiplier=0.998,
                )
                add(
                    f"{timeframe} {btc_name} squeeze breakout ATR{atr}",
                    "squeeze_breakout",
                    timeframe,
                    btc,
                    atr_multiplier=atr,
                    max_hold_bars=breakout_hold,
                    min_volume_ratio=1.1,
                    rsi_min=48,
                    rsi_max=76,
                    breakout_multiplier=0.998,
                    bb_width_multiplier=0.95,
                )
            for atr in (1.2, 1.5, 1.8):
                add(
                    f"{timeframe} {btc_name} momentum continuation ATR{atr}",
                    "continuation",
                    timeframe,
                    btc,
                    atr_multiplier=atr,
                    max_hold_bars=cont_hold,
                    min_volume_ratio=1.0,
                    rsi_min=50,
                    rsi_max=78,
                    momentum_return_min=0.01 if is_4h else 0.015,
                )
                add(
                    f"{timeframe} {btc_name} recovery reclaim ATR{atr}",
                    "recovery_reclaim",
                    timeframe,
                    btc,
                    atr_multiplier=atr,
                    max_hold_bars=cont_hold,
                    min_volume_ratio=1.0,
                    rsi_min=38,
                    rsi_max=64,
                    ema200_floor_multiplier=0.9,
                )
        for atr in (1.0, 1.2, 1.5):
            add(
                f"{timeframe} sideways oversold reclaim ATR{atr}",
                "mean_reversion",
                timeframe,
                btc_sets["sideways"],
                atr_multiplier=atr,
                max_hold_bars=mr_hold,
                min_volume_ratio=0.7,
                rsi_max=40,
                mean_reversion_low_multiplier=1.02,
                ema200_floor_multiplier=0.86,
            )
            add(
                f"{timeframe} broad low-vol trend ATR{atr}",
                "low_vol_trend",
                timeframe,
                btc_sets["broad"],
                atr_multiplier=atr,
                max_hold_bars=cont_hold,
                min_volume_ratio=0.85,
                rsi_min=48,
                rsi_max=72,
                bb_width_multiplier=0.9,
            )
    return specs


def run_strategy_candidate_factory(
    *,
    data_path: Path = DEFAULT_DATA_PATH,
    timerange: str = DEFAULT_TIMERANGE,
    max_approved: int = 5,
) -> dict[str, Any]:
    warnings: list[str] = []
    available_timeframes = sorted(
        {
            timeframe
            for timeframe in DEFAULT_TIMEFRAMES
            if discover_ohlcv_files(data_path, timeframe)
        }
    )
    prepared_by_timeframe: dict[str, tuple[FactorConfluenceBacktestConfig, dict[str, pd.DataFrame]]] = {}
    for timeframe in available_timeframes:
        config, prepared, load_warnings = _load_prepared_frames(data_path, timerange, timeframe)
        warnings.extend(load_warnings)
        if prepared:
            prepared_by_timeframe[timeframe] = (config, prepared)

    results: list[dict[str, Any]] = []
    for spec in _candidate_specs():
        if spec.timeframe not in prepared_by_timeframe:
            continue
        config, prepared = prepared_by_timeframe[spec.timeframe]
        trades = _simulate_candidate(spec, prepared)
        metrics = _metrics(trades, config)
        walk_forward = _walk_forward_metrics(trades, config)
        candidate = {
            "candidateId": spec.candidate_id,
            "displayName": spec.display_name,
            "spec": spec.to_dict(),
            "metrics": metrics,
            "walkForward": walk_forward,
            "byPair": _group_metrics(trades, "pair", config)[:80],
            "byRegime": _group_metrics(trades, "btcPrimaryRegime", config),
            "exitReasonBreakdown": _group_metrics(trades, "exitReason", config),
            "tradeSample": sorted(trades, key=lambda item: item["exitTimestamp"])[:40],
        }
        approval = _approval(candidate)
        candidate["approval"] = approval
        candidate["score"] = _score(metrics, approval)
        results.append(candidate)

    ranked = sorted(
        results,
        key=lambda item: (
            bool(item["approval"]["passed"]),
            item["score"],
            item["metrics"].get("tradeCount", 0),
        ),
        reverse=True,
    )
    approved = [candidate for candidate in ranked if candidate["approval"]["passed"]][:max_approved]
    watchlist = [candidate for candidate in ranked if not candidate["approval"]["passed"]][:20]
    return {
        "status": "completed",
        "factoryId": "v13_7_20_five_strategy_candidate_factory",
        "objective": "Search deterministic 2R low-frequency strategy candidates and approve up to five research-usable strategies.",
        "timerange": timerange,
        "dataPath": data_path.as_posix(),
        "availableTimeframes": available_timeframes,
        "candidateCount": len(results),
        "approvedCount": len(approved),
        "targetApprovedCount": max_approved,
        "approvedCandidates": approved,
        "topWatchlistCandidates": watchlist,
        "allCandidateSummaries": [
            {
                "candidateId": item["candidateId"],
                "displayName": item["displayName"],
                "family": item["spec"]["family"],
                "timeframe": item["spec"]["timeframe"],
                "score": item["score"],
                "approved": item["approval"]["passed"],
                "tradeCount": item["metrics"]["tradeCount"],
                "winRatePct": item["metrics"]["winRatePct"],
                "profitFactor": item["metrics"]["profitFactor"],
                "totalReturnPct": item["metrics"]["totalReturnPct"],
                "maxDrawdownPct": item["metrics"]["maxDrawdownPct"],
                "failedChecks": [
                    key for key, value in item["approval"]["checks"].items() if not value
                ],
            }
            for item in ranked
        ],
        "warnings": warnings,
        "safetyBoundary": {
            "realTradingEnabled": False,
            "exchangeDryRunApproved": False,
            "liveTradingApproved": False,
            "tradeApiEnabled": False,
            "withdrawApiEnabled": False,
            "apiKeyStorage": False,
            "realAccountReads": False,
            "realPositionReads": False,
            "orderCreation": False,
            "autoTrading": False,
        },
    }
