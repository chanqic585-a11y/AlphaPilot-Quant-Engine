"""Typed public gate schema for V13.27.1.11 research decisions."""

from __future__ import annotations

from typing import Any, Mapping


PUBLIC_GATE_FIELDS = (
    "developmentPrefilterPassed",
    "walkForwardNumericPassed",
    "simpleBenchmarkPassed",
    "uncertaintyPassed",
    "capitalCompetitionPassed",
    "implementationParityPassed",
    "formalDataProvenancePassed",
    "cleanHoldoutPassed",
    "overallBasicPassed",
    "overallFormalPassed",
)

EXECUTION_FACT_FIELDS = (
    "eventReplayExecuted",
    "freqtradeBacktestExecuted",
    "portfolioBacktestExecuted",
    "translationParityPassed",
)


def require_metric_type(
    metrics: Mapping[str, Any] | None,
    expected: str,
    evidence_name: str,
) -> dict[str, Any] | None:
    if metrics is None:
        return None
    if metrics.get("metricType") != expected:
        raise TypeError(f"{evidence_name} must use {expected} metrics")
    return dict(metrics)


def public_gate_projection(values: Mapping[str, Any]) -> dict[str, bool]:
    missing = [field for field in PUBLIC_GATE_FIELDS if field not in values]
    if missing:
        raise ValueError(f"missing public gate fields: {', '.join(missing)}")
    return {field: bool(values[field]) for field in PUBLIC_GATE_FIELDS}
