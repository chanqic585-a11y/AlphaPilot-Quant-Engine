"""Typed wide factor panel. Missing observations intentionally remain NaN."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class FactorDataPanel:
    open: pd.DataFrame
    high: pd.DataFrame
    low: pd.DataFrame
    close: pd.DataFrame
    volume: pd.DataFrame
    amount: pd.DataFrame
    vwap: pd.DataFrame
    returns: pd.DataFrame
    funding: pd.DataFrame | None = None
    open_interest: pd.DataFrame | None = None
    basis: pd.DataFrame | None = None
    liquidation: pd.DataFrame | None = None
    spread_proxy: pd.DataFrame | None = None
    btc_return: pd.Series | None = None
    eth_return: pd.Series | None = None
    market_return: pd.Series | None = None
    market_breadth: pd.Series | None = None
    cap_or_liquidity_proxy: pd.DataFrame | None = None
