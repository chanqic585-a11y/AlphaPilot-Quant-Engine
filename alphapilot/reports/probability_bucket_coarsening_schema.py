"""Schema for V13.4.19 probability bucket coarsening reports."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ProbabilityBucketCoarseningReport:
    reportId: str
    sourceProbabilityTable: str
    sourceDiagnosis: str
    currentGateSummary: dict[str, Any]
    researchGateSummary: dict[str, Any]
    exploratoryGateSummary: dict[str, Any]
    coarseningSchemes: list[dict[str, Any]]
    rootCauseConclusion: str
    rootCauseEvidence: list[str]
    recommendedNextStep: str
    dryRunApproved: bool
    liveTradingApproved: bool
    warnings: list[str] = field(default_factory=list)
    generatedAt: str = ""
    source: str = "alphapilot_v13_4_19_probability_bucket_coarsening"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
