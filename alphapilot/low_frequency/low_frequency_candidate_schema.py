"""Schemas for V13.4.33 low-frequency candidate specifications."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class LowFrequencyCandidateSpec:
    candidateId: str
    name: str
    direction: str
    timeframe: str
    pairs: list[str]
    coreConditions: list[str]
    exitConcept: dict[str, Any]
    riskConcept: dict[str, Any]
    baselineHurdles: dict[str, Any]
    expectedStrength: list[str]
    knownRisk: list[str]
    validationPlan: list[str]
    invalidationRules: list[str]
    status: str = "spec_only"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LowFrequencyCandidateSpecReport:
    reportId: str
    version: str
    sourceBaselineReport: str
    sourceDataReport: str
    sourceResearchPlan: str
    currentStatus: str
    dryRunApproved: bool
    liveTradingApproved: bool
    scope: dict[str, Any]
    baselineHurdles: dict[str, Any]
    candidates: list[LowFrequencyCandidateSpec]
    directionalScoreFramework: dict[str, Any]
    v13_4_34Plan: dict[str, Any]
    safetyBoundary: dict[str, bool]
    generatedAt: str
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["candidates"] = [item.to_dict() for item in self.candidates]
        return payload
