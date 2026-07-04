"""Schema for V13.4.20 Alpha factor research design report."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class AlphaFactorResearchDesignReport:
    reportId: str
    purpose: str
    sourceInsights: list[str]
    factorDataPanel: dict[str, Any]
    operatorSubset: dict[str, Any]
    manualFactorLibrary: list[dict[str, Any]]
    factorEvaluationMetrics: dict[str, Any]
    benchmarkSuite: dict[str, Any]
    strategyResearchFactory: dict[str, Any]
    integrationWithDynamicRegime: dict[str, Any]
    dryRunApproved: bool
    liveTradingApproved: bool
    nextStepRecommendation: str
    generatedAt: str
    warnings: list[str] = field(default_factory=list)
    source: str = "alphapilot_v13_4_20_alpha_factor_research_design"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
