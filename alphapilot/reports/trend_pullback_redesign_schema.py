"""Schema for V13.4.10 Trend Pullback redesign review reports."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class TrendPullbackRedesignReviewReport:
    reportId: str
    version: str
    strategyId: str
    sourceReports: list[dict[str, Any]]
    currentStatus: str
    dryRunApproved: bool
    smokeVsExpanded: dict[str, Any]
    pairConcentration: dict[str, Any]
    monthlyBreakdown: dict[str, Any]
    costSensitivity: dict[str, Any]
    payoffReview: dict[str, Any]
    filterReview: dict[str, Any]
    strategyFamilyDecision: dict[str, Any]
    failureFindings: list[str]
    redesignOptions: list[dict[str, Any]]
    recommendedNextStep: str
    doNotProceed: list[str]
    warnings: list[str] = field(default_factory=list)
    generatedAt: str = ""
    source: str = "alphapilot_v13_4_10_trend_pullback_redesign_review"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

