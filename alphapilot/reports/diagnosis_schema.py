"""AlphaPilot V13.4.1 backtest diagnosis schema."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class BacktestDiagnosisReport:
    reportId: str
    sourceReport: str
    sourceResult: str | None
    isMock: bool
    strategyId: str
    timerange: str
    pairs: list[str]
    overall: dict[str, Any]
    pairBreakdown: list[dict[str, Any]]
    monthlyBreakdown: list[dict[str, Any]]
    exitReasonBreakdown: list[dict[str, Any]]
    holdingTimeBreakdown: list[dict[str, Any]]
    costAnalysis: dict[str, Any]
    consecutiveLossAnalysis: dict[str, Any]
    filterEffectiveness: dict[str, Any]
    tradeQualityReview: dict[str, Any]
    diagnosisFindings: list[dict[str, Any]]
    hypotheses: list[dict[str, Any]]
    v02CandidateIdeas: list[dict[str, Any]]
    doNotChangeYet: list[str]
    warnings: list[str]
    generatedAt: str
    source: str = "alphapilot_v13_4_1_backtest_diagnosis"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
