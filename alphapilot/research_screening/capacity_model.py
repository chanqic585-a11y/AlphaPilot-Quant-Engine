"""Preregisterable liquidity-capacity checks for competing signals."""

from __future__ import annotations

from typing import Any


def _ratio(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator > 0 else float("inf")


def evaluate_capacity(
    *,
    order_notional: float,
    quote_volume_24h: float,
    bar_quote_volume: float,
    depth_proxy: float,
    maximum_24h_ratio: float,
    maximum_bar_ratio: float,
    maximum_depth_ratio: float,
) -> dict[str, Any]:
    ratios = {
        "orderNotionalTo24hQuoteVolume": _ratio(order_notional, quote_volume_24h),
        "orderNotionalToBarQuoteVolume": _ratio(order_notional, bar_quote_volume),
        "orderNotionalToDepthProxy": _ratio(order_notional, depth_proxy),
    }
    passed = all(
        (
            ratios["orderNotionalTo24hQuoteVolume"] <= maximum_24h_ratio,
            ratios["orderNotionalToBarQuoteVolume"] <= maximum_bar_ratio,
            ratios["orderNotionalToDepthProxy"] <= maximum_depth_ratio,
        )
    )
    estimated_slippage = min(10_000.0, ratios["orderNotionalToDepthProxy"] * 100.0)
    return {
        **ratios,
        "estimatedSlippageBps": estimated_slippage,
        "capacityPassed": passed,
    }
