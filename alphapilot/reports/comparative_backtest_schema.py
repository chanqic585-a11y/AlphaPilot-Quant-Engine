"""Schema for V13.4.4 comparative backtest reports."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ComparativeCandidateResult:
    strategy: str
    candidateId: str | None
    isExecutable: bool
    backtestReport: str | None
    metrics: dict[str, Any]
    deltaVsBaseline: dict[str, Any]
    passedComparisonGate: bool
    warnings: list[str] = field(default_factory=list)


@dataclass
class ComparativeBacktestReport:
    reportId: str
    timerange: str
    pairs: list[str]
    baselineStrategy: str
    baselineMetrics: dict[str, Any]
    candidateResults: list[ComparativeCandidateResult]
    comparisonTable: list[dict[str, Any]]
    ranking: list[dict[str, Any]]
    bestCandidate: str | None
    dryRunApproved: bool
    reasons: list[str]
    warnings: list[str]
    slippageApplied: bool
    nextStepRecommendation: str
    generatedAt: str
    source: str = "alphapilot_v13_4_4_comparative_backtest"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

