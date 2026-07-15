"""Immutable risk profile for strategy-validation Demo releases."""

from __future__ import annotations

from typing import Any, Mapping

from alphapilot.evolution.registry.hashing import stable_hash


DEFAULT_DEMO_RISK_PROFILE = {
    "schemaVersion": "strategy_validation_demo_risk_v1",
    "riskPerTradeR": 1.0,
    "maximumConcurrentPositions": 3,
    "maximumOpenRiskR": 3.0,
    "maximumSingleSymbolRiskR": 1.0,
    "maximumCorrelatedClusterRiskR": 2.0,
    "maximumDailyLossR": 3.0,
    "maximumWeeklyLossR": 6.0,
    "maximumConsecutiveLosses": 4,
    "maximumDemoDrawdownPct": 12.0,
    "minimumTargetR": 2.0,
    "stopWideningAllowed": False,
    "addingToLossAllowed": False,
    "martingaleAllowed": False,
    "automaticParameterChangeAllowed": False,
    "environment": "demo",
}


def _content(profile: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in profile.items() if key != "riskConfigHash"}


def validate_demo_risk_profile(profile: Mapping[str, Any]) -> str:
    content = _content(profile)
    if content.get("environment") != "demo":
        raise ValueError("strategy-validation risk profile must target demo")
    if float(content.get("minimumTargetR") or 0) < 2.0:
        raise ValueError("minimumTargetR must remain at least 2R")
    for key in ("riskPerTradeR", "maximumOpenRiskR", "maximumSingleSymbolRiskR", "maximumCorrelatedClusterRiskR", "maximumDailyLossR", "maximumWeeklyLossR"):
        if float(content.get(key) or 0) <= 0:
            raise ValueError(f"{key} must be positive")
    if int(content.get("maximumConcurrentPositions") or 0) <= 0:
        raise ValueError("maximumConcurrentPositions must be positive")
    for key in ("stopWideningAllowed", "addingToLossAllowed", "martingaleAllowed", "automaticParameterChangeAllowed"):
        if content.get(key) is not False:
            raise ValueError(f"{key} must remain false")
    expected = stable_hash(content, prefix="demo_risk")
    supplied = profile.get("riskConfigHash")
    if supplied is not None and supplied != expected:
        raise ValueError("riskConfigHash mismatch")
    return expected


def build_demo_risk_profile(**overrides: Any) -> dict[str, Any]:
    profile = {**DEFAULT_DEMO_RISK_PROFILE, **overrides}
    profile["riskConfigHash"] = stable_hash(profile, prefix="demo_risk")
    validate_demo_risk_profile(profile)
    return profile
