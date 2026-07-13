"""Bounded, split-safe structural redesign policy for research strategies."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from alphapilot.evolution.registry.hashing import stable_hash

from .bounded_optimizer import evaluate_selection_gate, sanitize_selection_metrics


STRUCTURAL_GRAMMAR_VERSION = "structural_strategy_grammar_v1"
MAX_STRUCTURAL_GENERATIONS = 3
_SELECTION_SPLITS = ("development", "walk_forward")


@dataclass(frozen=True)
class StructuralRedesignInput:
    rootStrategyVersionId: str
    currentStrategyVersionId: str
    displayName: str
    definition: dict[str, Any]
    parameters: dict[str, Any]
    metrics: dict[str, Any]
    gateRules: dict[str, Any]
    failureCategory: str | None
    runStatus: str
    usedRecipeIds: tuple[str, ...] = ()
    activeStructuralChildExists: bool = False


@dataclass(frozen=True)
class StructuralFailureProfile:
    failedGateNames: tuple[str, ...]
    metricsBySplit: dict[str, dict[str, Any]]
    costStressBySplit: dict[str, dict[str, Any]]
    direction: str
    timeframe: str
    signalFamily: str
    exitPolicy: str
    currentFilters: dict[str, Any]
    overtrading: bool
    weakExpectancy: bool
    drawdownConcentration: bool
    sparseSample: bool
    transactionCostSensitive: bool
    evidenceHash: str


@dataclass(frozen=True)
class StructuralRedesignDecision:
    action: str
    reasonCode: str
    campaignId: str
    decisionKey: str
    rootStrategyVersionId: str
    currentStrategyVersionId: str
    generation: int
    maxGenerations: int
    recipeId: str | None
    recipeSummary: str | None
    failureProfile: StructuralFailureProfile | None
    proposedDefinition: dict[str, Any] | None
    proposedParameters: dict[str, Any] | None


@dataclass(frozen=True)
class _Recipe:
    recipeId: str
    summary: str
    supportedDirections: tuple[str, ...]
    build: Callable[[str, str], tuple[str, dict[str, Any], dict[str, Any]]]


def _number(value: Any, fallback: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return fallback
    return parsed if parsed == parsed else fallback


def _selection_metrics_available(metrics: dict[str, Any]) -> bool:
    splits = metrics.get("bySplit") if isinstance(metrics, dict) else None
    return isinstance(splits, dict) and all(
        isinstance(splits.get(split), dict) and bool(splits[split])
        for split in _SELECTION_SPLITS
    )


def _timeframe_settings(timeframe: str) -> tuple[float, int, float, float]:
    settings = {
        "5m": (1.0, 24, 0.002, 0.018),
        "15m": (1.2, 16, 0.003, 0.025),
        "1h": (1.5, 12, 0.004, 0.04),
        "4h": (1.8, 8, 0.006, 0.06),
        "1d": (2.0, 6, 0.008, 0.08),
    }
    return settings.get(timeframe, settings["15m"])


def _trend_pullback_recipe(
    direction: str, timeframe: str
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    stop_atr, max_hold, atr_min, atr_max = _timeframe_settings(timeframe)
    if direction == "short":
        return _failed_reclaim_parameters(
            timeframe,
            stop_atr=stop_atr,
            max_hold=max_hold,
            atr_min=atr_min,
            atr_max=atr_max,
            volume_min=1.2,
            regime="ema_downtrend_with_btc_shock_guard",
        )
    parameters = {
        "pullback_lookback": 5 if timeframe != "5m" else 6,
        "pullback_tolerance": 0.004 if timeframe != "5m" else 0.003,
        "ema_slope_lookback": 4 if timeframe != "5m" else 6,
        "trend_tolerance": 1.0,
        "reclaim_buffer": 0.0005,
        "rsi_min": 42 if timeframe != "5m" else 44,
        "rsi_max": 66 if timeframe != "5m" else 64,
        "volume_min": 1.1 if timeframe != "5m" else 1.15,
        "atr_pct_min": atr_min,
        "atr_pct_max": atr_max,
        "stop_atr": stop_atr,
        "max_hold": max_hold,
    }
    filters = {
        "regime": "ema_uptrend_with_btc_shock_guard",
        "confirmation": "closed_candle_rsi_volume",
        "volatilityBand": [atr_min, atr_max],
    }
    return "trend_pullback_confirmation_long", parameters, filters


def _compression_recipe(
    direction: str, timeframe: str
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    stop_atr, max_hold, atr_min, atr_max = _timeframe_settings(timeframe)
    if direction == "short":
        return _failed_reclaim_parameters(
            timeframe,
            stop_atr=stop_atr,
            max_hold=max_hold,
            atr_min=atr_min,
            atr_max=atr_max,
            volume_min=1.35,
            regime="volatility_guarded_downtrend",
        )
    parameters = {
        "lookback": 36 if timeframe == "5m" else 28,
        "squeeze_window": 96 if timeframe == "5m" else 72,
        "squeeze_ratio": 0.72 if timeframe == "5m" else 0.75,
        "expansion_min": 1.08,
        "trend_tolerance": 1.0,
        "rsi_max": 72 if timeframe == "5m" else 74,
        "volume_min": 1.8 if timeframe == "5m" else 1.6,
        "atr_pct_max": atr_max,
        "stop_atr": max(stop_atr, 1.1),
        "max_hold": max_hold,
    }
    filters = {
        "regime": "ema_alignment_with_btc_shock_guard",
        "confirmation": "closed_candle_range_expansion",
        "volatilityBand": [atr_min, atr_max],
    }
    return "compression_release_long", parameters, filters


def _failed_reclaim_parameters(
    timeframe: str,
    *,
    stop_atr: float,
    max_hold: int,
    atr_min: float,
    atr_max: float,
    volume_min: float,
    regime: str,
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    parameters = {
        "reclaim_lookback": 6 if timeframe == "5m" else 5,
        "reclaim_tolerance": 0.003 if timeframe == "5m" else 0.005,
        "rejection_buffer": 0.0005,
        "ema_slope_lookback": 6 if timeframe == "5m" else 4,
        "trend_tolerance": 1.0,
        "rsi_min": 36 if timeframe == "5m" else 34,
        "rsi_max": 58 if timeframe == "5m" else 60,
        "volume_min": volume_min,
        "atr_pct_min": atr_min,
        "atr_pct_max": atr_max,
        "stop_atr": stop_atr,
        "max_hold": max_hold,
    }
    filters = {
        "regime": regime,
        "confirmation": "closed_candle_failed_reclaim",
        "volatilityBand": [atr_min, atr_max],
    }
    return "failed_reclaim_short", parameters, filters


def _failed_reclaim_recipe(
    direction: str, timeframe: str
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    stop_atr, max_hold, atr_min, atr_max = _timeframe_settings(timeframe)
    return _failed_reclaim_parameters(
        timeframe,
        stop_atr=stop_atr,
        max_hold=max_hold,
        atr_min=atr_min,
        atr_max=atr_max,
        volume_min=1.15 if timeframe == "5m" else 1.1,
        regime="ema_downtrend_with_btc_shock_guard",
    )


_RECIPES = (
    _Recipe(
        recipeId="regime_confirmed_trend_pullback_v1",
        summary="趋势与 BTC 急跌过滤后的闭合 K 线回踩确认",
        supportedDirections=("long", "short"),
        build=_trend_pullback_recipe,
    ),
    _Recipe(
        recipeId="volatility_guarded_compression_release_v1",
        summary="波动率护栏下的压缩释放确认",
        supportedDirections=("long", "short"),
        build=_compression_recipe,
    ),
    _Recipe(
        recipeId="failed_reclaim_rejection_v1",
        summary="弱势反抽失败后的闭合 K 线拒绝",
        supportedDirections=("short",),
        build=_failed_reclaim_recipe,
    ),
)


def build_structural_failure_profile(
    value: StructuralRedesignInput,
) -> StructuralFailureProfile:
    sanitized = sanitize_selection_metrics(value.metrics)
    metrics_by_split = {
        split: dict(sanitized["bySplit"].get(split) or {})
        for split in _SELECTION_SPLITS
    }
    stress_by_split = {
        split: dict(sanitized["costStress"]["bySplit"].get(split) or {})
        for split in _SELECTION_SPLITS
    }
    target_r = _number(value.definition.get("targetR"), 0.0)
    checks = evaluate_selection_gate(
        sanitized,
        gate_rules=value.gateRules,
        target_r=target_r,
    )
    failed_gates = tuple(sorted(name for name, passed in checks.items() if not passed))
    trade_counts = [
        int(_number(metrics_by_split[split].get("tradeCount"), 0.0))
        for split in _SELECTION_SPLITS
    ]
    average_net_rs = [
        _number(metrics_by_split[split].get("averageNetR"), -1.0)
        for split in _SELECTION_SPLITS
    ]
    drawdowns = [
        _number(metrics_by_split[split].get("maximumDrawdownR"), float("inf"))
        for split in _SELECTION_SPLITS
    ]
    stress_net_rs = [
        _number(stress_by_split[split].get("averageNetR"), -1.0)
        for split in _SELECTION_SPLITS
    ]
    minimum_trade_count = int(_number(value.gateRules.get("minimumTradeCount"), 30))
    maximum_drawdown = _number(value.gateRules.get("maximumDrawdownR"), 20.0)
    profile_payload = {
        "failedGateNames": failed_gates,
        "metricsBySplit": metrics_by_split,
        "costStressBySplit": stress_by_split,
        "direction": str(value.definition.get("direction") or ""),
        "timeframe": str(value.definition.get("timeframe") or ""),
        "signalFamily": str(value.definition.get("signalFamily") or ""),
        "exitPolicy": str(value.definition.get("exitPolicy") or ""),
        "currentFilters": dict(value.parameters),
        "overtrading": sum(trade_counts) >= max(120, minimum_trade_count * 4),
        "weakExpectancy": any(item <= 0 for item in average_net_rs),
        "drawdownConcentration": any(item > maximum_drawdown for item in drawdowns),
        "sparseSample": any(item <= 0 for item in trade_counts)
        or sum(trade_counts) < minimum_trade_count,
        "transactionCostSensitive": any(item <= 0 for item in stress_net_rs),
    }
    return StructuralFailureProfile(
        **profile_payload,
        evidenceHash=stable_hash(profile_payload),
    )


def _campaign_id(value: StructuralRedesignInput) -> str:
    return stable_hash(
        {
            "rootStrategyVersionId": value.rootStrategyVersionId,
            "grammarVersion": STRUCTURAL_GRAMMAR_VERSION,
            "maxGenerations": MAX_STRUCTURAL_GENERATIONS,
        },
        prefix="structural_redesign_campaign",
    )


def _decision(
    value: StructuralRedesignInput,
    *,
    action: str,
    reason_code: str,
    generation: int,
    profile: StructuralFailureProfile | None,
    recipe: _Recipe | None = None,
    proposed_definition: dict[str, Any] | None = None,
    proposed_parameters: dict[str, Any] | None = None,
) -> StructuralRedesignDecision:
    campaign_id = _campaign_id(value)
    decision_key = stable_hash(
        {
            "campaignId": campaign_id,
            "currentStrategyVersionId": value.currentStrategyVersionId,
            "generation": generation,
            "failureEvidenceHash": profile.evidenceHash if profile is not None else None,
            "grammarVersion": STRUCTURAL_GRAMMAR_VERSION,
            "action": action,
            "reasonCode": reason_code,
            "recipeId": recipe.recipeId if recipe is not None else None,
        },
        prefix="structural_redesign_decision",
    )
    return StructuralRedesignDecision(
        action=action,
        reasonCode=reason_code,
        campaignId=campaign_id,
        decisionKey=decision_key,
        rootStrategyVersionId=value.rootStrategyVersionId,
        currentStrategyVersionId=value.currentStrategyVersionId,
        generation=generation,
        maxGenerations=MAX_STRUCTURAL_GENERATIONS,
        recipeId=recipe.recipeId if recipe is not None else None,
        recipeSummary=recipe.summary if recipe is not None else None,
        failureProfile=profile,
        proposedDefinition=proposed_definition,
        proposedParameters=proposed_parameters,
    )


def decide_structural_redesign(
    value: StructuralRedesignInput,
) -> StructuralRedesignDecision:
    lineage = value.definition.get("structuralRedesignLineage")
    lineage = lineage if isinstance(lineage, dict) else {}
    current_generation = max(0, int(lineage.get("generation") or 0))

    if value.activeStructuralChildExists:
        return _decision(
            value,
            action="wait",
            reason_code="active_structural_child_exists",
            generation=current_generation,
            profile=None,
        )
    if value.failureCategory != "strategy_performance":
        return _decision(
            value,
            action="stop",
            reason_code="non_performance_failure",
            generation=current_generation,
            profile=None,
        )
    if value.runStatus != "failed":
        return _decision(
            value,
            action="stop",
            reason_code="terminal_failed_run_required",
            generation=current_generation,
            profile=None,
        )
    if _number(value.definition.get("targetR"), 0.0) < 2.0:
        return _decision(
            value,
            action="stop",
            reason_code="minimum_target_r_violation",
            generation=current_generation,
            profile=None,
        )

    sanitized = sanitize_selection_metrics(value.metrics)
    if not _selection_metrics_available(sanitized):
        return _decision(
            value,
            action="stop",
            reason_code="selection_metrics_missing",
            generation=current_generation,
            profile=None,
        )
    profile = build_structural_failure_profile(value)
    development = profile.metricsBySplit["development"]
    if not (
        _number(development.get("profitFactor"), -1.0) < 0.8
        and _number(development.get("averageNetR"), -1.0) <= -0.15
        and len(profile.failedGateNames) >= 3
    ):
        return _decision(
            value,
            action="stop",
            reason_code="failure_not_structurally_weak",
            generation=current_generation,
            profile=profile,
        )
    if current_generation >= MAX_STRUCTURAL_GENERATIONS:
        return _decision(
            value,
            action="stop",
            reason_code="structural_generation_budget_exhausted",
            generation=current_generation,
            profile=profile,
        )

    direction = str(value.definition.get("direction") or "")
    timeframe = str(value.definition.get("timeframe") or "")
    used_recipe_ids = set(value.usedRecipeIds)
    current_recipe_id = str(lineage.get("recipeId") or "")
    if current_recipe_id:
        used_recipe_ids.add(current_recipe_id)
    recipe = next(
        (
            candidate
            for candidate in _RECIPES
            if candidate.recipeId not in used_recipe_ids
            and direction in candidate.supportedDirections
        ),
        None,
    )
    next_generation = current_generation + 1
    if recipe is None:
        return _decision(
            value,
            action="stop",
            reason_code="no_novel_structural_recipe",
            generation=current_generation,
            profile=profile,
        )

    signal_family, parameters, structural_filters = recipe.build(direction, timeframe)
    definition = dict(value.definition)
    definition.update(
        {
            "signalEngine": "short_cycle_v1",
            "signalFamily": signal_family,
            "timeframe": timeframe,
            "direction": direction,
            "targetR": _number(value.definition.get("targetR"), 2.0),
            "exitPolicy": "two_r_half_atr_runner_v1",
            "researchOnly": True,
            "executionEnabled": False,
            "structuralFilters": structural_filters,
            "forwardSignalPolicy": {
                "schemaVersion": "short_cycle_forward_policy_v1",
                "signalEngine": "short_cycle_v1",
                "signalFamily": signal_family,
                "timeframe": timeframe,
                "direction": direction,
                "parameters": dict(parameters),
            },
            "structuralRedesignLineage": {
                "schemaVersion": "structural_redesign_lineage_v1",
                "campaignId": _campaign_id(value),
                "rootStrategyVersionId": value.rootStrategyVersionId,
                "parentStrategyVersionId": value.currentStrategyVersionId,
                "generation": next_generation,
                "maxGenerations": MAX_STRUCTURAL_GENERATIONS,
                "grammarVersion": STRUCTURAL_GRAMMAR_VERSION,
                "recipeId": recipe.recipeId,
                "failureEvidenceHash": profile.evidenceHash,
            },
        }
    )
    definition.pop("optimizationLineage", None)
    return _decision(
        value,
        action="create_child",
        reason_code="novel_structural_recipe_selected",
        generation=next_generation,
        profile=profile,
        recipe=recipe,
        proposed_definition=definition,
        proposed_parameters=parameters,
    )
