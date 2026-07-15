"""Whitelisted factor operators with explicit lookback and NaN semantics."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

PandasValue = pd.Series | pd.DataFrame


def _sanitize(value: Any) -> Any:
    if isinstance(value, (pd.Series, pd.DataFrame)):
        return value.replace([np.inf, -np.inf], np.nan)
    if isinstance(value, np.ndarray):
        result = value.astype(float, copy=True)
        result[~np.isfinite(result)] = np.nan
        return result
    if isinstance(value, (float, np.floating)) and not np.isfinite(value):
        return np.nan
    return value


def _window(window: int, min_periods: int) -> None:
    if window <= 0:
        raise ValueError("window must be positive")
    if min_periods <= 0 or min_periods > window:
        raise ValueError("min_periods must be in [1, window]")


def rank(values: PandasValue, *, pit_mask: PandasValue | None = None) -> PandasValue:
    data = values.where(pit_mask) if pit_mask is not None else values
    if isinstance(data, pd.DataFrame):
        return _sanitize(data.rank(axis=1, pct=True, method="average"))
    return _sanitize(data.rank(pct=True, method="average"))


def zscore(values: PandasValue) -> PandasValue:
    if isinstance(values, pd.DataFrame):
        mean = values.mean(axis=1)
        std = values.std(axis=1, ddof=0).replace(0, np.nan)
        return _sanitize(values.sub(mean, axis=0).div(std, axis=0))
    std = values.std(ddof=0)
    return _sanitize((values - values.mean()) / (std if std != 0 else np.nan))


def scale(values: PandasValue) -> PandasValue:
    if isinstance(values, pd.DataFrame):
        denominator = values.abs().sum(axis=1).replace(0, np.nan)
        return _sanitize(values.div(denominator, axis=0))
    denominator = values.abs().sum()
    return _sanitize(values / (denominator if denominator != 0 else np.nan))


def winsorize(values: PandasValue, lower: float = 0.01, upper: float = 0.99) -> PandasValue:
    if not 0 <= lower < upper <= 1:
        raise ValueError("winsorize bounds must satisfy 0 <= lower < upper <= 1")
    if isinstance(values, pd.DataFrame):
        lows = values.quantile(lower, axis=1)
        highs = values.quantile(upper, axis=1)
        return _sanitize(values.clip(lows, highs, axis=0))
    return _sanitize(values.clip(values.quantile(lower), values.quantile(upper)))


def delay(values: PandasValue, periods: int) -> PandasValue:
    if periods < 0:
        raise ValueError("delay periods must be non-negative")
    return _sanitize(values.shift(periods))


def delta(values: PandasValue, periods: int) -> PandasValue:
    return _sanitize(values - delay(values, periods))


def ts_rank(values: PandasValue, window: int, min_periods: int) -> PandasValue:
    _window(window, min_periods)
    return _sanitize(
        values.rolling(window, min_periods=min_periods).apply(
            lambda item: pd.Series(item).rank(pct=True, method="average").iloc[-1], raw=False
        )
    )


def ts_corr(left: PandasValue, right: PandasValue, window: int, min_periods: int) -> PandasValue:
    _window(window, min_periods)
    return _sanitize(left.rolling(window, min_periods=min_periods).corr(right))


def ts_cov(left: PandasValue, right: PandasValue, window: int, min_periods: int) -> PandasValue:
    _window(window, min_periods)
    return _sanitize(left.rolling(window, min_periods=min_periods).cov(right))


def ts_mean(values: PandasValue, window: int, min_periods: int) -> PandasValue:
    _window(window, min_periods)
    return _sanitize(values.rolling(window, min_periods=min_periods).mean())


def ts_std(values: PandasValue, window: int, min_periods: int) -> PandasValue:
    _window(window, min_periods)
    return _sanitize(values.rolling(window, min_periods=min_periods).std(ddof=0))


def ts_sum(values: PandasValue, window: int, min_periods: int) -> PandasValue:
    _window(window, min_periods)
    return _sanitize(values.rolling(window, min_periods=min_periods).sum())


def ts_product(values: PandasValue, window: int, min_periods: int) -> PandasValue:
    _window(window, min_periods)
    return _sanitize(values.rolling(window, min_periods=min_periods).apply(np.prod, raw=True))


def ts_min(values: PandasValue, window: int, min_periods: int) -> PandasValue:
    _window(window, min_periods)
    return _sanitize(values.rolling(window, min_periods=min_periods).min())


def ts_max(values: PandasValue, window: int, min_periods: int) -> PandasValue:
    _window(window, min_periods)
    return _sanitize(values.rolling(window, min_periods=min_periods).max())


def ts_argmin(values: PandasValue, window: int, min_periods: int) -> PandasValue:
    _window(window, min_periods)
    return _sanitize(values.rolling(window, min_periods=min_periods).apply(np.nanargmin, raw=True))


def ts_argmax(values: PandasValue, window: int, min_periods: int) -> PandasValue:
    _window(window, min_periods)
    return _sanitize(values.rolling(window, min_periods=min_periods).apply(np.nanargmax, raw=True))


def ts_ema(values: PandasValue, span: int, min_periods: int) -> PandasValue:
    _window(span, min_periods)
    return _sanitize(values.ewm(span=span, min_periods=min_periods, adjust=False).mean())


def ts_slope(values: PandasValue, window: int, min_periods: int) -> PandasValue:
    _window(window, min_periods)

    def slope(item: np.ndarray) -> float:
        valid = np.isfinite(item)
        if valid.sum() < min_periods:
            return np.nan
        x = np.arange(len(item), dtype=float)[valid]
        y = item[valid]
        return float(np.polyfit(x, y, 1)[0])

    return _sanitize(values.rolling(window, min_periods=min_periods).apply(slope, raw=True))


def decay_linear(values: PandasValue, window: int, min_periods: int) -> PandasValue:
    _window(window, min_periods)

    def weighted(item: np.ndarray) -> float:
        valid = np.isfinite(item)
        if valid.sum() < min_periods:
            return np.nan
        weights = np.arange(1, len(item) + 1, dtype=float)[valid]
        return float(np.dot(item[valid], weights) / weights.sum())

    return _sanitize(values.rolling(window, min_periods=min_periods).apply(weighted, raw=True))


def safe_div(numerator: Any, denominator: Any) -> Any:
    if isinstance(denominator, (pd.Series, pd.DataFrame)):
        denominator = denominator.replace(0, np.nan)
    elif isinstance(denominator, np.ndarray):
        denominator = np.where(denominator == 0, np.nan, denominator)
    elif denominator == 0:
        denominator = np.nan
    return _sanitize(numerator / denominator)


def signed_power(values: Any, exponent: float) -> Any:
    return _sanitize(np.sign(values) * np.power(np.abs(values), exponent))


def count(condition: PandasValue, window: int, min_periods: int) -> PandasValue:
    _window(window, min_periods)
    return _sanitize(condition.astype(float).rolling(window, min_periods=min_periods).sum())


def sum_if(values: PandasValue, condition: PandasValue, window: int, min_periods: int) -> PandasValue:
    _window(window, min_periods)
    return _sanitize(values.where(condition, 0.0).rolling(window, min_periods=min_periods).sum())


def rolling_beta(
    dependent: PandasValue,
    independent: PandasValue,
    window: int,
    min_periods: int,
) -> PandasValue:
    variance = ts_cov(independent, independent, window, min_periods)
    covariance = ts_cov(dependent, independent, window, min_periods)
    return safe_div(covariance, variance)


def rolling_residual(
    dependent: PandasValue,
    independent: PandasValue,
    window: int,
    min_periods: int,
) -> PandasValue:
    beta = rolling_beta(dependent, independent, window, min_periods)
    return _sanitize(dependent - beta * independent)


def conditional_select(condition: Any, when_true: Any, when_false: Any) -> Any:
    if isinstance(condition, (pd.Series, pd.DataFrame)):
        return _sanitize(when_true.where(condition, when_false))
    return when_true if condition else when_false


def absolute(values: Any) -> Any:
    return _sanitize(np.abs(values))


OPERATOR_REGISTRY = {
    name: value
    for name, value in globals().copy().items()
    if callable(value)
    and name
    in {
        "rank",
        "zscore",
        "scale",
        "winsorize",
        "delay",
        "delta",
        "ts_rank",
        "ts_corr",
        "ts_cov",
        "ts_mean",
        "ts_std",
        "ts_sum",
        "ts_product",
        "ts_min",
        "ts_max",
        "ts_argmin",
        "ts_argmax",
        "ts_ema",
        "ts_slope",
        "decay_linear",
        "safe_div",
        "signed_power",
        "count",
        "sum_if",
        "rolling_beta",
        "rolling_residual",
        "conditional_select",
        "absolute",
    }
}
