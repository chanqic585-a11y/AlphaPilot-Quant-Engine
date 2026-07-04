"""Schema for V13.4.12 Dynamic Regime strategy specification reports."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class DynamicRegimeStrategySpecReport:
    reportId: str
    version: str
    strategyName: str
    strategyNameCn: str
    purpose: str
    currentStatus: str
    sourceDocuments: list[dict[str, Any]]
    architectureFlow: list[str]
    dynamicUniverse: dict[str, Any]
    historicalUniverseSnapshots: dict[str, Any]
    regimeRouter: dict[str, Any]
    trendModule: dict[str, Any]
    meanReversionModule: dict[str, Any]
    breakoutModule: dict[str, Any]
    probabilityScore: dict[str, Any]
    liquidityGateIntegration: dict[str, Any]
    riskGateIntegration: dict[str, Any]
    backtestPlan: dict[str, Any]
    roadmap: list[dict[str, Any]]
    doNotProceed: list[str]
    dryRunApproved: bool
    liveTradingApproved: bool
    nextStepRecommendation: str
    warnings: list[str] = field(default_factory=list)
    generatedAt: str = ""
    source: str = "alphapilot_v13_4_12_dynamic_regime_strategy_spec"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

