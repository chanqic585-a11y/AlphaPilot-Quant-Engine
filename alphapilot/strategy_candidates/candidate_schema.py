"""Schema objects for strategy candidate design reports."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class StrategyCandidate:
    candidateId: str
    name: str
    description: str
    status: str
    evidence: list[dict[str, Any]]
    proposedChanges: list[str]
    expectedImpact: list[str]
    risks: list[str]
    whatToTest: list[str]
    doNotAssume: list[str]


@dataclass
class CandidateMatrixReport:
    reportId: str
    sourceDiagnosis: str
    sourceSignalAudit: str
    strategyId: str
    currentStatus: dict[str, Any]
    evidenceSummary: dict[str, Any]
    candidates: list[StrategyCandidate]
    recommendedComparisonPlan: list[dict[str, Any]]
    doNotChangeYet: list[str]
    warnings: list[str] = field(default_factory=list)
    generatedAt: str = ""
    source: str = "alphapilot_v13_4_3_candidate_design"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

