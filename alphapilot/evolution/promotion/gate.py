"""Hard, evidence-bound gates for automatic promotion into OKX Demo only."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class FrequencyThresholds:
    lockedOosClosedSamples: int
    shadowClosedSamples: int
    shadowCalendarDays: int


FREQUENCY_THRESHOLDS = {
    "short_cycle": FrequencyThresholds(200, 50, 14),
    "medium_cycle": FrequencyThresholds(120, 30, 30),
    "low_frequency": FrequencyThresholds(60, 20, 60),
}


@dataclass(frozen=True)
class PromotionEvidence:
    frequency: str
    pointInTimePassed: bool
    leakageCheckPassed: bool
    fdrPassed: bool
    deflatedSharpePassed: bool
    pboPassed: bool
    validWalkForwardFolds: int
    lockedOosProfitFactor: float
    doubledCostProfitFactor: float
    maxDrawdownPercent: float
    realizedRewardRisk: float
    largestSymbolShare: float
    largestMonthShare: float
    largestRegimeShare: float
    lockedOosClosedSamples: int
    shadowClosedSamples: int
    shadowCalendarDays: int
    shadowPublicMarketDriven: bool
    inputsFrozen: bool
    checksumsMatch: bool


@dataclass(frozen=True)
class GateCheck:
    checkId: str
    passed: bool
    actual: Any
    required: Any


@dataclass(frozen=True)
class PromotionGateResult:
    passed: bool
    sourceStatus: str
    targetStatus: str
    checks: tuple[GateCheck, ...]
    evidence: PromotionEvidence

    @property
    def failedCheckIds(self) -> tuple[str, ...]:
        return tuple(check.checkId for check in self.checks if not check.passed)

    def as_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "sourceStatus": self.sourceStatus,
            "targetStatus": self.targetStatus,
            "failedCheckIds": list(self.failedCheckIds),
            "checks": [asdict(check) for check in self.checks],
            "evidence": asdict(self.evidence),
        }


def _finite(value: float) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def evaluate_demo_promotion(evidence: PromotionEvidence) -> PromotionGateResult:
    thresholds = FREQUENCY_THRESHOLDS.get(evidence.frequency)
    if thresholds is None:
        raise ValueError(f"Unsupported strategy frequency: {evidence.frequency}")
    numeric_values = (
        evidence.lockedOosProfitFactor,
        evidence.doubledCostProfitFactor,
        evidence.maxDrawdownPercent,
        evidence.realizedRewardRisk,
        evidence.largestSymbolShare,
        evidence.largestMonthShare,
        evidence.largestRegimeShare,
    )
    if not all(_finite(value) for value in numeric_values):
        raise ValueError("Promotion evidence contains non-finite metrics")
    if min(
        evidence.validWalkForwardFolds,
        evidence.lockedOosClosedSamples,
        evidence.shadowClosedSamples,
        evidence.shadowCalendarDays,
    ) < 0:
        raise ValueError("Promotion evidence sample counts cannot be negative")

    checks = (
        GateCheck("point_in_time", evidence.pointInTimePassed, evidence.pointInTimePassed, True),
        GateCheck("leakage", evidence.leakageCheckPassed, evidence.leakageCheckPassed, True),
        GateCheck("fdr", evidence.fdrPassed, evidence.fdrPassed, True),
        GateCheck("deflated_sharpe", evidence.deflatedSharpePassed, evidence.deflatedSharpePassed, True),
        GateCheck("pbo", evidence.pboPassed, evidence.pboPassed, True),
        GateCheck("walk_forward_folds", evidence.validWalkForwardFolds >= 3, evidence.validWalkForwardFolds, 3),
        GateCheck("locked_oos_profit_factor", evidence.lockedOosProfitFactor >= 1.25, evidence.lockedOosProfitFactor, 1.25),
        GateCheck("doubled_cost_profit_factor", evidence.doubledCostProfitFactor >= 1.05, evidence.doubledCostProfitFactor, 1.05),
        GateCheck("max_drawdown", 0 <= evidence.maxDrawdownPercent <= 20.0, evidence.maxDrawdownPercent, "0..20"),
        GateCheck("reward_risk", evidence.realizedRewardRisk >= 2.0, evidence.realizedRewardRisk, 2.0),
        GateCheck("symbol_concentration", 0 <= evidence.largestSymbolShare <= 0.25, evidence.largestSymbolShare, 0.25),
        GateCheck("month_concentration", 0 <= evidence.largestMonthShare <= 0.20, evidence.largestMonthShare, 0.20),
        GateCheck("regime_concentration", 0 <= evidence.largestRegimeShare <= 0.60, evidence.largestRegimeShare, 0.60),
        GateCheck("locked_oos_closed_samples", evidence.lockedOosClosedSamples >= thresholds.lockedOosClosedSamples, evidence.lockedOosClosedSamples, thresholds.lockedOosClosedSamples),
        GateCheck("shadow_closed_samples", evidence.shadowClosedSamples >= thresholds.shadowClosedSamples, evidence.shadowClosedSamples, thresholds.shadowClosedSamples),
        GateCheck("shadow_calendar_days", evidence.shadowCalendarDays >= thresholds.shadowCalendarDays, evidence.shadowCalendarDays, thresholds.shadowCalendarDays),
        GateCheck("shadow_public_market", evidence.shadowPublicMarketDriven, evidence.shadowPublicMarketDriven, True),
        GateCheck("inputs_frozen", evidence.inputsFrozen, evidence.inputsFrozen, True),
        GateCheck("checksums", evidence.checksumsMatch, evidence.checksumsMatch, True),
    )
    passed = all(check.passed for check in checks)
    return PromotionGateResult(
        passed=passed,
        sourceStatus="shadow_observation",
        targetStatus="demo_eligible" if passed else "shadow_observation",
        checks=checks,
        evidence=evidence,
    )
