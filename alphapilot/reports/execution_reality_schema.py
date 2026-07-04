"""Schema for V13.4.11 execution reality design reports."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ExecutionRealityDesignReport:
    reportId: str
    version: str
    purpose: str
    modules: list[dict[str, Any]]
    liquidityGate: dict[str, Any]
    slippageStressTest: dict[str, Any]
    orderImpactModel: dict[str, Any]
    shadowTrading: dict[str, Any]
    liveFeasibilityScore: dict[str, Any]
    proposalIntegration: dict[str, Any]
    riskGateIntegration: dict[str, Any]
    dryRunApproved: bool
    liveTradingApproved: bool
    nextStepRecommendation: str
    warnings: list[str] = field(default_factory=list)
    generatedAt: str = ""
    source: str = "alphapilot_v13_4_11_execution_reality_design"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

