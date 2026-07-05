"""Low-frequency mainstream coin research plan schema.

This module defines research specifications only. It does not implement a
Freqtrade strategy, run a backtest, download data, enter Dry-run, call exchange
APIs, read accounts, create orders, or auto trade.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class LowFrequencyHypothesis:
    hypothesisId: str
    name: str
    thesis: str
    direction: str
    primaryTimeframe: str
    informativeTimeframes: list[str]
    coreConditions: list[str]
    regimeUse: str
    validationFocus: list[str]
    firstVersionConditionLimit: str = "4-6 core conditions"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LowFrequencyResearchPlan:
    planId: str
    currentStatus: str
    scope: dict[str, Any]
    principles: list[str]
    hypotheses: list[LowFrequencyHypothesis]
    longShortFramework: dict[str, Any]
    minimalConditionsPhilosophy: dict[str, Any]
    benchmarkRequirements: list[str]
    evaluationMetrics: list[str]
    dataRequirements: list[str]
    optionalFutureData: list[str]
    nextStepRecommendation: str
    dryRunApproved: bool = False
    liveTradingApproved: bool = False
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["hypotheses"] = [item.to_dict() for item in self.hypotheses]
        return payload
