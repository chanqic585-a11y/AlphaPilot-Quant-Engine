"""Bounded, split-safe policy for immutable strategy challengers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from alphapilot.evolution.registry.hashing import stable_hash


MAX_AUTOMATIC_ATTEMPTS = 3
TERMINAL_STATUSES = {
    "passed",
    "budget_exhausted",
    "structural_redesign_required",
    "data_evidence_blocked",
    "formal_validation_failed",
}
_SELECTION_SPLITS = ("development", "walk_forward")
_SELECTION_METRIC_KEYS = {
    "tradeCount",
    "profitFactor",
    "averageNetR",
    "averageGrossR",
    "maximumDrawdownR",
    "winRate",
    "ambiguousPathCount",
    "partialTargetCount",
}
_STRESS_METRIC_KEYS = {"tradeCount", "averageNetR", "missingPathCount"}


@dataclass(frozen=True)
class OptimizationInput:
    rootStrategyVersionId: str
    currentStrategyVersionId: str
    displayName: str
    definition: dict[str, Any]
    parameters: dict[str, Any]
    metrics: dict[str, Any]
    gateRules: dict[str, Any]
    failureCategory: str | None
    runStatus: str
    completedAttempts: int
    activeChallengerExists: bool


@dataclass(frozen=True)
class OptimizationDecision:
    action: str
    reasonCode: str
    terminalStatus: str | None
    campaignId: str
    rootStrategyVersionId: str
    currentStrategyVersionId: str
    attemptNumber: int
    maxAttempts: int
    changedParameter: dict[str, Any] | None
    proposedDefinition: dict[str, Any] | None
    proposedParameters: dict[str, Any] | None
    selectionMetrics: dict[str, Any]


@dataclass(frozen=True)
class _MutationStep:
    name: str
    delta: float
    minimum: float
    maximum: float
    integer: bool = False


_FAMILY_STEPS: dict[str, tuple[_MutationStep, ...]] = {
    "breakout_volume_long": (
        _MutationStep("volume_min", 0.2, 0.8, 3.0),
        _MutationStep("breakout_buffer", 0.0005, 0.0, 0.01),
        _MutationStep("rsi_max", -3, 45, 85, True),
    ),
    "ema_reclaim_long": (
        _MutationStep("volume_min", 0.2, 0.8, 3.0),
        _MutationStep("rsi_min", 2, 25, 65, True),
        _MutationStep("reclaim_buffer", -0.0005, 0.0, 0.01),
    ),
    "mean_reversion_reclaim_long": (
        _MutationStep("rsi_low", -2, 15, 40, True),
        _MutationStep("volume_min", 0.2, 0.8, 3.0),
        _MutationStep("max_range_pct", -0.003, 0.01, 0.08),
    ),
    "short_breakdown_momentum": (
        _MutationStep("volume_min", 0.2, 0.8, 3.0),
        _MutationStep("breakdown_buffer", 0.0005, 0.0, 0.01),
        _MutationStep("rsi_max", -3, 30, 70, True),
    ),
    "short_rejection": (
        _MutationStep("rsi_high", 3, 45, 85, True),
        _MutationStep("volume_min", 0.2, 0.8, 3.0),
        _MutationStep("upper_buffer", 0.001, 0.001, 0.02),
    ),
    "momentum_continuation_long": (
        _MutationStep("volume_min", 0.2, 0.8, 3.0),
        _MutationStep("rsi_min", 2, 25, 65, True),
        _MutationStep("macd_tolerance", 0.05, 0.5, 1.2),
    ),
    "squeeze_breakout_long": (
        _MutationStep("volume_min", 0.2, 0.8, 3.0),
        _MutationStep("squeeze_ratio", -0.05, 0.4, 1.0),
        _MutationStep("lookback", 8, 12, 96, True),
    ),
    "windowed_breakout_retest_long": (
        _MutationStep("breakout_volume_min", 0.15, 0.8, 3.0),
        _MutationStep("confirmation_volume_min", 0.1, 0.6, 2.5),
        _MutationStep("reclaim_buffer", 0.0002, 0.0, 0.01),
    ),
    "windowed_failed_breakout_short": (
        _MutationStep("volume_min", 0.15, 0.8, 3.0),
        _MutationStep("rsi_high", 2, 45, 85, True),
        _MutationStep("rejection_buffer", 0.0002, 0.0, 0.01),
    ),
    "windowed_failed_reclaim_short": (
        _MutationStep("volume_min", 0.15, 0.8, 3.0),
        _MutationStep("rsi_max", -2, 35, 75, True),
        _MutationStep("rejection_buffer", 0.0002, 0.0, 0.01),
    ),
    "windowed_liquidity_sweep_reclaim_long": (
        _MutationStep("volume_min", 0.15, 0.8, 3.0),
        _MutationStep("rsi_oversold", -2, 15, 40, True),
        _MutationStep("reclaim_buffer", 0.0002, 0.0, 0.01),
    ),
    "windowed_recovery_reclaim_long": (
        _MutationStep("volume_min", 0.15, 0.8, 3.0),
        _MutationStep("rsi_min", 2, 25, 65, True),
        _MutationStep("trend_floor", 0.002, 0.9, 1.1),
    ),
    "windowed_squeeze_breakout_long": (
        _MutationStep("volume_min", 0.15, 0.8, 3.0),
        _MutationStep("squeeze_ratio", -0.03, 0.4, 1.0),
        _MutationStep("breakout_buffer", 0.0002, 0.0, 0.01),
    ),
    "windowed_trend_reclaim_long": (
        _MutationStep("volume_min", 0.15, 0.8, 3.0),
        _MutationStep("rsi_min", 2, 25, 65, True),
        _MutationStep("reclaim_buffer", 0.0002, 0.0, 0.01),
    ),
}


def _number(value: Any, fallback: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return fallback
    return parsed if parsed == parsed else fallback


def _bounded_payload(value: Any, keys: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return {key: value[key] for key in sorted(keys) if key in value}


def sanitize_selection_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    """Return the only metric view permitted to influence parameter changes."""

    by_split = metrics.get("bySplit") if isinstance(metrics, dict) else None
    stress = metrics.get("costStress") if isinstance(metrics, dict) else None
    stress_by_split = stress.get("bySplit") if isinstance(stress, dict) else None
    return {
        "bySplit": {
            split: _bounded_payload(
                by_split.get(split) if isinstance(by_split, dict) else None,
                _SELECTION_METRIC_KEYS,
            )
            for split in _SELECTION_SPLITS
        },
        "costStress": {
            "bySplit": {
                split: _bounded_payload(
                    (
                        stress_by_split.get(split)
                        if isinstance(stress_by_split, dict)
                        else None
                    ),
                    _STRESS_METRIC_KEYS,
                )
                for split in _SELECTION_SPLITS
            }
        },
    }


def _selection_metrics_available(metrics: dict[str, Any]) -> bool:
    splits = metrics.get("bySplit") if isinstance(metrics, dict) else None
    return isinstance(splits, dict) and all(
        isinstance(splits.get(split), dict) and bool(splits[split])
        for split in _SELECTION_SPLITS
    )


def evaluate_selection_gate(
    metrics: dict[str, Any],
    *,
    gate_rules: dict[str, Any],
    target_r: float,
) -> dict[str, bool]:
    """Evaluate development and walk-forward evidence without locked feedback."""

    splits = metrics.get("bySplit") if isinstance(metrics, dict) else {}
    selected = [
        splits.get(split) if isinstance(splits, dict) else {}
        for split in _SELECTION_SPLITS
    ]
    stress_root = metrics.get("costStress") if isinstance(metrics, dict) else {}
    stress_splits = (
        stress_root.get("bySplit") if isinstance(stress_root, dict) else {}
    )
    selected_stress = [
        stress_splits.get(split) if isinstance(stress_splits, dict) else {}
        for split in _SELECTION_SPLITS
    ]
    minimum_trades = _number(gate_rules.get("minimumTradeCount"), 30.0)
    minimum_pf = _number(gate_rules.get("minimumProfitFactor"), 1.1)
    minimum_net_r = _number(gate_rules.get("minimumAverageNetR"), 0.0)
    maximum_drawdown = _number(gate_rules.get("maximumDrawdownR"), 20.0)
    requires_stress = bool(gate_rules.get("requiresCostStress"))
    return {
        "selectionMinimumTargetR": target_r
        >= _number(gate_rules.get("minimumTargetR"), 2.0),
        "selectionMinimumTradeCount": sum(
            _number(item.get("tradeCount"), -1.0) for item in selected
        )
        >= minimum_trades
        and all(_number(item.get("tradeCount"), 0.0) > 0 for item in selected),
        "selectionMinimumProfitFactor": all(
            _number(item.get("profitFactor"), -1.0) >= minimum_pf
            for item in selected
        ),
        "selectionPositiveAverageNetR": all(
            _number(item.get("averageNetR"), -1.0) >= minimum_net_r
            for item in selected
        ),
        "selectionMaximumDrawdown": all(
            _number(item.get("maximumDrawdownR"), float("inf"))
            <= maximum_drawdown
            for item in selected
        ),
        "selectionCostStress": (not requires_stress)
        or all(
            _number(item.get("tradeCount"), 0.0) > 0
            and _number(item.get("averageNetR"), -1.0) > 0
            for item in selected_stress
        ),
    }


def _decision(
    value: OptimizationInput,
    *,
    action: str,
    reason_code: str,
    terminal_status: str | None = None,
    attempt_number: int | None = None,
    changed_parameter: dict[str, Any] | None = None,
    proposed_definition: dict[str, Any] | None = None,
    proposed_parameters: dict[str, Any] | None = None,
    selection_metrics: dict[str, Any] | None = None,
) -> OptimizationDecision:
    campaign_id = stable_hash(
        {
            "rootStrategyVersionId": value.rootStrategyVersionId,
            "maxAttempts": MAX_AUTOMATIC_ATTEMPTS,
        },
        prefix="optimization_campaign",
    )
    return OptimizationDecision(
        action=action,
        reasonCode=reason_code,
        terminalStatus=terminal_status,
        campaignId=campaign_id,
        rootStrategyVersionId=value.rootStrategyVersionId,
        currentStrategyVersionId=value.currentStrategyVersionId,
        attemptNumber=(
            value.completedAttempts + 1
            if attempt_number is None
            else attempt_number
        ),
        maxAttempts=MAX_AUTOMATIC_ATTEMPTS,
        changedParameter=changed_parameter,
        proposedDefinition=proposed_definition,
        proposedParameters=proposed_parameters,
        selectionMetrics=selection_metrics or {},
    )


def _next_mutation(
    family: str,
    parameters: dict[str, Any],
    attempt_index: int,
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    steps = _FAMILY_STEPS.get(family)
    if not steps:
        return None
    ordered = steps[attempt_index:] + steps[:attempt_index]
    for step in ordered:
        if step.name not in parameters:
            continue
        before = _number(parameters[step.name], float("nan"))
        if before != before:
            continue
        after = min(step.maximum, max(step.minimum, before + step.delta))
        if step.integer:
            after = int(round(after))
        else:
            after = round(after, 8)
        if after == before:
            continue
        proposed = dict(parameters)
        proposed[step.name] = after
        return proposed, {"name": step.name, "before": before, "after": after}
    return None


def decide_bounded_optimization(value: OptimizationInput) -> OptimizationDecision:
    target_r = _number(value.definition.get("targetR"), 0.0)
    lineage = value.definition.get("optimizationLineage")
    lineage = lineage if isinstance(lineage, dict) else {}
    phase = str(lineage.get("phase") or "root")
    sanitized = sanitize_selection_metrics(value.metrics)

    if value.activeChallengerExists:
        return _decision(
            value,
            action="wait",
            reason_code="active_challenger_exists",
            attempt_number=max(value.completedAttempts, 0),
            selection_metrics=sanitized,
        )
    if target_r < 2.0:
        return _decision(
            value,
            action="stop",
            reason_code="minimum_target_r_violation",
            terminal_status="data_evidence_blocked",
            selection_metrics=sanitized,
        )
    if value.runStatus == "passed":
        if phase == "selection":
            final_definition = dict(value.definition)
            final_definition["optimizationLineage"] = {
                **lineage,
                "phase": "formal_validation",
                "formalValidationConsumed": True,
                "selectionMetricsHash": stable_hash(sanitized),
            }
            return _decision(
                value,
                action="create_formal_validation",
                reason_code="selection_gate_passed",
                attempt_number=int(
                    lineage.get("attemptNumber") or value.completedAttempts or 1
                ),
                proposed_definition=final_definition,
                proposed_parameters=dict(value.parameters),
                selection_metrics=sanitized,
            )
        return _decision(
            value,
            action="stop",
            reason_code="formal_gate_passed",
            terminal_status="passed",
            attempt_number=value.completedAttempts,
            selection_metrics=sanitized,
        )
    if phase == "formal_validation":
        return _decision(
            value,
            action="stop",
            reason_code="one_shot_formal_validation_failed",
            terminal_status="formal_validation_failed",
            attempt_number=int(lineage.get("attemptNumber") or value.completedAttempts),
            selection_metrics=sanitized,
        )
    if value.failureCategory != "strategy_performance":
        return _decision(
            value,
            action="stop",
            reason_code="non_performance_failure",
            terminal_status="data_evidence_blocked",
            selection_metrics=sanitized,
        )
    if not _selection_metrics_available(sanitized):
        return _decision(
            value,
            action="stop",
            reason_code="selection_metrics_missing",
            terminal_status="data_evidence_blocked",
            selection_metrics=sanitized,
        )

    checks = evaluate_selection_gate(
        sanitized,
        gate_rules=value.gateRules,
        target_r=target_r,
    )
    development = sanitized["bySplit"]["development"]
    independent_failures = sum(not passed for passed in checks.values())
    if (
        _number(development.get("profitFactor"), -1.0) < 0.8
        and _number(development.get("averageNetR"), -1.0) <= -0.15
        and independent_failures >= 3
    ):
        return _decision(
            value,
            action="stop",
            reason_code="development_structurally_weak",
            terminal_status="structural_redesign_required",
            selection_metrics=sanitized,
        )
    if value.completedAttempts >= MAX_AUTOMATIC_ATTEMPTS:
        return _decision(
            value,
            action="stop",
            reason_code="automatic_attempt_budget_exhausted",
            terminal_status="budget_exhausted",
            attempt_number=MAX_AUTOMATIC_ATTEMPTS,
            selection_metrics=sanitized,
        )

    family = str(value.definition.get("signalFamily") or "")
    mutation = _next_mutation(family, value.parameters, value.completedAttempts)
    if mutation is None:
        return _decision(
            value,
            action="stop",
            reason_code="parameter_allowlist_missing",
            terminal_status="structural_redesign_required",
            selection_metrics=sanitized,
        )
    proposed_parameters, changed_parameter = mutation
    attempt_number = value.completedAttempts + 1
    proposed_definition = dict(value.definition)
    proposed_definition["exitPolicy"] = "two_r_half_atr_runner_v1"
    proposed_definition["optimizationLineage"] = {
        "schemaVersion": "bounded_optimization_lineage_v1",
        "campaignId": stable_hash(
            {
                "rootStrategyVersionId": value.rootStrategyVersionId,
                "maxAttempts": MAX_AUTOMATIC_ATTEMPTS,
            },
            prefix="optimization_campaign",
        ),
        "rootStrategyVersionId": value.rootStrategyVersionId,
        "parentStrategyVersionId": value.currentStrategyVersionId,
        "phase": "selection",
        "attemptNumber": attempt_number,
        "maxAttempts": MAX_AUTOMATIC_ATTEMPTS,
        "formalValidationConsumed": False,
        "changedParameter": changed_parameter,
        "selectionMetricsHash": stable_hash(sanitized),
    }
    return _decision(
        value,
        action="create_challenger",
        reason_code="bounded_parameter_adjustment",
        attempt_number=attempt_number,
        changed_parameter=changed_parameter,
        proposed_definition=proposed_definition,
        proposed_parameters=proposed_parameters,
        selection_metrics=sanitized,
    )
