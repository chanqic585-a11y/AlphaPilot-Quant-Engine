"""Compare offline models without automatically replacing a Demo champion."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ChampionChallengerDecision:
    championModelId: str
    challengerModelId: str
    approvedForShadow: bool
    requestedStatus: str
    checks: dict[str, bool]
    reasons: list[str]
    autoReplacesDemo: bool = False
    createsOrders: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "championModelId": self.championModelId,
            "challengerModelId": self.challengerModelId,
            "approvedForShadow": self.approvedForShadow,
            "requestedStatus": self.requestedStatus,
            "checks": self.checks,
            "reasons": self.reasons,
            "autoReplacesDemo": self.autoReplacesDemo,
            "createsOrders": self.createsOrders,
        }


def compare_champion_challenger(
    *,
    champion_model_id: str,
    challenger_model_id: str,
    champion_metrics: dict[str, Any],
    challenger_metrics: dict[str, Any],
    minimum_relative_improvement: float = 0.03,
    minimum_folds: int = 3,
) -> ChampionChallengerDecision:
    if not 0 <= minimum_relative_improvement < 1 or minimum_folds <= 0:
        raise ValueError("Invalid champion/challenger thresholds")
    required_numeric = [
        champion_metrics.get("logLoss"),
        champion_metrics.get("brierScore"),
        challenger_metrics.get("logLoss"),
        challenger_metrics.get("brierScore"),
    ]
    if any(value is None or not math.isfinite(float(value)) for value in required_numeric):
        raise ValueError("Champion and challenger require finite logLoss and brierScore")
    log_loss_target = float(champion_metrics["logLoss"]) * (1 - minimum_relative_improvement)
    brier_target = float(champion_metrics["brierScore"]) * (1 - minimum_relative_improvement)
    checks = {
        "log_loss_improved": float(challenger_metrics["logLoss"]) <= log_loss_target,
        "brier_improved": float(challenger_metrics["brierScore"]) <= brier_target,
        "minimum_walk_forward_folds": int(challenger_metrics.get("foldCount") or 0) >= minimum_folds,
        "cost_stress_passed": bool(challenger_metrics.get("costStressPassed")),
        "stability_passed": bool(challenger_metrics.get("stabilityPassed")),
        "calibration_passed": bool(challenger_metrics.get("calibrationPassed")),
    }
    reasons = [name for name, passed in checks.items() if not passed]
    approved = all(checks.values())
    return ChampionChallengerDecision(
        championModelId=champion_model_id,
        challengerModelId=challenger_model_id,
        approvedForShadow=approved,
        requestedStatus="shadow_approved" if approved else "rejected",
        checks=checks,
        reasons=reasons,
    )
