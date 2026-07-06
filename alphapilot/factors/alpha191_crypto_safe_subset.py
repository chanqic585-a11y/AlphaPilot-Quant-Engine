"""Crypto-safe Alpha191-inspired factor subset for V13.5.23.

The factors in this module are inspired by the Alpha191 category catalog that
AlphaPilot extracted in V13.5.22. They are not copied formulas. They are compact
OHLCV-derived features designed for crypto public-data research only.

No exchange requests, API keys, account reads, order creation, or automatic
trading are performed here.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


ALPHA191_CRYPTO_SAFE_FACTOR_COLUMNS = [
    "a191_return_volume_corr_24",
    "a191_return_volume_corr_48",
    "a191_ts_close_location_rank_48",
    "a191_ts_volume_ratio_rank_48",
    "a191_cs_range_rank",
    "a191_cs_volume_activity_rank",
    "a191_cs_residual_strength_rank",
    "a191_reversal_pressure",
    "a191_short_exhaustion_pressure",
    "a191_range_rejection_pressure",
    "a191_liquidity_range_quality",
    "a191_volume_reclaim_pressure",
]


def _cross_section_rank(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(np.nan, index=frame.index)
    return frame.groupby("date")[column].rank(method="average", pct=True)


def _rolling_rank(frame: pd.DataFrame, column: str, window: int) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(np.nan, index=frame.index)

    def rank_pair(values: pd.Series) -> pd.Series:
        return values.rolling(window, min_periods=max(8, window // 3)).rank(method="average", pct=True)

    return frame.groupby("pair", group_keys=False)[column].apply(rank_pair)


def _rolling_corr(frame: pd.DataFrame, left: str, right: str, window: int) -> pd.Series:
    if left not in frame.columns or right not in frame.columns:
        return pd.Series(np.nan, index=frame.index)

    def corr_pair(group: pd.DataFrame) -> pd.Series:
        return group[left].rolling(window, min_periods=max(12, window // 2)).corr(group[right])

    return frame.groupby("pair", group_keys=False).apply(corr_pair).reset_index(level=0, drop=True)


def _bounded(series: pd.Series, lower: float = 0.0, upper: float = 1.0) -> pd.Series:
    return series.astype(float).clip(lower, upper)


def add_alpha191_crypto_safe_factors(panel: pd.DataFrame) -> pd.DataFrame:
    """Add a small Alpha191-inspired feature subset to a derivatives panel."""

    if panel.empty:
        return panel.copy()

    out = panel.sort_values(["date", "pair"]).reset_index(drop=True).copy()

    if "volume_change_1" not in out.columns:
        out["volume_change_1"] = out.groupby("pair")["volume"].pct_change(1)
    if "quote_volume_proxy" not in out.columns:
        out["quote_volume_proxy"] = out["close"] * out["volume"]

    if "cs_return_12_rank" not in out.columns:
        out["cs_return_12_rank"] = _cross_section_rank(out, "return_12")
    if "cs_volume_ratio_rank" not in out.columns:
        out["cs_volume_ratio_rank"] = _cross_section_rank(out, "volume_ratio")
    if "cs_bollinger_z_rank" not in out.columns:
        out["cs_bollinger_z_rank"] = _cross_section_rank(out, "bollinger_z")
    if "cs_atr_rank" not in out.columns:
        out["cs_atr_rank"] = _cross_section_rank(out, "atr_pct")
    if "cs_liquidity_rank" not in out.columns:
        out["cs_liquidity_rank"] = _cross_section_rank(out, "quote_volume_proxy")

    out["a191_return_volume_corr_24"] = _rolling_corr(out, "return_1", "volume_change_1", 24)
    out["a191_return_volume_corr_48"] = _rolling_corr(out, "return_1", "volume_change_1", 48)
    out["a191_ts_close_location_rank_48"] = _rolling_rank(out, "close_location", 48)
    out["a191_ts_volume_ratio_rank_48"] = _rolling_rank(out, "volume_ratio", 48)
    out["a191_cs_range_rank"] = _cross_section_rank(out, "range_pct")
    out["a191_cs_volume_activity_rank"] = _cross_section_rank(out, "volume_ratio")
    out["a191_cs_residual_strength_rank"] = _cross_section_rank(out, "relative_return_6")

    close_location = _bounded(out["close_location"].fillna(0.5))
    upper_rejection = _bounded(1.0 - close_location)
    lower_reclaim = close_location
    volume_rank = _bounded(out["cs_volume_ratio_rank"].fillna(0.5))
    return_rank = _bounded(out["cs_return_12_rank"].fillna(0.5))
    bollinger_rank = _bounded(out["cs_bollinger_z_rank"].fillna(0.5))
    range_rank = _bounded(out["a191_cs_range_rank"].fillna(0.5))
    liquidity_rank = _bounded(out["cs_liquidity_rank"].fillna(0.5))
    atr_rank = _bounded(out["cs_atr_rank"].fillna(0.5))
    residual_rank = _bounded(out["a191_cs_residual_strength_rank"].fillna(0.5))
    ts_volume_rank = _bounded(out["a191_ts_volume_ratio_rank_48"].fillna(0.5))

    out["a191_reversal_pressure"] = (
        (1.0 - return_rank)
        * volume_rank
        * (1.0 - bollinger_rank)
        * lower_reclaim
        * ts_volume_rank
    )
    out["a191_short_exhaustion_pressure"] = (
        return_rank
        * volume_rank
        * bollinger_rank
        * upper_rejection
        * ts_volume_rank
    )
    out["a191_range_rejection_pressure"] = range_rank * volume_rank * upper_rejection * bollinger_rank
    out["a191_liquidity_range_quality"] = liquidity_rank * (1.0 - atr_rank * 0.35) * (1.0 - range_rank * 0.15)
    out["a191_volume_reclaim_pressure"] = (
        volume_rank
        * lower_reclaim
        * (1.0 - bollinger_rank)
        * _bounded(1.0 - residual_rank)
    )

    return out
