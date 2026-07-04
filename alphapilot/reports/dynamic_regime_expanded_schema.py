"""Schema for V13.4.17 Dynamic Regime expanded validation reports."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class DynamicRegimeExpandedReport:
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
    rawMetrics: dict[str, Any]
    slippageStressMetrics: list[dict[str, Any]]
    liquidityGateSummary: dict[str, Any]
    probabilityScoreSummary: dict[str, Any]
    probabilityBucketPerformance: list[dict[str, Any]]
    regimeBreakdown: dict[str, int]
    moduleBreakdown: dict[str, Any]
    dynamicUniverseSummary: dict[str, Any]
    pairBreakdown: list[dict[str, Any]]
    monthlyBreakdown: list[dict[str, Any]]
    qualityGate: dict[str, Any]
    backtestResultPath: str | None
    reportWarnings: list[str] = field(default_factory=list)
    generatedAt: str = ""
    source: str = "alphapilot_v13_4_17_dynamic_regime_expanded_report"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
