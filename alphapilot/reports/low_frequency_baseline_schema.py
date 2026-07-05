"""Schema for V13.4.32 low-frequency baseline report."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class LowFrequencyBaselineReport:
    reportId: str
    version: str
    status: str
    timerange: str
    pairs: list[str]
    timeframes: list[str]
    dataReportPath: str
    researchPlanPath: str
    dataQualitySummary: dict[str, Any]
    baselines: dict[str, Any]
    comparisonTable: list[dict[str, Any]]
    benchmarkRequirementsForFutureStrategy: list[str]
    interpretation: list[str]
    safetyBoundary: dict[str, bool]
    generatedAt: str
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
