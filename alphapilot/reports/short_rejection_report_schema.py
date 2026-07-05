"""Schemas for V13.4.29 Short Rejection 1H research report."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class SlippageAdjustedMetrics:
    slippageRateOneWay: float
    totalSlippageCost: float
    totalReturnPct: float | None
    profitFactor: float | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ShortRejectionRunSummary:
    scope: str
    resultPath: str
    isRealBacktest: bool
    strategyName: str
    pairs: list[str]
    timerange: str | None
    timeframe: str | None
    tradeCount: int
    shortTradeCount: int
    longTradeCount: int
    totalReturnPct: float | None
    slippageAdjustedTotalReturnPct: float | None
    maxDrawdownPct: float | None
    profitFactor: float | None
    slippageAdjustedProfitFactor: float | None
    winRate: float | None
    maxConsecutiveLosses: int | None
    exitReasonBreakdown: list[dict[str, Any]]
    pairPerformance: list[dict[str, Any]]
    monthlyPerformance: list[dict[str, Any]]
    slippageStress: list[SlippageAdjustedMetrics]
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["slippageStress"] = [item.to_dict() for item in self.slippageStress]
        return payload


@dataclass(frozen=True)
class ShortRejectionReport:
    reportId: str
    version: str
    status: str
    isMock: bool
    strategyId: str
    strategyName: str
    strategyVersion: str
    timeframe: str
    direction: str
    primaryRunScope: str | None
    pairs: list[str]
    timerange: str | None
    tradeCount: int
    shortTradeCount: int
    totalReturnPct: float | None
    slippageAdjustedTotalReturnPct: float | None
    maxDrawdownPct: float | None
    profitFactor: float | None
    slippageAdjustedProfitFactor: float | None
    winRate: float | None
    maxConsecutiveLosses: int | None
    exitReasonBreakdown: list[dict[str, Any]]
    pairPerformance: list[dict[str, Any]]
    monthlyPerformance: list[dict[str, Any]]
    regimeBackground: dict[str, Any]
    excludedPairs: list[str]
    watchlistPairs: list[str]
    exclusionReasons: dict[str, str]
    backtestRuns: list[dict[str, Any]]
    smokeBacktestSucceeded: bool
    expandedBacktestSucceeded: bool
    expandedFailed: bool
    researchGate: dict[str, Any]
    slippageAppliedByFreqtrade: bool
    slippageAppliedByPostProcessing: bool
    dryRunApproved: bool
    liveTradingApproved: bool
    safetyBoundary: dict[str, bool]
    generatedAt: str
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
