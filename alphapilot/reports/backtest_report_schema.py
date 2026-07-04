"""AlphaPilot standard backtest report schema skeleton."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class BacktestMetrics:
    totalReturnPct: float
    maxDrawdownPct: float
    winRate: float
    profitFactor: float
    tradeCount: int
    maxConsecutiveLosses: int
    averageHoldingMinutes: float
    feesPaid: float
    slippageCost: float
    netReturnAfterCosts: float


@dataclass
class AlphaPilotBacktestReport:
    strategyId: str
    strategyVersion: str
    market: str
    timeframe: str
    universe: list[str]
    timerange: str
    config: dict[str, Any]
    metrics: BacktestMetrics
    pairPerformance: list[dict[str, Any]] = field(default_factory=list)
    monthlyPerformance: list[dict[str, Any]] = field(default_factory=list)
    trades: list[dict[str, Any]] = field(default_factory=list)
    skippedSignals: list[dict[str, Any]] = field(default_factory=list)
    riskGateSummary: dict[str, Any] = field(default_factory=dict)
    auditSummary: dict[str, Any] = field(default_factory=dict)
    generatedAt: str = ""
    isMock: bool = True
    source: str = "alphapilot_report_exporter_v13_3"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
