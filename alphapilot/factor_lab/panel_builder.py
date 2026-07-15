"""Build deterministic wide panels from immutable canonical Parquet files."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import numpy as np
import pandas as pd

from .panel_schema import FactorDataPanel


def _wide(frames: dict[str, pd.DataFrame], column: str) -> pd.DataFrame:
    return pd.concat({symbol: frame.set_index("date")[column] for symbol, frame in frames.items()}, axis=1).sort_index()


def build_factor_panel(paths: Mapping[str, Path | str]) -> FactorDataPanel:
    frames: dict[str, pd.DataFrame] = {}
    required = ["date", "open", "high", "low", "close", "volume"]
    for symbol, path in sorted(paths.items()):
        frame = pd.read_parquet(path, columns=required)
        frame["date"] = pd.to_datetime(frame["date"], utc=True)
        frame = frame.drop_duplicates("date", keep="last").sort_values("date")
        frames[symbol] = frame
    if not frames:
        raise ValueError("at least one OHLCV source is required")
    open_ = _wide(frames, "open")
    high = _wide(frames, "high")
    low = _wide(frames, "low")
    close = _wide(frames, "close")
    volume = _wide(frames, "volume")
    amount = close * volume
    typical = (high + low + close) / 3
    vwap = typical.where(volume > 0, np.nan)
    returns = close.pct_change(fill_method=None)
    market_return = returns.mean(axis=1, skipna=True)
    return FactorDataPanel(
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=volume,
        amount=amount,
        vwap=vwap,
        returns=returns,
        btc_return=returns.get("BTC-USDT-SWAP"),
        eth_return=returns.get("ETH-USDT-SWAP"),
        market_return=market_return,
        market_breadth=(returns > 0).sum(axis=1).div(returns.notna().sum(axis=1).replace(0, np.nan)),
        cap_or_liquidity_proxy=amount.rolling(20, min_periods=5).mean(),
    )
