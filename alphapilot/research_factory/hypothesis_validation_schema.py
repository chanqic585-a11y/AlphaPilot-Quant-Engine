"""Schema for V13.4.26 hypothesis validation.

The validation dataset is research-only. Conditions use point-in-time factors.
Forward labels are evaluation targets only and must never be used to create
conditions, orders, Dry-run approvals, or live-trading approvals.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal


SupportLevel = Literal[
    "strong_research_support",
    "moderate_research_support",
    "weak_research_support",
    "no_support",
    "insufficient_sample",
]


@dataclass(frozen=True)
class HypothesisValidationConfig:
    hypothesesPath: str
    factorPanelPath: str | None
    timerange: str
    timeframe: str
    horizons: list[int]
    tpPct: float
    slPct: float
    dataPath: str
    useDynamicUniverse: bool
    universeSnapshotsPath: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class HypothesisValidationRule:
    hypothesisId: str
    conditionId: str
    description: str
    requiredColumns: list[str]
    noLookaheadNotes: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class HypothesisValidationMetrics:
    hypothesisId: str
    hypothesisName: str
    supportLevel: SupportLevel
    sampleCount: int
    conditionPassCount: int
    conditionPassRate: float
    validLabelCount: int
    primaryHorizon: int
    averageForwardReturn: float | None
    medianForwardReturn: float | None
    hitTpBeforeSlProbability: float | None
    hitSlBeforeTpProbability: float | None
    profitFactor: float | None
    expectancy: float | None
    averageMfe: float | None
    averageMae: float | None
    averageExcessReturnVsBTC: float | None
    perHorizon: dict[str, Any]
    monthlyStability: dict[str, Any]
    pairStability: dict[str, Any]
    regimeStability: dict[str, Any]
    liquidityStability: dict[str, Any]
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class HypothesisValidationReport:
    reportId: str
    version: str
    status: str
    config: HypothesisValidationConfig
    hypothesisCount: int
    validatedHypothesisCount: int
    rejectedHypothesisCount: int
    sampleCount: int
    factorPanelContext: dict[str, Any]
    noLookaheadAssurance: list[str]
    validationRules: list[dict[str, Any]]
    validationMetrics: list[dict[str, Any]]
    topSupportedHypotheses: list[str]
    unsupportedHypotheses: list[str]
    insufficientSampleHypotheses: list[str]
    hypothesesWithPositiveExcessVsBTC: list[str]
    stabilityWarnings: list[str]
    recommendations: list[dict[str, Any]]
    nextStep: str
    dryRunApproved: bool
    liveTradingApproved: bool
    warnings: list[str]
    generatedAt: str
    outputReportPath: str
    outputSummaryPath: str
    outputSamplePath: str
    outputRecommendationsPath: str
    source: str = "alphapilot_v13_4_26_hypothesis_validation"

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["config"] = self.config.to_dict()
        return payload
