"""Research-only liquidity gate skeleton.

The liquidity gate estimates whether a theoretical position has enough public
liquidity context to be considered for later shadow trading research. It never
places orders and never calls exchange private endpoints.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class LiquidityGateInput:
    symbol: str
    timestamp: str
    marketType: str
    positionNotional: float
    lastPrice: float | None = None
    quoteVolume24h: float | None = None
    quoteVolume1h: float | None = None
    bidAskSpreadPct: float | None = None
    orderbookDepthTop5: float | None = None
    orderbookDepthTop10: float | None = None
    maxPositionToVolumePct: float = 0.001
    maxPositionToDepthPct: float = 0.10

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class LiquidityGateResult:
    approved: bool
    decision: str
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    liquidityScore: float = 0.0
    estimatedSlippagePct: float | None = None
    maxRecommendedNotional: float | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def _positive(value: float | None) -> bool:
    return value is not None and value > 0


def _estimate_slippage_pct(inputs: LiquidityGateInput) -> float | None:
    if inputs.bidAskSpreadPct is None and not _positive(inputs.orderbookDepthTop5) and not _positive(inputs.quoteVolume1h):
        return None
    spread_component = (inputs.bidAskSpreadPct or 0.0) / 2
    depth_component = 0.0
    if _positive(inputs.orderbookDepthTop5):
        depth_component = min(inputs.positionNotional / float(inputs.orderbookDepthTop5), 1.0) * 0.002
    elif _positive(inputs.quoteVolume1h):
        depth_component = min(inputs.positionNotional / float(inputs.quoteVolume1h), 1.0) * 0.001
    return round(spread_component + depth_component, 6)


def _max_recommended_notional(inputs: LiquidityGateInput) -> float | None:
    candidates: list[float] = []
    if _positive(inputs.quoteVolume1h):
        candidates.append(float(inputs.quoteVolume1h) * inputs.maxPositionToVolumePct)
    if _positive(inputs.orderbookDepthTop5):
        candidates.append(float(inputs.orderbookDepthTop5) * inputs.maxPositionToDepthPct)
    if _positive(inputs.orderbookDepthTop10):
        candidates.append(float(inputs.orderbookDepthTop10) * inputs.maxPositionToDepthPct)
    return round(min(candidates), 8) if candidates else None


def evaluate_liquidity_gate(inputs: LiquidityGateInput) -> LiquidityGateResult:
    """Evaluate liquidity context without approving any real execution."""
    reasons: list[str] = ["liquidity_gate_research_only", "no_order_will_be_created"]
    warnings: list[str] = []

    if not inputs.symbol or inputs.positionNotional <= 0 or not _positive(inputs.lastPrice):
        return LiquidityGateResult(
            approved=False,
            decision="insufficient_liquidity_data",
            reasons=reasons + ["symbol_position_notional_or_price_missing"],
            warnings=warnings,
            liquidityScore=0.0,
        )

    if not _positive(inputs.quoteVolume1h):
        warnings.append("quoteVolume1h unavailable; liquidity gate cannot approve by volume.")
    if inputs.bidAskSpreadPct is None:
        warnings.append("bidAskSpreadPct unavailable; spread risk cannot be measured.")
    if not _positive(inputs.orderbookDepthTop5):
        warnings.append("orderbookDepthTop5 unavailable; depth impact cannot be measured.")

    max_notional = _max_recommended_notional(inputs)
    estimated_slippage = _estimate_slippage_pct(inputs)
    score = 100.0

    if not _positive(inputs.quoteVolume1h) and not _positive(inputs.orderbookDepthTop5):
        return LiquidityGateResult(
            approved=False,
            decision="insufficient_liquidity_data",
            reasons=reasons + ["no_1h_volume_or_orderbook_depth"],
            warnings=warnings,
            liquidityScore=0.0,
            estimatedSlippagePct=estimated_slippage,
            maxRecommendedNotional=max_notional,
        )

    if _positive(inputs.quoteVolume1h) and inputs.positionNotional > float(inputs.quoteVolume1h) * inputs.maxPositionToVolumePct:
        reasons.append("position_notional_exceeds_1h_volume_limit")
        score -= 45
    if inputs.bidAskSpreadPct is not None and inputs.bidAskSpreadPct > 0.0008:
        reasons.append("bid_ask_spread_too_wide")
        score -= 35
    if _positive(inputs.orderbookDepthTop5) and inputs.positionNotional > float(inputs.orderbookDepthTop5) * inputs.maxPositionToDepthPct:
        reasons.append("position_notional_exceeds_top5_depth_limit")
        score -= 45
    if warnings:
        score -= min(len(warnings) * 10, 30)

    score = round(max(score, 0.0), 2)
    blocking_reasons = {
        "position_notional_exceeds_1h_volume_limit",
        "bid_ask_spread_too_wide",
        "position_notional_exceeds_top5_depth_limit",
    }
    if any(reason in blocking_reasons for reason in reasons):
        decision = "rejected_by_liquidity_gate" if score < 60 else "needs_review"
        approved = False
    elif warnings:
        decision = "needs_review"
        approved = False
    else:
        decision = "approved_for_shadow_research"
        approved = True

    return LiquidityGateResult(
        approved=approved,
        decision=decision,
        reasons=reasons,
        warnings=warnings,
        liquidityScore=score,
        estimatedSlippagePct=estimated_slippage,
        maxRecommendedNotional=max_notional,
    )

