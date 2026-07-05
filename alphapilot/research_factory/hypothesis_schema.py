"""Research hypothesis schema for the Strategy Research Factory.

These objects describe research candidates only. They are not trading
strategies, Freqtrade strategies, Dry-run approvals, orders, or advice.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

HypothesisCategory = Literal[
    "factor_based",
    "benchmark_informed",
    "regime_based",
    "execution_reality",
    "rejected",
]
HypothesisStatus = Literal["research_only", "rejected", "deferred"]
HypothesisPriority = Literal["high", "medium", "low"]


@dataclass(frozen=True)
class ResearchHypothesis:
    hypothesisId: str
    name: str
    category: HypothesisCategory
    status: HypothesisStatus
    evidence: list[dict[str, Any]]
    sourceReports: list[str]
    proposedMechanism: str
    expectedBehavior: str
    riskNotes: list[str]
    requiredData: list[str]
    validationPlan: list[str]
    invalidationRules: list[str]
    priority: HypothesisPriority
    dryRunApproved: bool = False
    liveTradingApproved: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class HypothesisMiningResult:
    reportId: str
    version: str
    status: str
    inputReportSummaries: dict[str, Any]
    hypotheses: list[ResearchHypothesis]
    warnings: list[str] = field(default_factory=list)
    dryRunApproved: bool = False
    liveTradingApproved: bool = False

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["hypotheses"] = [item.to_dict() for item in self.hypotheses]
        return payload
