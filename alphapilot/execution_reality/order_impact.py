"""Order impact estimation skeleton for research-only execution checks."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class OrderImpactInput:
    positionNotional: float
    lastPrice: float | None = None
    bidAskSpreadPct: float | None = None
    orderbookDepth: float | None = None
    quoteVolume1h: float | None = None
    quoteVolume24h: float | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class OrderImpactResult:
    estimatedImpactPct: float | None
    impactLevel: str
    maxRecommendedNotional: float | None
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _impact_level(impact: float | None) -> str:
    if impact is None:
        return "unavailable"
    if impact <= 0.001:
        return "low"
    if impact <= 0.005:
        return "medium"
    if impact <= 0.02:
        return "high"
    return "extreme"


def estimate_order_impact(inputs: OrderImpactInput) -> OrderImpactResult:
    """Estimate theoretical order impact without interacting with an exchange."""
    warnings: list[str] = []
    if inputs.positionNotional <= 0:
        return OrderImpactResult(
            estimatedImpactPct=None,
            impactLevel="unavailable",
            maxRecommendedNotional=None,
            warnings=["positionNotional must be positive"],
        )

    denominator = None
    max_recommended = None
    if inputs.orderbookDepth and inputs.orderbookDepth > 0:
        denominator = inputs.orderbookDepth
        max_recommended = inputs.orderbookDepth * 0.10
    elif inputs.quoteVolume1h and inputs.quoteVolume1h > 0:
        denominator = inputs.quoteVolume1h
        max_recommended = inputs.quoteVolume1h * 0.001
        warnings.append("orderbookDepth unavailable; using quoteVolume1h approximation")
    elif inputs.quoteVolume24h and inputs.quoteVolume24h > 0:
        denominator = inputs.quoteVolume24h
        max_recommended = inputs.quoteVolume24h * 0.00005
        warnings.append("orderbookDepth and quoteVolume1h unavailable; using quoteVolume24h approximation")

    if denominator is None:
        return OrderImpactResult(
            estimatedImpactPct=None,
            impactLevel="unavailable",
            maxRecommendedNotional=None,
            warnings=warnings + ["no depth or volume data available"],
        )

    impact = inputs.positionNotional / denominator
    spread = inputs.bidAskSpreadPct or 0.0
    estimated = round(impact + spread, 6)
    return OrderImpactResult(
        estimatedImpactPct=estimated,
        impactLevel=_impact_level(estimated),
        maxRecommendedNotional=round(max_recommended, 8) if max_recommended is not None else None,
        warnings=warnings,
    )

