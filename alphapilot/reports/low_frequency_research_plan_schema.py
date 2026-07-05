"""Report schema for V13.4.31 low-frequency research plan."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class LowFrequencyResearchPlanReport:
    reportId: str
    currentStatus: str
    sourceReports: list[str]
    inputReportSummaries: dict[str, Any]
    scope: dict[str, Any]
    hypotheses: list[dict[str, Any]]
    longShortFramework: dict[str, Any]
    minimalConditionsPhilosophy: dict[str, Any]
    benchmarkRequirements: list[str]
    evaluationMetrics: list[str]
    dataRequirements: list[str]
    optionalFutureData: list[str]
    nextStepRecommendation: str
    dryRunApproved: bool
    liveTradingApproved: bool
    generatedAt: str
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
