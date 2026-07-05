"""Alpha101-style factor overlay helpers for V13.5.7.

The implementation is concept-inspired, not copied from external projects. It
uses local public feature-panel rows only and builds a compact set of
cross-sectional rank, time-series rank, correlation, and decay-style factors
for candidate filtering. It does not download data, use API keys, call exchange
endpoints, create orders, or auto trade.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


ALPHA101_STYLE_FACTOR_COLUMNS = [
    "cs_return_3_rank",
    "cs_return_12_rank",
    "cs_volume_ratio_rank",
    "cs_bollinger_z_rank",
    "cs_mark_basis_rank",
    "cs_atr_rank",
    "cs_liquidity_rank",
    "ts_return_3_rank_24",
    "ts_return_12_rank_24",
    "ts_volume_ratio_rank_24",
    "ts_bollinger_z_rank_24",
    "ts_close_location_rank_24",
    "ts_return_volume_corr_24",
    "decay_return_12",
    "decay_volume_pressure_12",
    "alpha_rebound_pressure",
    "alpha_exhaustion_pressure",
    "alpha_liquidity_quality",
]


def _cross_section_rank(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(np.nan, index=frame.index)
    return frame.groupby("date")[column].rank(method="average", pct=True)


def _rolling_rank(frame: pd.DataFrame, column: str, window: int = 24) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(np.nan, index=frame.index)

    def rank_last(values: pd.Series) -> pd.Series:
        return values.rolling(window, min_periods=max(6, window // 3)).rank(method="average", pct=True)

    return frame.groupby("pair", group_keys=False)[column].apply(rank_last)


def _rolling_corr(frame: pd.DataFrame, left: str, right: str, window: int = 24) -> pd.Series:
    if left not in frame.columns or right not in frame.columns:
        return pd.Series(np.nan, index=frame.index)

    def corr_pair(group: pd.DataFrame) -> pd.Series:
        return group[left].rolling(window, min_periods=max(8, window // 2)).corr(group[right])

    return frame.groupby("pair", group_keys=False).apply(corr_pair).reset_index(level=0, drop=True)


def add_alpha101_style_factors(panel: pd.DataFrame) -> pd.DataFrame:
    """Add compact Alpha101-style factors to a derivative feature panel."""

    if panel.empty:
        return panel.copy()

    out = panel.sort_values(["date", "pair"]).reset_index(drop=True).copy()
    out["volume_change_1"] = out.groupby("pair")["volume"].pct_change(1)
    out["quote_volume_proxy"] = out["close"] * out["volume"]

    out["cs_return_3_rank"] = _cross_section_rank(out, "return_3")
    out["cs_return_12_rank"] = _cross_section_rank(out, "return_12")
    out["cs_volume_ratio_rank"] = _cross_section_rank(out, "volume_ratio")
    out["cs_bollinger_z_rank"] = _cross_section_rank(out, "bollinger_z")
    out["cs_mark_basis_rank"] = _cross_section_rank(out, "mark_basis_pct")
    out["cs_atr_rank"] = _cross_section_rank(out, "atr_pct")
    out["cs_liquidity_rank"] = _cross_section_rank(out, "quote_volume_proxy")

    out["ts_return_3_rank_24"] = _rolling_rank(out, "return_3", 24)
    out["ts_return_12_rank_24"] = _rolling_rank(out, "return_12", 24)
    out["ts_volume_ratio_rank_24"] = _rolling_rank(out, "volume_ratio", 24)
    out["ts_bollinger_z_rank_24"] = _rolling_rank(out, "bollinger_z", 24)
    out["ts_close_location_rank_24"] = _rolling_rank(out, "close_location", 24)
    out["ts_return_volume_corr_24"] = _rolling_corr(out, "return_1", "volume_change_1", 24)

    out["decay_return_12"] = out.groupby("pair")["return_1"].transform(
        lambda values: values.ewm(span=12, adjust=False, min_periods=6).mean()
    )
    wick_pressure = out["close_location"].fillna(0.5) * out["volume_ratio"].fillna(1.0)
    out["decay_volume_pressure_12"] = wick_pressure.groupby(out["pair"]).transform(
        lambda values: values.ewm(span=12, adjust=False, min_periods=6).mean()
    )

    out["alpha_rebound_pressure"] = (
        (1 - out["cs_return_12_rank"])
        * out["cs_volume_ratio_rank"]
        * out["close_location"].clip(0, 1)
        * (1 - out["cs_bollinger_z_rank"])
    )
    out["alpha_exhaustion_pressure"] = (
        out["cs_return_12_rank"]
        * out["cs_volume_ratio_rank"]
        * (1 - out["close_location"].clip(0, 1))
        * out["cs_bollinger_z_rank"]
    )
    out["alpha_liquidity_quality"] = out["cs_liquidity_rank"] * (1 - out["cs_atr_rank"].fillna(0.5) * 0.35)
    return out
