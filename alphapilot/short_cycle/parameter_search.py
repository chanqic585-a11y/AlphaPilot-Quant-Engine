"""Short-cycle parameter search with fixed 2R exits.

The search is research-only. It reads local public Freqtrade OHLCV feather files
and simulates deterministic 2R exits. It does not use API keys, exchange private
endpoints, real accounts, real positions, orders, dry-run, or live trading.
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

from alphapilot.factors.ohlcv_loader import _read_ohlcv_file, discover_ohlcv_files


VERSION = "V13.7.40"
SOURCE = "alphapilot_short_cycle_parameter_search_v13_7_40"
DEFAULT_TIMEFRAMES = ("15m", "30m", "1h")
DEFAULT_TARGET_R = 2.0
DEFAULT_FEE_RATE = 0.0005
DEFAULT_SLIPPAGE_RATE = 0.0005
DEFAULT_TIMERANGE = "20260101-"


@dataclass(frozen=True)
class SearchConfig:
    dataPath: Path = Path("user_data/data/okx/futures")
    timerange: str = DEFAULT_TIMERANGE
    timeframes: tuple[str, ...] = DEFAULT_TIMEFRAMES
    targetR: float = DEFAULT_TARGET_R
    feeRate: float = DEFAULT_FEE_RATE
    slippageRate: float = DEFAULT_SLIPPAGE_RATE
    maxSelected: int = 5
    maxPairsPerTimeframe: int | None = None


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _parse_timerange(timerange: str) -> tuple[pd.Timestamp | None, pd.Timestamp | None]:
    start_raw, _, end_raw = timerange.partition("-")
    start = pd.Timestamp(datetime.strptime(start_raw, "%Y%m%d"), tz="UTC") if start_raw else None
    end = pd.Timestamp(datetime.strptime(end_raw, "%Y%m%d"), tz="UTC") if end_raw else None
    return start, end


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def _round(value: Any, digits: int = 4) -> float | None:
    number = _safe_float(value)
    if number is None:
        return None
    return round(number, digits)


def _normalise_ohlcv(raw: pd.DataFrame, pair: str, timerange: str) -> pd.DataFrame:
    frame = raw.loc[:, ["date", "open", "high", "low", "close", "volume"]].copy()
    frame["date"] = pd.to_datetime(frame["date"], utc=True, errors="coerce")
    for column in ("open", "high", "low", "close", "volume"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.dropna(subset=["date", "open", "high", "low", "close", "volume"])
    frame = frame.sort_values("date").drop_duplicates(subset=["date"], keep="last")
    start, end = _parse_timerange(timerange)
    if start is not None:
        frame = frame[frame["date"] >= start]
    if end is not None:
        frame = frame[frame["date"] < end]
    frame["pair"] = pair
    return frame.reset_index(drop=True)


def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _atr(frame: pd.DataFrame, period: int = 14) -> pd.Series:
    prev_close = frame["close"].shift(1)
    true_range = pd.concat(
        [
            frame["high"] - frame["low"],
            (frame["high"] - prev_close).abs(),
            (frame["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return true_range.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()


def add_indicators(frame: pd.DataFrame) -> pd.DataFrame:
    output = frame.copy()
    output["ema20"] = output["close"].ewm(span=20, adjust=False).mean()
    output["ema50"] = output["close"].ewm(span=50, adjust=False).mean()
    output["ema200"] = output["close"].ewm(span=200, adjust=False).mean()
    output["rsi14"] = _rsi(output["close"], 14)
    ema12 = output["close"].ewm(span=12, adjust=False).mean()
    ema26 = output["close"].ewm(span=26, adjust=False).mean()
    output["macd"] = ema12 - ema26
    output["macd_signal"] = output["macd"].ewm(span=9, adjust=False).mean()
    output["macd_hist"] = output["macd"] - output["macd_signal"]
    output["atr14"] = _atr(output, 14)
    output["volume_mean20"] = output["volume"].rolling(20, min_periods=20).mean()
    output["volume_ratio"] = output["volume"] / output["volume_mean20"].replace(0, np.nan)
    middle = output["close"].rolling(20, min_periods=20).mean()
    std = output["close"].rolling(20, min_periods=20).std()
    output["bb_middle"] = middle
    output["bb_upper"] = middle + std * 2
    output["bb_lower"] = middle - std * 2
    output["bb_width"] = (output["bb_upper"] - output["bb_lower"]) / output["bb_middle"].replace(0, np.nan)
    output["candle_body_pct"] = (output["close"] - output["open"]).abs() / output["open"].replace(0, np.nan)
    output["range_pct"] = (output["high"] - output["low"]) / output["open"].replace(0, np.nan)
    return output


def merge_btc_context(frame: pd.DataFrame, btc: pd.DataFrame | None) -> pd.DataFrame:
    output = frame.copy()
    if btc is None or btc.empty:
        output["btc_ret_3"] = np.nan
        output["btc_long_block"] = True
        output["btc_short_block"] = True
        return output
    context = btc[["date", "close"]].copy()
    context["btc_ret_3"] = context["close"] / context["close"].shift(3) - 1
    output = output.merge(context[["date", "btc_ret_3"]], on="date", how="left")
    output["btc_long_block"] = output["btc_ret_3"].isna() | (output["btc_ret_3"] <= -0.012)
    output["btc_short_block"] = output["btc_ret_3"].isna() | (output["btc_ret_3"] >= 0.012)
    return output


_merge_btc_context = merge_btc_context


def _base_ready(frame: pd.DataFrame) -> pd.Series:
    return frame[["ema20", "ema50", "ema200", "rsi14", "atr14", "volume_ratio"]].notna().all(axis=1)


def build_signal(frame: pd.DataFrame, family: str, params: dict[str, Any]) -> tuple[pd.Series, str]:
    ready = _base_ready(frame)
    atr_pct = frame["atr14"] / frame["close"].replace(0, np.nan)
    if family == "liquidity_sweep_reclaim_long":
        lookback = params["lookback"]
        prior_floor = frame["low"].rolling(lookback, min_periods=lookback).min().shift(2)
        prior_sweep = frame["low"].shift(1) <= (
            prior_floor * (1 - params["sweep_buffer"])
        )
        signal = (
            ready
            & ~frame["btc_long_block"]
            & prior_sweep
            & (frame["close"] >= prior_floor * (1 + params["reclaim_buffer"]))
            & (frame["close"] > frame["open"])
            & (frame["close"] > frame["high"].shift(1))
            & (frame["close"] >= frame["ema200"] * params["trend_floor"])
            & (frame["rsi14"].shift(1) <= params["rsi_oversold"])
            & (frame["rsi14"] >= params["rsi_recovery_min"])
            & (frame["rsi14"] > frame["rsi14"].shift(1))
            & (frame["volume_ratio"] >= params["volume_min"])
            & atr_pct.between(params["atr_pct_min"], params["atr_pct_max"])
        )
        return signal.fillna(False), "long"

    if family == "breakout_retest_continuation_long":
        lookback = params["lookback"]
        prior_ceiling = frame["high"].rolling(lookback, min_periods=lookback).max().shift(2)
        prior_breakout = (
            (frame["close"].shift(1) > prior_ceiling * (1 + params["breakout_buffer"]))
            & (frame["volume_ratio"].shift(1) >= params["breakout_volume_min"])
        )
        signal = (
            ready
            & ~frame["btc_long_block"]
            & prior_breakout
            & (frame["low"] <= prior_ceiling * (1 + params["retest_tolerance"]))
            & (frame["close"] >= prior_ceiling * (1 + params["reclaim_buffer"]))
            & (frame["close"] > frame["open"])
            & (frame["ema20"] >= frame["ema50"] * params["trend_tolerance"])
            & (frame["ema50"] >= frame["ema200"] * params["trend_tolerance"])
            & frame["rsi14"].between(params["rsi_min"], params["rsi_max"])
            & (frame["volume_ratio"] >= params["confirmation_volume_min"])
            & (
                frame["volume_ratio"]
                <= frame["volume_ratio"].shift(1) * params["retest_volume_ratio_max"]
            )
            & atr_pct.between(params["atr_pct_min"], params["atr_pct_max"])
        )
        return signal.fillna(False), "long"

    if family == "failed_breakout_reversal_short":
        lookback = params["lookback"]
        prior_ceiling = frame["high"].rolling(lookback, min_periods=lookback).max().shift(2)
        prior_sweep = frame["high"].shift(1) >= (
            prior_ceiling * (1 + params["sweep_buffer"])
        )
        signal = (
            ready
            & ~frame["btc_short_block"]
            & prior_sweep
            & (frame["close"] <= prior_ceiling * (1 - params["rejection_buffer"]))
            & (frame["close"] < frame["open"])
            & (frame["low"] < frame["low"].shift(1))
            & (frame["close"] <= frame["ema200"] * params["trend_ceiling"])
            & (frame["rsi14"].shift(1) >= params["rsi_high"])
            & (frame["rsi14"] < frame["rsi14"].shift(1))
            & (frame["volume_ratio"] >= params["volume_min"])
            & atr_pct.between(params["atr_pct_min"], params["atr_pct_max"])
        )
        return signal.fillna(False), "short"

    if family == "trend_pullback_confirmation_long":
        pullback = frame["low"] <= frame["ema20"] * (1 + params["pullback_tolerance"])
        recent_pullback = (
            pullback.shift(1)
            .rolling(params["pullback_lookback"], min_periods=params["pullback_lookback"])
            .max()
            .fillna(0)
            .astype(bool)
        )
        signal = (
            ready
            & ~frame["btc_long_block"]
            & recent_pullback
            & (frame["ema20"] > frame["ema20"].shift(params["ema_slope_lookback"]))
            & (frame["ema20"] >= frame["ema50"] * params["trend_tolerance"])
            & (frame["ema50"] >= frame["ema200"] * params["trend_tolerance"])
            & (frame["close"] > frame["ema20"] * (1 + params["reclaim_buffer"]))
            & (frame["close"] > frame["open"])
            & (frame["close"] > frame["high"].shift(1))
            & frame["rsi14"].between(params["rsi_min"], params["rsi_max"])
            & (frame["volume_ratio"] >= params["volume_min"])
            & atr_pct.between(params["atr_pct_min"], params["atr_pct_max"])
        )
        return signal.fillna(False), "long"

    if family == "compression_release_long":
        lookback = params["lookback"]
        prior_high = frame["high"].rolling(lookback, min_periods=lookback).max().shift(1)
        squeeze_ref = frame["bb_width"].rolling(
            params["squeeze_window"], min_periods=params["squeeze_window"]
        ).median()
        prior_squeeze = frame["bb_width"].shift(1) < (
            squeeze_ref.shift(1) * params["squeeze_ratio"]
        )
        signal = (
            ready
            & ~frame["btc_long_block"]
            & prior_squeeze
            & (frame["bb_width"] >= frame["bb_width"].shift(1) * params["expansion_min"])
            & (frame["ema20"] >= frame["ema50"] * params["trend_tolerance"])
            & (frame["ema50"] >= frame["ema200"] * params["trend_tolerance"])
            & (frame["close"] > prior_high)
            & (frame["close"] > frame["open"])
            & (frame["rsi14"] <= params["rsi_max"])
            & (frame["volume_ratio"] >= params["volume_min"])
            & (atr_pct <= params["atr_pct_max"])
        )
        return signal.fillna(False), "long"

    if family == "failed_reclaim_short":
        reclaim_attempt = frame["high"] >= frame["ema20"] * (
            1 - params["reclaim_tolerance"]
        )
        recent_attempt = (
            reclaim_attempt.shift(1)
            .rolling(params["reclaim_lookback"], min_periods=params["reclaim_lookback"])
            .max()
            .fillna(0)
            .astype(bool)
        )
        signal = (
            ready
            & ~frame["btc_short_block"]
            & recent_attempt
            & (frame["ema20"] < frame["ema20"].shift(params["ema_slope_lookback"]))
            & (frame["ema20"] <= frame["ema50"] * params["trend_tolerance"])
            & (frame["ema50"] <= frame["ema200"] * params["trend_tolerance"])
            & (frame["close"] < frame["ema20"] * (1 - params["rejection_buffer"]))
            & (frame["close"] < frame["open"])
            & (frame["close"] < frame["low"].shift(1))
            & (frame["macd_hist"] < 0)
            & frame["rsi14"].between(params["rsi_min"], params["rsi_max"])
            & (frame["volume_ratio"] >= params["volume_min"])
            & atr_pct.between(params["atr_pct_min"], params["atr_pct_max"])
        )
        return signal.fillna(False), "short"

    if family == "volume_rebound_long":
        signal = (
            ready
            & ~frame["btc_long_block"]
            & (frame["close"] > frame["ema20"])
            & (frame["close"] > frame["open"])
            & (frame["ema50"] >= frame["ema200"] * params["trend_tolerance"])
            & (frame["low"] <= frame["ema20"] * (1 + params["ema_touch_pct"]))
            & frame["rsi14"].between(params["rsi_min"], params["rsi_max"])
            & (frame["volume_ratio"] >= params["volume_min"])
            & (frame["macd_hist"] > frame["macd_hist"].shift(1))
        )
        return signal.fillna(False), "long"

    if family == "breakout_volume_long":
        lookback = params["lookback"]
        prior_high = frame["high"].rolling(lookback, min_periods=lookback).max().shift(1)
        signal = (
            ready
            & ~frame["btc_long_block"]
            & (frame["close"] > prior_high * (1 + params["breakout_buffer"]))
            & (frame["close"] > frame["ema200"])
            & (frame["rsi14"] <= params["rsi_max"])
            & (frame["volume_ratio"] >= params["volume_min"])
        )
        return signal.fillna(False), "long"

    if family == "momentum_continuation_long":
        signal = (
            ready
            & ~frame["btc_long_block"]
            & (frame["ema20"] >= frame["ema50"] * params["trend_tolerance"])
            & (frame["close"] > frame["ema20"])
            & (frame["macd_hist"] > 0)
            & (frame["macd_hist"] >= frame["macd_hist"].shift(1) * params["macd_tolerance"])
            & frame["rsi14"].between(params["rsi_min"], params["rsi_max"])
            & (frame["volume_ratio"] >= params["volume_min"])
        )
        return signal.fillna(False), "long"

    if family == "squeeze_breakout_long":
        lookback = params["lookback"]
        prior_high = frame["high"].rolling(lookback, min_periods=lookback).max().shift(1)
        squeeze_ref = frame["bb_width"].rolling(params["squeeze_window"], min_periods=params["squeeze_window"]).median()
        signal = (
            ready
            & ~frame["btc_long_block"]
            & (frame["bb_width"] < squeeze_ref * params["squeeze_ratio"])
            & (frame["close"] > prior_high)
            & (frame["close"] > frame["ema50"])
            & (frame["volume_ratio"] >= params["volume_min"])
        )
        return signal.fillna(False), "long"

    if family == "ema_reclaim_long":
        signal = (
            ready
            & ~frame["btc_long_block"]
            & (frame["close"] > frame["ema50"] * params["trend_tolerance"])
            & (frame["close"].shift(1) <= frame["ema20"].shift(1) * (1 + params["reclaim_buffer"]))
            & (frame["close"] > frame["ema20"])
            & (frame["close"] > frame["open"])
            & frame["rsi14"].between(params["rsi_min"], params["rsi_max"])
            & (frame["volume_ratio"] >= params["volume_min"])
        )
        return signal.fillna(False), "long"

    if family == "trend_pullback_long":
        signal = (
            ready
            & ~frame["btc_long_block"]
            & (frame["close"] > frame["ema200"] * params["trend_tolerance"])
            & (frame["ema20"] >= frame["ema50"])
            & (frame["low"] <= frame["ema20"] * (1 + params["pullback_pct"]))
            & (frame["close"] > frame["ema20"])
            & (frame["close"] > frame["close"].shift(1))
            & frame["rsi14"].between(params["rsi_min"], params["rsi_max"])
        )
        return signal.fillna(False), "long"

    if family == "mean_reversion_reclaim_long":
        prev_was_stretched = (frame["close"].shift(1) < frame["bb_lower"].shift(1)) | (
            frame["rsi14"].shift(1) <= params["rsi_low"]
        )
        signal = (
            ready
            & ~frame["btc_long_block"]
            & prev_was_stretched
            & (frame["close"] > frame["bb_lower"])
            & (frame["close"] > frame["open"])
            & (frame["volume_ratio"] >= params["volume_min"])
            & (frame["range_pct"] <= params["max_range_pct"])
        )
        return signal.fillna(False), "long"

    if family == "short_rejection":
        signal = (
            ready
            & ~frame["btc_short_block"]
            & (frame["close"] < frame["ema200"] * params["trend_tolerance"])
            & (frame["ema20"] <= frame["ema50"])
            & (frame["high"] >= frame["bb_upper"] * (1 - params["upper_buffer"]))
            & (frame["close"] < frame["open"])
            & (frame["rsi14"] >= params["rsi_high"])
            & (frame["volume_ratio"] >= params["volume_min"])
        )
        return signal.fillna(False), "short"

    if family == "short_breakdown_momentum":
        lookback = params["lookback"]
        prior_low = frame["low"].rolling(lookback, min_periods=lookback).min().shift(1)
        signal = (
            ready
            & ~frame["btc_short_block"]
            & (frame["ema20"] <= frame["ema50"] * params["trend_tolerance"])
            & (frame["close"] < prior_low * (1 - params["breakdown_buffer"]))
            & (frame["macd_hist"] < 0)
            & (frame["rsi14"] <= params["rsi_max"])
            & (frame["volume_ratio"] >= params["volume_min"])
        )
        return signal.fillna(False), "short"

    raise ValueError(f"Unknown signal family: {family}")


def _iter_param_grid() -> Iterable[dict[str, Any]]:
    grids: list[tuple[str, str, dict[str, list[Any]]]] = [
        (
            "15m",
            "momentum_continuation_long",
            {
                "trend_tolerance": [0.995, 1.0],
                "macd_tolerance": [0.8, 1.0],
                "rsi_min": [44, 50],
                "rsi_max": [72, 82],
                "volume_min": [0.8, 1.0, 1.2],
                "stop_atr": [1.0, 1.4],
                "max_hold": [12, 20],
            },
        ),
        (
            "15m",
            "ema_reclaim_long",
            {
                "trend_tolerance": [0.985, 0.995, 1.0],
                "reclaim_buffer": [0.002, 0.006],
                "rsi_min": [38, 44],
                "rsi_max": [68, 78],
                "volume_min": [0.7, 1.0],
                "stop_atr": [1.0, 1.4],
                "max_hold": [12, 20],
            },
        ),
        (
            "15m",
            "volume_rebound_long",
            {
                "volume_min": [1.5, 1.9, 2.3],
                "rsi_min": [34, 40],
                "rsi_max": [62, 70],
                "ema_touch_pct": [0.003, 0.008],
                "trend_tolerance": [0.995, 1.0],
                "stop_atr": [1.0, 1.3],
                "max_hold": [16, 24],
            },
        ),
        (
            "15m",
            "breakout_volume_long",
            {
                "lookback": [32, 64, 96],
                "breakout_buffer": [0.0, 0.001],
                "volume_min": [1.4, 1.8],
                "rsi_max": [76, 84],
                "stop_atr": [1.2, 1.6],
                "max_hold": [16, 24],
            },
        ),
        (
            "30m",
            "momentum_continuation_long",
            {
                "trend_tolerance": [0.995, 1.0],
                "macd_tolerance": [0.8, 1.0],
                "rsi_min": [44, 50],
                "rsi_max": [72, 82],
                "volume_min": [0.8, 1.0, 1.2],
                "stop_atr": [1.0, 1.4],
                "max_hold": [10, 16],
            },
        ),
        (
            "30m",
            "squeeze_breakout_long",
            {
                "lookback": [20, 40],
                "squeeze_window": [80, 120],
                "squeeze_ratio": [0.75, 0.9],
                "volume_min": [1.1, 1.4],
                "stop_atr": [1.2, 1.6],
                "max_hold": [12, 20],
            },
        ),
        (
            "30m",
            "short_breakdown_momentum",
            {
                "lookback": [16, 32, 48],
                "trend_tolerance": [1.0, 1.01],
                "breakdown_buffer": [0.0, 0.001],
                "rsi_max": [42, 50, 58],
                "volume_min": [0.8, 1.1],
                "stop_atr": [1.0, 1.4],
                "max_hold": [10, 16],
            },
        ),
        (
            "30m",
            "mean_reversion_reclaim_long",
            {
                "rsi_low": [24, 30, 35],
                "volume_min": [0.8, 1.0],
                "max_range_pct": [0.025, 0.04],
                "stop_atr": [1.0, 1.4],
                "max_hold": [12, 20],
            },
        ),
        (
            "1h",
            "momentum_continuation_long",
            {
                "trend_tolerance": [0.995, 1.0],
                "macd_tolerance": [0.8, 1.0],
                "rsi_min": [44, 50],
                "rsi_max": [72, 82],
                "volume_min": [0.8, 1.0, 1.2],
                "stop_atr": [1.0, 1.4, 1.8],
                "max_hold": [8, 12],
            },
        ),
        (
            "1h",
            "ema_reclaim_long",
            {
                "trend_tolerance": [0.985, 0.995, 1.0],
                "reclaim_buffer": [0.002, 0.006],
                "rsi_min": [38, 44],
                "rsi_max": [68, 78],
                "volume_min": [0.7, 1.0],
                "stop_atr": [1.0, 1.4, 1.8],
                "max_hold": [8, 12],
            },
        ),
        (
            "1h",
            "trend_pullback_long",
            {
                "pullback_pct": [0.006, 0.012, 0.02],
                "trend_tolerance": [0.995, 1.0],
                "rsi_min": [36, 42],
                "rsi_max": [62, 70],
                "stop_atr": [1.2, 1.6, 2.0],
                "max_hold": [8, 12],
            },
        ),
        (
            "1h",
            "short_rejection",
            {
                "upper_buffer": [0.0, 0.003],
                "trend_tolerance": [1.0, 1.005],
                "rsi_high": [62, 70],
                "volume_min": [0.9, 1.2],
                "stop_atr": [1.2, 1.6],
                "max_hold": [8, 12],
            },
        ),
        (
            "1h",
            "short_rejection",
            {
                "upper_buffer": [0.003, 0.006],
                "trend_tolerance": [1.0, 1.01],
                "rsi_high": [58, 60],
                "volume_min": [1.0, 1.2],
                "stop_atr": [1.0, 1.2, 1.4],
                "max_hold": [8, 12, 16],
            },
        ),
    ]
    for timeframe, family, grid in grids:
        keys = list(grid)
        for values in itertools.product(*(grid[key] for key in keys)):
            params = dict(zip(keys, values, strict=True))
            yield {"timeframe": timeframe, "family": family, "params": params}


def simulate_trades(
    frame: pd.DataFrame,
    signal: pd.Series,
    direction: str,
    *,
    stop_atr: float,
    max_hold: int,
    target_r: float,
    fee_rate: float,
    slippage_rate: float,
) -> list[dict[str, Any]]:
    trades: list[dict[str, Any]] = []
    if frame.empty:
        return trades
    signal_values = signal.to_numpy(dtype=bool)
    opens = frame["open"].to_numpy(dtype=float)
    highs = frame["high"].to_numpy(dtype=float)
    lows = frame["low"].to_numpy(dtype=float)
    closes = frame["close"].to_numpy(dtype=float)
    atr = frame["atr14"].to_numpy(dtype=float)
    dates = frame["date"].to_numpy()
    pair = str(frame["pair"].iloc[0])

    last_exit_idx = -1
    for signal_idx in np.flatnonzero(signal_values):
        entry_idx = int(signal_idx) + 1
        if entry_idx >= len(frame) or entry_idx <= last_exit_idx:
            continue
        risk_distance = atr[entry_idx] * stop_atr
        if not np.isfinite(risk_distance) or risk_distance <= 0:
            continue

        raw_entry = opens[entry_idx]
        if direction == "long":
            entry_price = raw_entry * (1 + slippage_rate)
            stop_price = entry_price - risk_distance
            target_price = entry_price + risk_distance * target_r
        else:
            entry_price = raw_entry * (1 - slippage_rate)
            stop_price = entry_price + risk_distance
            target_price = entry_price - risk_distance * target_r

        exit_idx = min(entry_idx + max_hold, len(frame) - 1)
        exit_reason = "time_exit"
        exit_price = closes[exit_idx]
        gross_r = 0.0
        for idx in range(entry_idx, exit_idx + 1):
            if direction == "long":
                stop_hit = lows[idx] <= stop_price
                target_hit = highs[idx] >= target_price
                if stop_hit:
                    exit_idx = idx
                    exit_reason = "stop"
                    exit_price = stop_price * (1 - slippage_rate)
                    gross_r = (exit_price - entry_price) / risk_distance
                    break
                if target_hit:
                    exit_idx = idx
                    exit_reason = "target"
                    exit_price = target_price * (1 - slippage_rate)
                    gross_r = (exit_price - entry_price) / risk_distance
                    break
            else:
                stop_hit = highs[idx] >= stop_price
                target_hit = lows[idx] <= target_price
                if stop_hit:
                    exit_idx = idx
                    exit_reason = "stop"
                    exit_price = stop_price * (1 + slippage_rate)
                    gross_r = (entry_price - exit_price) / risk_distance
                    break
                if target_hit:
                    exit_idx = idx
                    exit_reason = "target"
                    exit_price = target_price * (1 + slippage_rate)
                    gross_r = (entry_price - exit_price) / risk_distance
                    break
        else:
            if direction == "long":
                exit_price = closes[exit_idx] * (1 - slippage_rate)
                gross_r = (exit_price - entry_price) / risk_distance
            else:
                exit_price = closes[exit_idx] * (1 + slippage_rate)
                gross_r = (entry_price - exit_price) / risk_distance

        fee_r = ((entry_price * fee_rate) + (exit_price * fee_rate)) / risk_distance
        net_r = gross_r - fee_r
        trades.append(
            {
                "pair": pair,
                "entryDate": pd.Timestamp(dates[entry_idx]).isoformat(),
                "exitDate": pd.Timestamp(dates[exit_idx]).isoformat(),
                "direction": direction,
                "entryPrice": _round(entry_price, 8),
                "exitPrice": _round(exit_price, 8),
                "riskDistance": _round(risk_distance, 8),
                "grossR": _round(gross_r, 6),
                "feeR": _round(fee_r, 6),
                "netR": _round(net_r, 6),
                "exitReason": exit_reason,
                "holdCandles": exit_idx - entry_idx,
            }
        )
        last_exit_idx = exit_idx
    return trades


def compute_metrics(trades: list[dict[str, Any]]) -> dict[str, Any]:
    if not trades:
        return {
            "tradeCount": 0,
            "winRatePct": None,
            "profitFactor": None,
            "expectancyR": None,
            "totalR": 0.0,
            "maxDrawdownR": 0.0,
            "maxDrawdownPctAt1PctRisk": 0.0,
            "pairCount": 0,
            "targetHitRatePct": None,
            "stopHitRatePct": None,
        }
    values = np.array([float(item["netR"]) for item in trades], dtype=float)
    wins = values[values > 0]
    losses = values[values < 0]
    cumulative = np.cumsum(values)
    peak = np.maximum.accumulate(np.insert(cumulative, 0, 0.0))[1:]
    drawdown = peak - cumulative
    profit_factor = float(wins.sum() / abs(losses.sum())) if losses.size else None
    pair_count = len({item["pair"] for item in trades})
    target_hits = sum(1 for item in trades if item["exitReason"] == "target")
    stop_hits = sum(1 for item in trades if item["exitReason"] == "stop")
    return {
        "tradeCount": len(trades),
        "winCount": int((values > 0).sum()),
        "lossCount": int((values < 0).sum()),
        "winRatePct": _round((values > 0).mean() * 100, 4),
        "profitFactor": _round(profit_factor, 4),
        "expectancyR": _round(values.mean(), 6),
        "totalR": _round(values.sum(), 4),
        "maxDrawdownR": _round(drawdown.max() if drawdown.size else 0.0, 4),
        "maxDrawdownPctAt1PctRisk": _round((drawdown.max() if drawdown.size else 0.0), 4),
        "pairCount": pair_count,
        "targetHitRatePct": _round(target_hits / len(trades) * 100, 4),
        "stopHitRatePct": _round(stop_hits / len(trades) * 100, 4),
    }


def _split_trades(trades: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    if not trades:
        return {"train": [], "validation": [], "test": []}
    dates = pd.to_datetime([item["entryDate"] for item in trades], utc=True)
    start = dates.min()
    end = dates.max()
    span = end - start
    train_end = start + span * 0.50
    validation_end = start + span * 0.75
    splits = {"train": [], "validation": [], "test": []}
    for trade, date in zip(trades, dates, strict=True):
        if date <= train_end:
            splits["train"].append(trade)
        elif date <= validation_end:
            splits["validation"].append(trade)
        else:
            splits["test"].append(trade)
    return splits


def _gate_candidate(metrics: dict[str, Any], split_metrics: dict[str, dict[str, Any]]) -> tuple[bool, list[str]]:
    failed: list[str] = []
    test = split_metrics["test"]
    validation = split_metrics["validation"]
    if metrics["tradeCount"] < 100:
        failed.append("total_trade_count_lt_100")
    if test["tradeCount"] < 20:
        failed.append("test_trade_count_lt_20")
    if metrics["pairCount"] < 8:
        failed.append("pair_count_lt_8")
    if (metrics.get("profitFactor") or 0) < 1.1:
        failed.append("total_profit_factor_lt_1_10")
    if (test.get("profitFactor") or 0) < 1.05:
        failed.append("test_profit_factor_lt_1_05")
    if (test.get("expectancyR") or 0) <= 0:
        failed.append("test_expectancy_not_positive")
    if (validation.get("expectancyR") or 0) < -0.05:
        failed.append("validation_expectancy_too_negative")
    if (metrics.get("maxDrawdownPctAt1PctRisk") or 0) > 35:
        failed.append("drawdown_gt_35r")
    return not failed, failed


def _observation_gate(metrics: dict[str, Any], split_metrics: dict[str, dict[str, Any]]) -> tuple[bool, list[str]]:
    """Looser gate for local sandbox observation, not for dry-run or live trading."""

    failed: list[str] = []
    test = split_metrics["test"]
    validation = split_metrics["validation"]
    if metrics["tradeCount"] < 60:
        failed.append("observation_total_trade_count_lt_60")
    if test["tradeCount"] < 20:
        failed.append("observation_test_trade_count_lt_20")
    if metrics["pairCount"] < 8:
        failed.append("observation_pair_count_lt_8")
    if (metrics.get("profitFactor") or 0) < 1.0:
        failed.append("observation_total_profit_factor_lt_1_00")
    if (test.get("profitFactor") or 0) < 1.0:
        failed.append("observation_test_profit_factor_lt_1_00")
    if (test.get("expectancyR") or 0) <= 0:
        failed.append("observation_test_expectancy_not_positive")
    if (validation.get("expectancyR") or 0) < -0.25:
        failed.append("observation_validation_expectancy_too_negative")
    if (metrics.get("maxDrawdownPctAt1PctRisk") or 0) > 45:
        failed.append("observation_drawdown_gt_45r")
    return not failed, failed


def _score(metrics: dict[str, Any], split_metrics: dict[str, dict[str, Any]]) -> float:
    test = split_metrics["test"]
    validation = split_metrics["validation"]
    total_pf = metrics.get("profitFactor") or 0
    test_pf = test.get("profitFactor") or 0
    sample_penalty = max(0, 100 - metrics["tradeCount"]) * 2.0 + max(0, 20 - test["tradeCount"]) * 4.0
    return float(
        (test.get("expectancyR") or 0) * 120
        + (validation.get("expectancyR") or 0) * 40
        + min(test_pf, 4) * 12
        + min(total_pf, 4) * 6
        + min(metrics["pairCount"], 30) * 0.8
        + math.log1p(metrics["tradeCount"]) * 2
        - (metrics.get("maxDrawdownPctAt1PctRisk") or 0) * 0.55
        - sample_penalty
    )


def _train_asset_filtered_candidates(
    *,
    candidate_id: str,
    display_name: str,
    timeframe: str,
    family: str,
    direction: str,
    params: dict[str, Any],
    trades_by_pair: dict[str, list[dict[str, Any]]],
    target_r: float,
) -> list[dict[str, Any]]:
    """Build pre-test asset-filtered variants using train-segment pair evidence only."""

    all_trades = sorted(
        [trade for trades in trades_by_pair.values() for trade in trades],
        key=lambda item: item["entryDate"],
    )
    train_trades = _split_trades(all_trades)["train"]
    if not train_trades:
        return []
    train_end = max(trade["entryDate"] for trade in train_trades)

    pair_scores: list[tuple[str, float, float, int]] = []
    for pair, pair_trades in trades_by_pair.items():
        pair_train_trades = [trade for trade in pair_trades if trade["entryDate"] <= train_end]
        pair_metrics = compute_metrics(pair_train_trades)
        if (
            pair_metrics["tradeCount"] >= 3
            and (pair_metrics.get("profitFactor") or 0) >= 1.05
            and (pair_metrics.get("expectancyR") or 0) > 0
        ):
            pair_scores.append(
                (
                    pair,
                    pair_metrics.get("expectancyR") or 0,
                    pair_metrics.get("profitFactor") or 0,
                    pair_metrics["tradeCount"],
                )
            )
    pair_scores.sort(key=lambda item: (item[1], item[2], item[3]), reverse=True)

    variants: list[dict[str, Any]] = []
    seen_pair_sets: set[tuple[str, ...]] = set()
    for top_n in (8, 10, 12):
        if len(pair_scores) < top_n:
            continue
        selected_pairs = tuple(sorted(pair for pair, *_ in pair_scores[:top_n]))
        if selected_pairs in seen_pair_sets:
            continue
        seen_pair_sets.add(selected_pairs)

        filtered_trades = sorted(
            [trade for pair in selected_pairs for trade in trades_by_pair.get(pair, [])],
            key=lambda item: item["entryDate"],
        )
        metrics = compute_metrics(filtered_trades)
        splits = _split_trades(filtered_trades)
        split_metrics = {name: compute_metrics(rows) for name, rows in splits.items()}
        approved, failed = _gate_candidate(metrics, split_metrics)
        observation_passed, observation_failed = _observation_gate(metrics, split_metrics)
        if not approved and not observation_passed:
            continue
        score = _score(metrics, split_metrics)
        if approved:
            tier = "strict_approved_asset_filtered"
        else:
            tier = "observation_candidate_asset_filtered"
        variants.append(
            {
                "candidateId": f"{candidate_id}_asset_filter_top{top_n}",
                "displayName": f"{display_name} 资产筛选Top{top_n}",
                "timeframe": timeframe,
                "family": family,
                "direction": direction,
                "targetR": target_r,
                "params": params,
                "assetFilter": {
                    "enabled": True,
                    "selectionMethod": "train_segment_positive_pair_filter",
                    "selectedPairCount": len(selected_pairs),
                    "selectedPairs": list(selected_pairs),
                    "minTrainTradesPerPair": 3,
                    "minTrainProfitFactor": 1.05,
                    "requiresPositiveTrainExpectancy": True,
                    "note": "Pairs are selected from the train segment only; validation and test remain out of selection.",
                },
                "metrics": metrics,
                "splitMetrics": split_metrics,
                "approved": approved,
                "observationCandidate": observation_passed,
                "approvalTier": tier,
                "failedChecks": failed,
                "observationFailedChecks": observation_failed,
                "score": _round(score, 6),
                "sampleTrades": filtered_trades[:5],
                "pairBreakdown": _pair_breakdown(filtered_trades)[:12],
            }
        )
    return variants


def _display_name(family: str, timeframe: str, params: dict[str, Any]) -> str:
    family_name = {
        "volume_rebound_long": "放量回踩修复",
        "breakout_volume_long": "放量突破延续",
        "squeeze_breakout_long": "低波压缩突破",
        "trend_pullback_long": "趋势回踩确认",
        "mean_reversion_reclaim_long": "超卖回收修复",
        "short_rejection": "空头上影拒绝",
        "short_breakdown_momentum": "空头破位动量",
        "momentum_continuation_long": "动量延续",
        "ema_reclaim_long": "均线回收",
    }.get(family, family)
    return f"{timeframe} {family_name} ATR{params['stop_atr']}"


def run_short_cycle_parameter_search(config: SearchConfig) -> dict[str, Any]:
    frames: dict[tuple[str, str], pd.DataFrame] = {}
    warnings: list[str] = []
    data_coverage: dict[str, Any] = {}

    for timeframe in config.timeframes:
        discovered = discover_ohlcv_files(config.dataPath, timeframe)
        pairs = sorted(discovered)
        if config.maxPairsPerTimeframe:
            pairs = pairs[: config.maxPairsPerTimeframe]
        data_coverage[timeframe] = {"pairCount": len(pairs), "pairs": pairs}
        btc_frame: pd.DataFrame | None = None
        if "BTC/USDT:USDT" in discovered:
            btc_frame = add_indicators(_normalise_ohlcv(_read_ohlcv_file(discovered["BTC/USDT:USDT"]), "BTC/USDT:USDT", config.timerange))
        for pair in pairs:
            try:
                raw = _read_ohlcv_file(discovered[pair])
                frame = add_indicators(_normalise_ohlcv(raw, pair, config.timerange))
                frame = merge_btc_context(frame, btc_frame)
                if len(frame) < 260:
                    warnings.append(f"{timeframe}:{pair}: too few candles after timerange")
                    continue
                frames[(timeframe, pair)] = frame
            except Exception as exc:  # pragma: no cover - defensive report path
                warnings.append(f"{timeframe}:{pair}: {exc}")

    candidate_results: list[dict[str, Any]] = []
    for index, spec in enumerate(_iter_param_grid(), start=1):
        timeframe = spec["timeframe"]
        if timeframe not in config.timeframes:
            continue
        family = spec["family"]
        params = spec["params"]
        trades: list[dict[str, Any]] = []
        trades_by_pair: dict[str, list[dict[str, Any]]] = {}
        for (frame_timeframe, pair), frame in frames.items():
            if frame_timeframe != timeframe:
                continue
            signal, direction = build_signal(frame, family, params)
            pair_trades = simulate_trades(
                frame,
                signal,
                direction,
                stop_atr=float(params["stop_atr"]),
                max_hold=int(params["max_hold"]),
                target_r=config.targetR,
                fee_rate=config.feeRate,
                slippage_rate=config.slippageRate,
            )
            trades_by_pair[pair] = pair_trades
            trades.extend(pair_trades)

        trades.sort(key=lambda item: item["entryDate"])
        metrics = compute_metrics(trades)
        splits = _split_trades(trades)
        split_metrics = {name: compute_metrics(rows) for name, rows in splits.items()}
        approved, failed = _gate_candidate(metrics, split_metrics)
        observation_passed, observation_failed = _observation_gate(metrics, split_metrics)
        score = _score(metrics, split_metrics)
        if approved:
            tier = "strict_approved"
        elif observation_passed:
            tier = "observation_candidate"
        else:
            tier = "rejected"
        candidate_id = f"v13_7_40_{timeframe}_{family}_{index:03d}"
        direction = "short" if family in {"short_rejection", "short_breakdown_momentum"} else "long"
        display_name = _display_name(family, timeframe, params)
        base_candidate = {
            "candidateId": candidate_id,
            "displayName": display_name,
            "timeframe": timeframe,
            "family": family,
            "direction": direction,
            "targetR": config.targetR,
            "params": params,
            "assetFilter": {"enabled": False},
            "metrics": metrics,
            "splitMetrics": split_metrics,
            "approved": approved,
            "observationCandidate": observation_passed,
            "approvalTier": tier,
            "failedChecks": failed,
            "observationFailedChecks": observation_failed,
            "score": _round(score, 6),
            "sampleTrades": trades[:5],
            "pairBreakdown": _pair_breakdown(trades)[:12],
        }
        candidate_results.append(base_candidate)
        candidate_results.extend(
            _train_asset_filtered_candidates(
                candidate_id=candidate_id,
                display_name=display_name,
                timeframe=timeframe,
                family=family,
                direction=direction,
                params=params,
                trades_by_pair=trades_by_pair,
                target_r=config.targetR,
            )
        )

    ranked = sorted(candidate_results, key=lambda item: item["score"] or -9999, reverse=True)
    approved_ranked = [item for item in ranked if item["approved"]]
    observation_ranked = [item for item in ranked if item["observationCandidate"] and not item["approved"]]
    selected = approved_ranked[: config.maxSelected]
    if len(selected) < config.maxSelected:
        selected_ids = {item["candidateId"] for item in selected}
        selected.extend(
            [item for item in observation_ranked if item["candidateId"] not in selected_ids][
                : config.maxSelected - len(selected)
            ]
        )
    if len(selected) < config.maxSelected:
        selected_ids = {item["candidateId"] for item in selected}
        selected.extend(
            [item for item in ranked if item["candidateId"] not in selected_ids][: config.maxSelected - len(selected)]
        )

    return {
        "version": VERSION,
        "generatedAt": utc_now(),
        "source": SOURCE,
        "status": "completed",
        "objective": "Search short-cycle public-OHLCV research candidates with fixed 2R exits.",
        "config": {
            "dataPath": config.dataPath.as_posix(),
            "timerange": config.timerange,
            "timeframes": list(config.timeframes),
            "targetR": config.targetR,
            "feeRate": config.feeRate,
            "slippageRate": config.slippageRate,
            "maxSelected": config.maxSelected,
            "maxPairsPerTimeframe": config.maxPairsPerTimeframe,
        },
        "dataCoverage": data_coverage,
        "candidateCount": len(candidate_results),
        "approvedCount": len(approved_ranked),
        "observationCandidateCount": len(observation_ranked),
        "selectedCount": len(selected),
        "selectedCandidates": selected,
        "topCandidates": ranked[:25],
        "negativeSamples": [item for item in ranked if item["metrics"]["tradeCount"] >= 30 and not item["approved"]][-25:],
        "warnings": warnings[:200],
        "safetyBoundary": {
            "apiKeyStorage": False,
            "tradeApiEnabled": False,
            "withdrawApiEnabled": False,
            "realAccountReads": False,
            "realPositionReads": False,
            "orderCreation": False,
            "exchangeDryRun": False,
            "liveTrading": False,
            "autoTrading": False,
            "researchOnly": True,
        },
    }


def _pair_breakdown(trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_pair: dict[str, list[dict[str, Any]]] = {}
    for trade in trades:
        by_pair.setdefault(trade["pair"], []).append(trade)
    rows = []
    for pair, pair_trades in by_pair.items():
        metrics = compute_metrics(pair_trades)
        rows.append(
            {
                "pair": pair,
                "tradeCount": metrics["tradeCount"],
                "winRatePct": metrics["winRatePct"],
                "profitFactor": metrics["profitFactor"],
                "expectancyR": metrics["expectancyR"],
                "totalR": metrics["totalR"],
            }
        )
    return sorted(rows, key=lambda row: row["totalR"] or -9999, reverse=True)
