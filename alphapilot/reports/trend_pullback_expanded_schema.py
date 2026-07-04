"""Schema for V13.4.9 Trend Pullback expanded validation reports."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class TrendPullbackExpandedReport:
    reportId: str
    version: str
    strategyId: str
    strategyName: str
    timeframe: str
    timerange: str
    universe: str
    isMock: bool
    dryRunApproved: bool
    requestedPairCount: int
    requestedPairs: list[str]
    supportedPairs: list[str]
    excludedPairs: list[dict[str, Any]]
    rawMetrics: dict[str, Any]
    slippageAdjustedMetrics: dict[str, Any]
    pairPerformance: list[dict[str, Any]] = field(default_factory=list)
    monthlyPerformance: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    qualityGate: dict[str, Any] = field(default_factory=dict)
    nextStepRecommendation: str = ""
    sourceResult: str | None = None
    generatedAt: str = ""
    source: str = "alphapilot_v13_4_9_trend_pullback_expanded_report"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
