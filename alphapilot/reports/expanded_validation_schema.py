"""Schema for V13.4.5 expanded validation reports."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ExpandedValidationResult:
    strategy: str
    backtestReport: str | None
    backtestSucceeded: bool
    rawMetrics: dict[str, Any]
    slippageAdjustedMetrics: dict[str, Any]
    deltaVsBaseline: dict[str, Any]
    pairBreakdown: list[dict[str, Any]]
    monthlyBreakdown: list[dict[str, Any]]
    passedExpandedGate: bool
    warnings: list[str] = field(default_factory=list)


@dataclass
class ExpandedValidationReport:
    reportId: str
    scope: dict[str, Any]
    strategies: list[str]
    baselineStrategy: str
    baseline: dict[str, Any]
    results: list[ExpandedValidationResult]
    rawComparisonTable: list[dict[str, Any]]
    slippageAdjustedComparisonTable: list[dict[str, Any]]
    supportedPairs: list[str]
    excludedPairs: list[dict[str, Any]]
    warnings: list[str]
    bestRawCandidate: str | None
    bestSlippageAdjustedCandidate: str | None
    dryRunApproved: bool
    reasons: list[str]
    nextStepRecommendation: str
    generatedAt: str
    source: str = "alphapilot_v13_4_5_expanded_validation"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
