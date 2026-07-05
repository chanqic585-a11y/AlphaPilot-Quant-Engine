"""Schemas for V13.4.30 Short Rejection failure review.

The review is report-only. It reads V13.4.29 local research outputs and does
not run backtests, enter Dry-run, call exchange APIs, or create orders.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class ShortFailureReviewReport:
    reportId: str
    sourceShortReport: str
    strategyId: str
    strategyName: str
    currentStatus: str
    dryRunApproved: bool
    liveTradingApproved: bool
    researchWorthContinuing: bool
    overallFailure: dict[str, Any]
    tradeFrequencyReview: dict[str, Any]
    payoffReview: dict[str, Any]
    shortSqueezeRiskReview: dict[str, Any]
    pairMonthReview: dict[str, Any]
    exitReasonReview: dict[str, Any]
    costReview: dict[str, Any]
    negativeResearchRules: list[dict[str, Any]]
    futureShortResearchRecommendations: list[str]
    nextStepRecommendation: str
    warnings: list[str]
    generatedAt: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ShortStrategyStatusArchive:
    strategyId: str
    strategyName: str
    status: str
    dryRunApproved: bool
    liveTradingApproved: bool
    researchWorthContinuing: bool
    reason: str
    evidenceReports: list[str]
    archiveMode: str
    canBeUsedAsBenchmark: bool
    canBeRevivedIf: list[str]
    generatedAt: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class NegativeResearchRulesPayload:
    reportId: str
    sourceShortReport: str
    strategyId: str
    rules: list[dict[str, Any]]
    futureRequirements: list[str]
    generatedAt: str
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
