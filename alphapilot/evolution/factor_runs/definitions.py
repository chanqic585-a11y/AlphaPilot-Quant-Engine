"""Approved V13.17 factor definitions bound to the restricted DSL."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FactorSpec:
    factorId: str
    name: str
    expression: str
    version: str = "v13.17.0"


DEFAULT_FACTOR_SPECS = (
    FactorSpec(
        "return_1",
        "One-bar return",
        "safe_subtract(safe_divide(close, lag(close, 1)), 1)",
    ),
    FactorSpec(
        "return_6",
        "Six-bar return",
        "safe_subtract(safe_divide(close, lag(close, 6)), 1)",
    ),
    FactorSpec(
        "volatility_12",
        "Twelve-bar realized volatility",
        "rolling_std(safe_subtract(safe_divide(close, lag(close, 1)), 1), 12)",
    ),
    FactorSpec(
        "volume_ratio_20",
        "Volume versus twenty-bar mean",
        "safe_divide(volume, rolling_mean(volume, 20))",
    ),
    FactorSpec(
        "ema_distance_20",
        "Close distance from EMA20",
        "safe_subtract(safe_divide(close, ewm_mean(close, 20)), 1)",
    ),
    FactorSpec(
        "ema_distance_50",
        "Close distance from EMA50",
        "safe_subtract(safe_divide(close, ewm_mean(close, 50)), 1)",
    ),
    FactorSpec("rsi_14", "RSI14", "rsi(close, 14)"),
    FactorSpec(
        "macd_histogram",
        "MACD histogram 12/26/9",
        "macd_histogram(close, 12, 26, 9)",
    ),
    FactorSpec(
        "bollinger_position",
        "Bollinger normalized position",
        "bollinger_position(close, 20, 2)",
    ),
    FactorSpec(
        "atr_pct_14",
        "ATR14 as a fraction of close",
        "safe_divide(atr(high, low, close, 14), close)",
    ),
)


FACTOR_FIELD_TYPES = {
    "open": "number",
    "high": "number",
    "low": "number",
    "close": "number",
    "volume": "number",
}
