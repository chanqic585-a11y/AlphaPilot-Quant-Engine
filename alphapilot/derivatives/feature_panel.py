"""Build V13.5 derivative feature panels from local public data.

The loader reads local Freqtrade feather files only. It does not request
exchange data, use API keys, read accounts, create orders, or auto trade.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


DEFAULT_DATA_DIR = Path("user_data/data/okx/futures")


@dataclass(frozen=True)
class FeaturePanelResult:
    rows: pd.DataFrame
    loaded_pairs: list[str]
    missing_pairs: list[str]
    missing_optional_sources: dict[str, list[str]]


def normalize_pair(pair: str) -> str:
    return pair.replace("/", "_").replace(":", "_")


def _read_feather(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None
    frame = pd.read_feather(path)
    if "date" not in frame.columns:
        return None
    frame = frame.copy()
    frame["date"] = pd.to_datetime(frame["date"], utc=True).astype("datetime64[ns, UTC]")
    return frame.sort_values("date").reset_index(drop=True)


def _load_ohlcv(pair: str, timeframe: str, data_dir: Path) -> pd.DataFrame | None:
    return _read_feather(data_dir / f"{normalize_pair(pair)}-{timeframe}-futures.feather")


def _load_mark(pair: str, data_dir: Path) -> pd.DataFrame | None:
    return _read_feather(data_dir / f"{normalize_pair(pair)}-1h-mark.feather")


def _load_funding(pair: str, data_dir: Path) -> pd.DataFrame | None:
    return _read_feather(data_dir / f"{normalize_pair(pair)}-1h-funding_rate.feather")


def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period, min_periods=period).mean()
    loss = (-delta.clip(upper=0)).rolling(period, min_periods=period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _atr_pct(frame: pd.DataFrame, period: int = 14) -> pd.Series:
    previous_close = frame["close"].shift(1)
    true_range = pd.concat(
        [
            frame["high"] - frame["low"],
            (frame["high"] - previous_close).abs(),
            (frame["low"] - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    atr = true_range.rolling(period, min_periods=period).mean()
    return atr / frame["close"].replace(0, np.nan)


def _add_base_features(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    close = out["close"]
    out["return_1"] = close.pct_change(1)
    out["return_3"] = close.pct_change(3)
    out["return_6"] = close.pct_change(6)
    out["return_12"] = close.pct_change(12)
    out["ema20"] = close.ewm(span=20, adjust=False).mean()
    out["ema50"] = close.ewm(span=50, adjust=False).mean()
    out["ema200"] = close.ewm(span=200, adjust=False).mean()
    out["ema20_gap"] = (close / out["ema20"]) - 1
    out["ema200_gap"] = (close / out["ema200"]) - 1
    out["rsi14"] = _rsi(close)
    out["atr_pct"] = _atr_pct(out)
    out["range_pct"] = (out["high"] - out["low"]) / close.replace(0, np.nan)
    out["volatility_12"] = out["return_1"].rolling(12, min_periods=12).std()
    out["volume_mean_20"] = out["volume"].rolling(20, min_periods=20).mean()
    out["volume_ratio"] = out["volume"] / out["volume_mean_20"].replace(0, np.nan)
    rolling_mean = close.rolling(20, min_periods=20).mean()
    rolling_std = close.rolling(20, min_periods=20).std()
    out["bollinger_z"] = (close - rolling_mean) / rolling_std.replace(0, np.nan)
    out["support_distance_pct"] = (close / out["low"].rolling(24, min_periods=24).min()) - 1
    out["resistance_distance_pct"] = (out["high"].rolling(24, min_periods=24).max() / close) - 1
    return out


def _resample_mark(mark: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    pandas_frequency = {
        "5m": "5min",
        "15m": "15min",
        "30m": "30min",
        "1h": "1h",
        "4h": "4h",
        "1d": "1D",
    }.get(timeframe, timeframe)
    resampled = (
        mark.set_index("date")[["close"]]
        .resample(pandas_frequency)
        .last()
        .rename(columns={"close": "mark_close"})
        .dropna()
        .reset_index()
    )
    return resampled


def _prepare_funding(funding: pd.DataFrame) -> pd.DataFrame:
    prepared = funding[["date", "open"]].rename(columns={"open": "funding_rate"}).copy()
    prepared["funding_rate"] = pd.to_numeric(prepared["funding_rate"], errors="coerce")
    return prepared.dropna(subset=["funding_rate"]).sort_values("date")


def _merge_optional_sources(
    pair: str,
    frame: pd.DataFrame,
    data_dir: Path,
    missing_optional_sources: dict[str, list[str]],
    timeframe: str,
) -> pd.DataFrame:
    out = frame.copy()
    mark = _load_mark(pair, data_dir)
    if mark is None or mark.empty:
        missing_optional_sources.setdefault(pair, []).append("mark_price")
        out["mark_close"] = np.nan
        out["mark_basis_pct"] = np.nan
    else:
        mark_4h = _resample_mark(mark, timeframe)
        out = pd.merge_asof(out.sort_values("date"), mark_4h, on="date", direction="backward")
        out["mark_basis_pct"] = (out["mark_close"] / out["close"].replace(0, np.nan)) - 1

    funding = _load_funding(pair, data_dir)
    if funding is None or funding.empty:
        missing_optional_sources.setdefault(pair, []).append("funding_rate")
        out["funding_rate"] = np.nan
    else:
        prepared = _prepare_funding(funding)
        out = pd.merge_asof(out.sort_values("date"), prepared, on="date", direction="backward")
    out["funding_rate"] = out["funding_rate"].ffill()
    out["funding_z_60"] = (
        (out["funding_rate"] - out["funding_rate"].rolling(60, min_periods=20).mean())
        / out["funding_rate"].rolling(60, min_periods=20).std().replace(0, np.nan)
    )
    return out


def _add_btc_context(frame: pd.DataFrame, btc_context: pd.DataFrame | None) -> pd.DataFrame:
    out = frame.copy()
    if btc_context is None or btc_context.empty:
        out["btc_return_3"] = np.nan
        out["btc_return_6"] = np.nan
        out["btc_return_12"] = np.nan
        out["btc_ema200_gap"] = np.nan
        out["btc_volatility_12"] = np.nan
    else:
        context = btc_context[
            ["date", "return_3", "return_6", "return_12", "ema200_gap", "volatility_12"]
        ].rename(
            columns={
                "return_3": "btc_return_3",
                "return_6": "btc_return_6",
                "return_12": "btc_return_12",
                "ema200_gap": "btc_ema200_gap",
                "volatility_12": "btc_volatility_12",
            }
        )
        out = pd.merge_asof(out.sort_values("date"), context.sort_values("date"), on="date", direction="backward")
    out["relative_return_6"] = out["return_6"] - out["btc_return_6"]
    out["btc_crash_block"] = out["btc_return_3"] <= -0.055
    out["btc_regime"] = np.select(
        [out["btc_ema200_gap"] > 0.025, out["btc_ema200_gap"] < -0.025],
        ["bull", "bear"],
        default="sideways",
    )
    return out


def build_derivatives_feature_panel(
    pairs: Iterable[str],
    timeframe: str = "4h",
    data_dir: Path = DEFAULT_DATA_DIR,
) -> FeaturePanelResult:
    """Build one feature panel row per pair/time candle."""

    pair_list = list(pairs)
    missing_pairs: list[str] = []
    missing_optional_sources: dict[str, list[str]] = {}
    base_by_pair: dict[str, pd.DataFrame] = {}
    for pair in pair_list:
        raw = _load_ohlcv(pair, timeframe, data_dir)
        if raw is None or raw.empty:
            missing_pairs.append(pair)
            continue
        enriched = _add_base_features(raw)
        enriched["pair"] = pair
        enriched["timeframe"] = timeframe
        enriched = _merge_optional_sources(pair, enriched, data_dir, missing_optional_sources, timeframe)
        base_by_pair[pair] = enriched

    btc_context = base_by_pair.get("BTC/USDT:USDT")
    rows = []
    for pair, frame in base_by_pair.items():
        rows.append(_add_btc_context(frame, btc_context))
    if not rows:
        return FeaturePanelResult(pd.DataFrame(), [], missing_pairs, missing_optional_sources)

    panel = pd.concat(rows, ignore_index=True)
    panel = panel.sort_values(["pair", "date"]).reset_index(drop=True)
    return FeaturePanelResult(panel, sorted(base_by_pair), missing_pairs, missing_optional_sources)
