"""Schema for V13.4.18 Dynamic Regime pipeline diagnosis reports."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class DynamicRegimePipelineDiagnosisReport:
    reportId: str
    sourceExpandedReport: str
    sourceProbabilityTable: str
    currentStatus: str
    dryRunApproved: bool
    liveTradingApproved: bool
    signalFunnel: dict[str, Any]
    probabilityGateDiagnosis: dict[str, Any]
    bucketKeyConsistency: dict[str, Any]
    regimeRouterDiagnosis: dict[str, Any]
    moduleCandidateDiagnosis: dict[str, Any]
    liquidityGateDiagnosis: dict[str, Any]
    rootCauseHypotheses: list[dict[str, Any]]
    recommendedNextStep: dict[str, Any]
    warnings: list[str] = field(default_factory=list)
    generatedAt: str = ""
    source: str = "alphapilot_v13_4_18_dynamic_regime_pipeline_diagnosis"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
