"""Schema for V13.4.25 Strategy Research Factory reports."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class StrategyResearchFactoryReport:
    reportId: str
    version: str
    status: str
    source: str
    inputReports: list[str]
    inputReportSummaries: dict[str, Any]
    hypothesisCategories: list[str]
    hypotheses: list[dict[str, Any]]
    hypothesisCounts: dict[str, Any]
    topPriorityHypotheses: list[str]
    rejectedHypotheses: list[str]
    nextExperimentPlan: dict[str, Any]
    dryRunApproved: bool
    liveTradingApproved: bool
    warnings: list[str]
    generatedAt: str
    outputReportPath: str
    outputSummaryPath: str
    outputHypothesesPath: str
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
