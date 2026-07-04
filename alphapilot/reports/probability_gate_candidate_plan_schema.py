"""Schema for V13.4.20 probability gate candidate plan reports."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ProbabilityGateCandidatePlanReport:
    reportId: str
    sourceCoarseningReport: str
    currentGateStatus: dict[str, Any]
    candidateGates: list[dict[str, Any]]
    rejectedBuckets: list[dict[str, Any]]
    backtestPlan: dict[str, Any]
    safetyBoundary: dict[str, Any]
    recommendedNextStep: str
    warnings: list[str] = field(default_factory=list)
    generatedAt: str = ""
    source: str = "alphapilot_v13_4_20_probability_gate_candidate_plan"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
