"""Schema for V13.4.35 multi-strategy batch research report."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class MultiStrategyResult:
    strategyId: str
    strategyClass: str
    direction: str
    resultPath: str | None
    status: str
    isRealBacktest: bool
    tradeCount: int
    totalReturnPct: float | None
    slippageAdjustedReturnPct: float | None
    maxDrawdownPct: float | None
    profitFactor: float | None
    slippageAdjustedProfitFactor: float | None
    winRate: float | None
    maxConsecutiveLosses: int | None
    feesPaid: float | None
    slippageCost: float | None
    pairPerformance: list[dict[str, Any]]
    monthlyPerformance: list[dict[str, Any]]
    exitReasonBreakdown: list[dict[str, Any]]
    baselineComparison: dict[str, Any]
    researchWorthContinuing: bool
    decisionReasons: list[str]
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MultiStrategyBatchReport:
    reportId: str
    version: str
    isMock: bool
    dryRunApproved: bool
    liveTradingApproved: bool
    timerange: str
    timeframe: str
    pairs: list[str]
    manifestPath: str
    expandedTop10Executed: bool
    expandedTop10Reason: str | None
    strategyResults: list[dict[str, Any]]
    leaderboardRaw: list[dict[str, Any]]
    leaderboardSlippageAdjusted: list[dict[str, Any]]
    longOnlyResults: list[dict[str, Any]]
    shortOnlyResults: list[dict[str, Any]]
    mixedDirectionResults: list[dict[str, Any]]
    bestRawStrategy: dict[str, Any] | None
    bestSlippageAdjustedStrategy: dict[str, Any] | None
    failedStrategies: list[dict[str, Any]]
    baselineComparison: dict[str, Any]
    recommendations: list[str]
    slippageModel: dict[str, Any]
    safetyBoundary: dict[str, bool]
    generatedAt: str
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
