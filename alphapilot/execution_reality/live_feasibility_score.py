"""Live feasibility scoring skeleton for research gates."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class LiveFeasibilityInput:
    backtestQuality: float | None
    slippageRobustness: float | None
    liquidityQuality: float | None
    tradeFrequency: float | None
    pairConcentration: float | None
    drawdownRisk: float | None
    lossStreakRisk: float | None
    executionDataAvailability: float | None
    shadowTradingReadiness: float | None
    riskGateReadiness: float | None
    hasShadowTradingResults: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class LiveFeasibilityScore:
    totalScore: float
    level: str
    cappedBy: list[str] = field(default_factory=list)
    componentScores: dict[str, float | None] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


WEIGHTS = {
    "backtestQuality": 0.15,
    "slippageRobustness": 0.15,
    "liquidityQuality": 0.15,
    "tradeFrequency": 0.10,
    "pairConcentration": 0.10,
    "drawdownRisk": 0.10,
    "lossStreakRisk": 0.05,
    "executionDataAvailability": 0.10,
    "shadowTradingReadiness": 0.05,
    "riskGateReadiness": 0.05,
}


def _clamp(value: float | None) -> float | None:
    if value is None:
        return None
    return max(0.0, min(float(value), 100.0))


def _level(score: float) -> str:
    if score <= 39:
        return "not_live_feasible"
    if score <= 59:
        return "research_only"
    if score <= 74:
        return "shadow_ready"
    if score <= 84:
        return "dry_run_candidate"
    return "controlled_live_candidate"


def calculate_live_feasibility_score(inputs: LiveFeasibilityInput) -> LiveFeasibilityScore:
    """Calculate research feasibility without approving live execution."""
    components = {
        key: _clamp(getattr(inputs, key))
        for key in WEIGHTS
    }
    warnings = [f"{key} unavailable" for key, value in components.items() if value is None]
    weighted_sum = 0.0
    available_weight = 0.0
    for key, weight in WEIGHTS.items():
        value = components[key]
        if value is None:
            continue
        weighted_sum += value * weight
        available_weight += weight

    total = 0.0 if available_weight == 0 else weighted_sum / available_weight
    capped_by: list[str] = []
    if not inputs.hasShadowTradingResults and total > 59:
        total = 59.0
        capped_by.append("missing_shadow_trading_results")
    if components.get("liquidityQuality") is None and total > 59:
        total = 59.0
        capped_by.append("missing_liquidity_quality")
    if components.get("slippageRobustness") is None and total > 59:
        total = 59.0
        capped_by.append("missing_slippage_robustness")

    return LiveFeasibilityScore(
        totalScore=round(total, 2),
        level=_level(total),
        cappedBy=capped_by,
        componentScores=components,
        warnings=warnings,
    )

