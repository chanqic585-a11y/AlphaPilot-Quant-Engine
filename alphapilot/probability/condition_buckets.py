"""Condition bucket helpers for V13.4.14 probability scoring."""

from __future__ import annotations

import math
from typing import Any


def safe_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def round_optional(value: Any, digits: int = 8) -> float | None:
    number = safe_float(value)
    return round(number, digits) if number is not None else None


def liquidity_bucket(quote_volume_24h: Any) -> str:
    value = safe_float(quote_volume_24h)
    if value is None or value <= 0:
        return "unavailable"
    if value >= 1_000_000_000:
        return "high"
    if value >= 100_000_000:
        return "medium"
    return "low"


def volatility_bucket(atr_pct: Any) -> str:
    value = safe_float(atr_pct)
    if value is None or value < 0:
        return "unavailable"
    if value < 0.02:
        return "low"
    if value < 0.05:
        return "medium"
    if value < 0.08:
        return "high"
    return "extreme"


def rsi_bucket(rsi14: Any) -> str:
    value = safe_float(rsi14)
    if value is None:
        return "unavailable"
    if value < 30:
        return "below30"
    if value < 45:
        return "30-45"
    if value < 55:
        return "45-55"
    if value < 65:
        return "55-65"
    return "above65"


def ema_distance_bucket(close: Any, ema20: Any) -> str:
    price = safe_float(close)
    ema = safe_float(ema20)
    if price is None or price <= 0 or ema is None:
        return "unavailable"
    distance = (price - ema) / price
    if distance < -0.005:
        return "below_ema20"
    if abs(distance) <= 0.01:
        return "near_ema20"
    if distance > 0.03:
        return "extended_above_ema20"
    return "above_ema20"


def bollinger_position_bucket(close: Any, lower: Any, middle: Any, upper: Any) -> str:
    price = safe_float(close)
    low = safe_float(lower)
    mid = safe_float(middle)
    high = safe_float(upper)
    if price is None or low is None or mid is None or high is None or high <= low:
        return "unavailable"
    if price < low or price > high:
        return "outside"
    if price <= mid:
        return "lower"
    upper_mid = mid + ((high - mid) * 0.5)
    if price >= upper_mid:
        return "upper"
    return "middle"


def btc_state(close: Any, ema200: Any, return_3h: Any) -> str:
    price = safe_float(close)
    ema = safe_float(ema200)
    ret = safe_float(return_3h)
    if price is None or ema is None or ret is None:
        return "unknown"
    if ret <= -0.015:
        return "crash"
    if ret <= -0.008 or price < ema:
        return "weak"
    return "safe"


def regime_candidate(close: Any, ema20: Any, ema50: Any, ema200: Any, rsi14: Any, atr_pct: Any, btc: str) -> str:
    price = safe_float(close)
    e20 = safe_float(ema20)
    e50 = safe_float(ema50)
    e200 = safe_float(ema200)
    rsi = safe_float(rsi14)
    atr = safe_float(atr_pct)
    if price is None or e20 is None or e50 is None or e200 is None or rsi is None:
        return "unknown"
    if btc == "crash" or (atr is not None and atr >= 0.08):
        return "avoid"
    if price > e200 and e20 > e50 and rsi >= 55:
        return "trend"
    if rsi <= 45 or price < e20:
        return "mean_reversion"
    if price < e200 and e20 < e50:
        return "avoid"
    return "unknown"


def bucket_id(parts: list[str]) -> str:
    return "_".join(part.replace("/", "_").replace(":", "_") for part in parts)

