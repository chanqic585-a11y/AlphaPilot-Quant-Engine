"""Schema for V13.4.16 Dynamic Regime smoke backtest reports."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class DynamicRegimeSmokeReport:
    reportId: str
    version: str
    strategyId: str
    strategyName: str
    strategyVersion: str
    timerange: str
    timeframe: str
    pairs: list[str]
    isMock: bool
    dryRunApproved: bool
    liveTradingApproved: bool
    metrics: dict[str, Any]
    regimeBreakdown: dict[str, int]
    moduleBreakdown: dict[str, Any]
    probabilityScoreSummary: dict[str, Any]
    liquidityGateSummary: dict[str, Any]
    backtestResultPath: str | None
    reportWarnings: list[str] = field(default_factory=list)
    generatedAt: str = ""
    source: str = "alphapilot_v13_4_16_dynamic_regime_smoke_report"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

