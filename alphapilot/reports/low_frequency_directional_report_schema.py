"""Schema for V13.4.34 low-frequency directional research report."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class LowFrequencyDirectionalReport:
    reportId: str
    version: str
    isMock: bool
    dryRunApproved: bool
    liveTradingApproved: bool
    strategyId: str
    strategyName: str
    strategyVersion: str
    strategyClass: str
    pairs: list[str]
    timeframe: str
    timerange: str
    resultFile: str
    tradeCount: int
    longTradeCount: int
    shortTradeCount: int
    totalReturnPct: float | None
    slippageAdjustedTotalReturnPct: float | None
    maxDrawdownPct: float | None
    profitFactor: float | None
    slippageAdjustedProfitFactor: float | None
    winRate: float | None
    maxConsecutiveLosses: int | None
    longMetrics: dict[str, Any]
    shortMetrics: dict[str, Any]
    pairPerformance: list[dict[str, Any]]
    monthlyPerformance: list[dict[str, Any]]
    regimeBreakdown: dict[str, Any]
    exitReasonBreakdown: list[dict[str, Any]]
    baselineComparison: dict[str, Any]
    slippageModel: dict[str, Any]
    researchWorthContinuing: bool
    researchDecisionReasons: list[str]
    safetyBoundary: dict[str, bool]
    generatedAt: str
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

