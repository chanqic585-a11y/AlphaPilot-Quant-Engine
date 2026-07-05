"""Build V13.4.26 hypothesis validation datasets and metrics."""

from __future__ import annotations

import json
import math
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from alphapilot.factors.compute_manual_factors import compute_manual_factors
from alphapilot.factors.factor_data_panel import build_factor_data_panel
from alphapilot.factors.factor_schema import FactorDataPanelConfig
from alphapilot.factors.forward_label_builder import ForwardLabelConfig, build_forward_labels
from alphapilot.research_factory.hypothesis_validation_rules import apply_validation_rule, build_hypothesis_validation_rules
from alphapilot.research_factory.hypothesis_validation_schema import (
    HypothesisValidationConfig,
    HypothesisValidationMetrics,
    HypothesisValidationReport,
)

REPORT_ID = "v13_4_26_hypothesis_validation_report"
VERSION = "V13.4.26"


@dataclass
class ValidationBuildResult:
    report: HypothesisValidationReport
    datasetSample: list[dict[str, Any]]
    recommendations: dict[str, Any]


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def load_hypotheses(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    hypotheses = payload.get("hypotheses", [])
    if not isinstance(hypotheses, list):
        raise ValueError("Hypotheses file must contain a hypotheses list.")
    return [item for item in hypotheses if isinstance(item, dict)]


def build_validation(
    config: HypothesisValidationConfig,
    output_report: Path,
    output_summary: Path,
    output_sample: Path,
    output_recommendations: Path,
    sample_limit: int = 240,
) -> ValidationBuildResult:
    warnings: list[str] = []
    hypotheses = load_hypotheses(Path(config.hypothesesPath))
    high_priority = [
        item for item in hypotheses
        if item.get("priority") == "high" and item.get("status") == "research_only"
    ]
    rejected = [item for item in hypotheses if item.get("status") == "rejected"]
    rules = build_hypothesis_validation_rules(high_priority)

    panel, panel_context, panel_warnings = _load_or_rebuild_panel(config)
    warnings.extend(panel_warnings)
    if panel.empty or len(panel) < 1000:
        report = _blocked_report(
            config=config,
            hypotheses=hypotheses,
            rejected_count=len(rejected),
            factor_panel_context=panel_context,
            warnings=warnings + ["Full factor panel unavailable or too small; formal validation blocked."],
            output_report=output_report,
            output_summary=output_summary,
            output_sample=output_sample,
            output_recommendations=output_recommendations,
        )
        return ValidationBuildResult(report=report, datasetSample=[], recommendations=_recommendations(report))

    prepared = _prepare_validation_panel(panel, config)
    metrics: list[HypothesisValidationMetrics] = []
    dataset_sample: list[dict[str, Any]] = []
    validation_rules = [rule.to_dict() for rule in rules]

    hypothesis_by_id = {str(item.get("hypothesisId")): item for item in hypotheses}
    for rule in rules:
        mask, reasons, rule_warnings = apply_validation_rule(prepared, rule)
        warnings.extend(rule_warnings)
        hypothesis = hypothesis_by_id.get(rule.hypothesisId, {})
        metric = _metrics_for_hypothesis(prepared, mask, rule.hypothesisId, str(hypothesis.get("name") or rule.hypothesisId), config.horizons)
        metrics.append(metric)
        dataset_sample.extend(_sample_rows(prepared, mask, reasons, rule.hypothesisId, rule.conditionId, config.horizons, sample_limit=40))

    counts = _result_sets(metrics)
    recommendations = _build_recommendations(metrics)
    report = HypothesisValidationReport(
        reportId=REPORT_ID,
        version=VERSION,
        status="research_only",
        config=config,
        hypothesisCount=len(hypotheses),
        validatedHypothesisCount=len(metrics),
        rejectedHypothesisCount=len(rejected),
        sampleCount=int(len(prepared)),
        factorPanelContext=panel_context,
        noLookaheadAssurance=_no_lookahead_assurance(),
        validationRules=validation_rules,
        validationMetrics=[item.to_dict() for item in metrics],
        topSupportedHypotheses=counts["topSupportedHypotheses"],
        unsupportedHypotheses=counts["unsupportedHypotheses"],
        insufficientSampleHypotheses=counts["insufficientSampleHypotheses"],
        hypothesesWithPositiveExcessVsBTC=counts["hypothesesWithPositiveExcessVsBTC"],
        stabilityWarnings=_stability_warnings(metrics),
        recommendations=recommendations["recommendations"],
        nextStep=recommendations["nextStep"],
        dryRunApproved=False,
        liveTradingApproved=False,
        warnings=warnings,
        generatedAt=utc_now(),
        outputReportPath=output_report.as_posix(),
        outputSummaryPath=output_summary.as_posix(),
        outputSamplePath=output_sample.as_posix(),
        outputRecommendationsPath=output_recommendations.as_posix(),
    )
    return ValidationBuildResult(
        report=report,
        datasetSample=dataset_sample[:sample_limit],
        recommendations=_recommendations(report),
    )


def _load_or_rebuild_panel(config: HypothesisValidationConfig) -> tuple[pd.DataFrame, dict[str, Any], list[str]]:
    if config.factorPanelPath:
        path = Path(config.factorPanelPath)
        loaded = _load_factor_panel(path)
        if _missing_manual_factors(loaded):
            factor_result = compute_manual_factors(loaded)
            loaded = factor_result.panel
            manual_warnings = factor_result.report.get("warnings", [])
        else:
            manual_warnings = []
        return loaded, {
            "factorPanelInput": path.as_posix(),
            "panelRebuilt": False,
            "rowsGenerated": int(len(loaded)),
            "timeframe": config.timeframe,
            "timerange": config.timerange,
        }, list(manual_warnings)

    panel_config = FactorDataPanelConfig(
        timerange=config.timerange,
        timeframe=config.timeframe,
        pairs=[],
        dataPath=config.dataPath,
        useDynamicUniverse=config.useDynamicUniverse,
        universeSnapshotsPath=config.universeSnapshotsPath,
        sampleSize=200,
    )
    panel_build = build_factor_data_panel(panel_config)
    factor_result = compute_manual_factors(panel_build.panel)
    context = {
        "factorPanelInput": "rebuilt_from_local_public_ohlcv",
        "panelRebuilt": True,
        "rowsGenerated": int(len(factor_result.panel)),
        "baseRowsGenerated": int(len(panel_build.panel)),
        "timeframe": config.timeframe,
        "timerange": config.timerange,
        "loadedPairs": panel_build.loadReport.loadedPairs,
        "failedPairs": panel_build.loadReport.failedPairs,
        "universeMembershipAvailable": panel_build.universeMembershipAvailable,
        "universeMembershipSource": panel_build.universeMembershipSource,
        "dynamicUniverseSnapshotsUsed": panel_build.dynamicUniverseSnapshotsUsed,
        "fullPanelCommitted": False,
    }
    warnings = list(panel_build.warnings) + list(factor_result.report.get("warnings", []))
    warnings.append("Full factor panel was rebuilt in memory from local public OHLCV; full panel was not committed.")
    return factor_result.panel, context, warnings


def _load_factor_panel(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"factor panel not found: {path.as_posix()}")
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return pd.DataFrame(payload)
    if isinstance(payload, dict):
        if isinstance(payload.get("rows"), list):
            return pd.DataFrame(payload["rows"])
        if isinstance(payload.get("panel"), list):
            return pd.DataFrame(payload["panel"])
    raise ValueError("Unsupported factor panel JSON layout. Expected a list, rows, or panel array.")


def _missing_manual_factors(panel: pd.DataFrame) -> bool:
    return "trend_strength" not in panel.columns or "bollinger_position" not in panel.columns


def _prepare_validation_panel(panel: pd.DataFrame, config: HypothesisValidationConfig) -> pd.DataFrame:
    label_result = build_forward_labels(
        panel,
        ForwardLabelConfig(horizons=config.horizons, tpPct=config.tpPct, slPct=config.slPct, timeframe=config.timeframe),
    )
    output = label_result.panel.copy()
    output = output.sort_values(["timestamp", "pair"]).reset_index(drop=True)
    output["timestampDt"] = pd.to_datetime(output["timestamp"], utc=True, errors="coerce")
    output["month"] = output["timestampDt"].dt.strftime("%Y-%m")
    output["volatilityRankPct"] = _timestamp_rank_pct(output, "volatility_3d")
    output["atrRankPct"] = _timestamp_rank_pct(output, "atr_pct")
    output["trendStrengthRankPct"] = _timestamp_rank_pct(output, "trend_strength")
    output["liquidityRankPct"] = _timestamp_rank_pct(output, "liquidity_rank")

    btc_rows = output[output["pair"] == "BTC/USDT:USDT"].set_index("timestamp")
    for horizon in config.horizons:
        forward = f"forwardReturn_{horizon}"
        btc_forward = f"btcForwardReturn_{horizon}"
        excess = f"excessReturnVsBTC_{horizon}"
        if forward in btc_rows:
            output[btc_forward] = output["timestamp"].map(btc_rows[forward])
            output[excess] = pd.to_numeric(output[forward], errors="coerce") - pd.to_numeric(output[btc_forward], errors="coerce")
        else:
            output[btc_forward] = pd.NA
            output[excess] = pd.NA
    return output


def _timestamp_rank_pct(panel: pd.DataFrame, column: str) -> pd.Series:
    if column not in panel.columns:
        return pd.Series(pd.NA, index=panel.index)
    values = pd.to_numeric(panel[column], errors="coerce")
    return values.groupby(panel["timestamp"], sort=False).rank(method="average", pct=True)


def _metrics_for_hypothesis(panel: pd.DataFrame, mask: pd.Series, hypothesis_id: str, name: str, horizons: list[int]) -> HypothesisValidationMetrics:
    primary = 12 if 12 in horizons else horizons[0]
    subset = panel.loc[mask.fillna(False)].copy()
    primary_return = pd.to_numeric(subset.get(f"forwardReturn_{primary}"), errors="coerce") if not subset.empty else pd.Series(dtype=float)
    valid = primary_return.dropna()
    per_horizon = {str(horizon): _per_horizon_metrics(subset, horizon) for horizon in horizons}
    stability = {
        "monthly": _group_stability(subset, primary, "month"),
        "pair": _group_stability(subset, primary, "pair"),
        "regime": _group_stability(subset, primary, "regimeLabel"),
        "liquidity": _group_stability(subset, primary, "liquidityBucket"),
    }
    profit_factor = _profit_factor(valid)
    expectancy = _safe_number(valid.mean()) if not valid.empty else None
    avg_excess = _safe_number(pd.to_numeric(subset.get(f"excessReturnVsBTC_{primary}"), errors="coerce").mean()) if not subset.empty else None
    support_level = _support_level(int(len(valid)), profit_factor, expectancy, avg_excess, bool(stability["monthly"]["stable"]))
    return HypothesisValidationMetrics(
        hypothesisId=hypothesis_id,
        hypothesisName=name,
        supportLevel=support_level,
        sampleCount=int(len(panel)),
        conditionPassCount=int(len(subset)),
        conditionPassRate=_safe_number(len(subset) / len(panel), 8) or 0.0,
        validLabelCount=int(len(valid)),
        primaryHorizon=primary,
        averageForwardReturn=_safe_number(valid.mean()) if not valid.empty else None,
        medianForwardReturn=_safe_number(valid.median()) if not valid.empty else None,
        hitTpBeforeSlProbability=_bool_mean(subset.get(f"hitTpBeforeSl_{primary}")),
        hitSlBeforeTpProbability=_bool_mean(subset.get(f"hitSlBeforeTp_{primary}")),
        profitFactor=profit_factor,
        expectancy=expectancy,
        averageMfe=_safe_number(pd.to_numeric(subset.get(f"mfePct_{primary}"), errors="coerce").mean()) if not subset.empty else None,
        averageMae=_safe_number(pd.to_numeric(subset.get(f"maePct_{primary}"), errors="coerce").mean()) if not subset.empty else None,
        averageExcessReturnVsBTC=avg_excess,
        perHorizon=per_horizon,
        monthlyStability=stability["monthly"],
        pairStability=stability["pair"],
        regimeStability=stability["regime"],
        liquidityStability=stability["liquidity"],
        warnings=_metric_warnings(hypothesis_id, int(len(valid)), profit_factor, expectancy, avg_excess, stability),
    )


def _per_horizon_metrics(subset: pd.DataFrame, horizon: int) -> dict[str, Any]:
    if subset.empty:
        return {"validLabelCount": 0, "averageForwardReturn": None, "profitFactor": None, "expectancy": None, "averageExcessReturnVsBTC": None}
    returns = pd.to_numeric(subset.get(f"forwardReturn_{horizon}"), errors="coerce").dropna()
    excess = pd.to_numeric(subset.get(f"excessReturnVsBTC_{horizon}"), errors="coerce").dropna()
    return {
        "validLabelCount": int(len(returns)),
        "averageForwardReturn": _safe_number(returns.mean()) if not returns.empty else None,
        "medianForwardReturn": _safe_number(returns.median()) if not returns.empty else None,
        "profitFactor": _profit_factor(returns),
        "expectancy": _safe_number(returns.mean()) if not returns.empty else None,
        "hitTpBeforeSlProbability": _bool_mean(subset.get(f"hitTpBeforeSl_{horizon}")),
        "hitSlBeforeTpProbability": _bool_mean(subset.get(f"hitSlBeforeTp_{horizon}")),
        "averageMfe": _safe_number(pd.to_numeric(subset.get(f"mfePct_{horizon}"), errors="coerce").mean()),
        "averageMae": _safe_number(pd.to_numeric(subset.get(f"maePct_{horizon}"), errors="coerce").mean()),
        "averageExcessReturnVsBTC": _safe_number(excess.mean()) if not excess.empty else None,
    }


def _group_stability(subset: pd.DataFrame, horizon: int, group_column: str) -> dict[str, Any]:
    if subset.empty or group_column not in subset.columns:
        return {"rows": [], "stable": False, "positiveGroupRatio": None}
    rows: list[dict[str, Any]] = []
    for group_value, frame in subset.groupby(group_column, dropna=False, sort=True):
        returns = pd.to_numeric(frame.get(f"forwardReturn_{horizon}"), errors="coerce").dropna()
        if returns.empty:
            continue
        rows.append({
            "group": str(group_value),
            "sampleCount": int(len(frame)),
            "validLabelCount": int(len(returns)),
            "averageForwardReturn": _safe_number(returns.mean()),
            "profitFactor": _profit_factor(returns),
            "expectancy": _safe_number(returns.mean()),
        })
    usable = [row for row in rows if row["validLabelCount"] >= 20 and row["averageForwardReturn"] is not None]
    positive_ratio = None
    if usable:
        positive_ratio = _safe_number(sum(1 for row in usable if float(row["averageForwardReturn"]) > 0) / len(usable))
    stable = bool(usable and len(usable) >= 3 and positive_ratio is not None and positive_ratio >= 0.6)
    return {
        "rows": rows[:40],
        "stable": stable,
        "positiveGroupRatio": positive_ratio,
        "usableGroupCount": len(usable),
    }


def _profit_factor(returns: pd.Series) -> float | None:
    values = pd.to_numeric(returns, errors="coerce").dropna()
    if values.empty:
        return None
    wins = float(values[values > 0].sum())
    losses = float(values[values < 0].sum())
    if losses >= 0:
        return None
    return _safe_number(wins / abs(losses))


def _bool_mean(values: Any) -> float | None:
    if values is None:
        return None
    series = pd.Series(values).dropna()
    if series.empty:
        return None
    return _safe_number(series.astype(bool).mean())


def _support_level(sample_count: int, profit_factor: float | None, expectancy: float | None, excess: float | None, stable_across_months: bool) -> str:
    if sample_count < 100:
        return "insufficient_sample"
    if (
        sample_count >= 500
        and profit_factor is not None
        and profit_factor >= 1.15
        and expectancy is not None
        and expectancy > 0
        and excess is not None
        and excess > 0
        and stable_across_months
    ):
        return "strong_research_support"
    if sample_count >= 200 and profit_factor is not None and profit_factor >= 1.05 and expectancy is not None and expectancy >= 0:
        return "moderate_research_support"
    if sample_count >= 100 and profit_factor is not None and profit_factor > 1.0:
        return "weak_research_support"
    return "no_support"


def _metric_warnings(
    hypothesis_id: str,
    valid_count: int,
    profit_factor: float | None,
    expectancy: float | None,
    excess: float | None,
    stability: dict[str, dict[str, Any]],
) -> list[str]:
    warnings: list[str] = []
    if valid_count < 100:
        warnings.append(f"{hypothesis_id} has insufficient valid samples.")
    if profit_factor is None:
        warnings.append(f"{hypothesis_id} profitFactor unavailable.")
    if expectancy is None:
        warnings.append(f"{hypothesis_id} expectancy unavailable.")
    if excess is None:
        warnings.append(f"{hypothesis_id} BTC excess return unavailable.")
    if not stability["monthly"]["stable"]:
        warnings.append(f"{hypothesis_id} not stable across months by the V13.4.26 research rule.")
    return warnings


def _sample_rows(
    panel: pd.DataFrame,
    mask: pd.Series,
    reasons: pd.Series,
    hypothesis_id: str,
    condition_id: str,
    horizons: list[int],
    sample_limit: int,
) -> list[dict[str, Any]]:
    passed = panel.loc[mask.fillna(False)].head(max(1, sample_limit - 5)).copy()
    failed = panel.loc[~mask.fillna(False)].head(5).copy()
    sample = pd.concat([passed, failed], ignore_index=False).head(sample_limit)
    rows: list[dict[str, Any]] = []
    for idx, row in sample.iterrows():
        factor_values = {
            key: _safe_value(row.get(key))
            for key in [
                "atr_pct",
                "volatility_3d",
                "trend_strength",
                "distance_to_ema50",
                "bollinger_position",
                "volume_expansion_3d",
                "liquidity_rank",
                "btc_momentum_12",
            ]
        }
        payload: dict[str, Any] = {
            "validationId": f"{hypothesis_id}-{idx}",
            "hypothesisId": hypothesis_id,
            "timestamp": row.get("timestamp"),
            "pair": row.get("pair"),
            "timeframe": "1h",
            "conditionPassed": bool(mask.loc[idx]) if idx in mask.index else False,
            "conditionReason": str(reasons.loc[idx]) if idx in reasons.index else "unavailable",
            "factorValues": factor_values,
            "regimeLabel": row.get("regimeLabel"),
            "liquidityBucket": row.get("liquidityBucket"),
            "volatilityBucket": row.get("volatilityBucket"),
            "universeMember": bool(row.get("universeMember")) if row.get("universeMember") is not None else None,
        }
        for horizon in horizons:
            for column in [
                f"forwardReturn_{horizon}",
                f"mfePct_{horizon}",
                f"maePct_{horizon}",
                f"hitTpBeforeSl_{horizon}",
                f"hitSlBeforeTp_{horizon}",
                f"btcForwardReturn_{horizon}",
                f"excessReturnVsBTC_{horizon}",
            ]:
                payload[column] = _safe_value(row.get(column))
        rows.append(payload)
    return rows


def _safe_value(value: Any) -> Any:
    if isinstance(value, (bool, str)) or value is None:
        return value
    try:
        if pd.isna(value):
            return None
    except TypeError:
        pass
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return round(value, 10)
    if isinstance(value, int):
        return int(value)
    try:
        number = float(value)
        if math.isnan(number) or math.isinf(number):
            return None
        return round(number, 10)
    except (TypeError, ValueError):
        return str(value)


def _safe_number(value: Any, digits: int = 8) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return round(number, digits)


def _result_sets(metrics: list[HypothesisValidationMetrics]) -> dict[str, list[str]]:
    top = [
        item.hypothesisId for item in metrics
        if item.supportLevel in {"strong_research_support", "moderate_research_support", "weak_research_support"}
    ]
    unsupported = [item.hypothesisId for item in metrics if item.supportLevel == "no_support"]
    insufficient = [item.hypothesisId for item in metrics if item.supportLevel == "insufficient_sample"]
    positive_excess = [
        item.hypothesisId for item in metrics
        if item.averageExcessReturnVsBTC is not None and item.averageExcessReturnVsBTC > 0
    ]
    return {
        "topSupportedHypotheses": top,
        "unsupportedHypotheses": unsupported,
        "insufficientSampleHypotheses": insufficient,
        "hypothesesWithPositiveExcessVsBTC": positive_excess,
    }


def _stability_warnings(metrics: list[HypothesisValidationMetrics]) -> list[str]:
    warnings: list[str] = []
    for item in metrics:
        warnings.extend(item.warnings)
    return warnings


def _build_recommendations(metrics: list[HypothesisValidationMetrics]) -> dict[str, Any]:
    supported = [
        item for item in metrics
        if item.supportLevel in {"strong_research_support", "moderate_research_support"}
    ]
    weak = [item for item in metrics if item.supportLevel == "weak_research_support"]
    if supported:
        next_step = "V13.4.27 - Hypothesis-Based Strategy Candidate Specification"
        recommendations = [
            {
                "type": "strategy_spec_research_only",
                "hypothesisIds": [item.hypothesisId for item in supported],
                "reason": "At least one hypothesis reached moderate or strong research support. This still is not Dry-run approval.",
            }
        ]
    elif weak:
        next_step = "V13.4.27 - Hypothesis Refinement and Expanded Validation"
        recommendations = [
            {
                "type": "refine_validation",
                "hypothesisIds": [item.hypothesisId for item in weak],
                "reason": "Only weak support was found; require expanded validation before any strategy specification.",
            }
        ]
    else:
        next_step = "V13.4.27 - Research Direction Reset / Data Expansion"
        recommendations = [
            {
                "type": "data_expansion",
                "hypothesisIds": [],
                "reason": "No high-priority hypothesis reached research support under V13.4.26 gates.",
            }
        ]
    recommendations.append(
        {
            "type": "safety_boundary",
            "reason": "supportLevel is research evidence only; it is not a trading gate, Dry-run approval, order, or live trading permission.",
        }
    )
    return {"nextStep": next_step, "recommendations": recommendations}


def _recommendations(report: HypothesisValidationReport) -> dict[str, Any]:
    return {
        "reportId": "v13_4_26_hypothesis_recommendations",
        "version": VERSION,
        "nextStep": report.nextStep,
        "topSupportedHypotheses": report.topSupportedHypotheses,
        "unsupportedHypotheses": report.unsupportedHypotheses,
        "insufficientSampleHypotheses": report.insufficientSampleHypotheses,
        "hypothesesWithPositiveExcessVsBTC": report.hypothesesWithPositiveExcessVsBTC,
        "recommendations": report.recommendations,
        "dryRunApproved": False,
        "liveTradingApproved": False,
        "generatedAt": report.generatedAt,
    }


def _blocked_report(
    config: HypothesisValidationConfig,
    hypotheses: list[dict[str, Any]],
    rejected_count: int,
    factor_panel_context: dict[str, Any],
    warnings: list[str],
    output_report: Path,
    output_summary: Path,
    output_sample: Path,
    output_recommendations: Path,
) -> HypothesisValidationReport:
    now = utc_now()
    return HypothesisValidationReport(
        reportId=REPORT_ID,
        version=VERSION,
        status="blocked_insufficient_factor_panel",
        config=config,
        hypothesisCount=len(hypotheses),
        validatedHypothesisCount=0,
        rejectedHypothesisCount=rejected_count,
        sampleCount=0,
        factorPanelContext=factor_panel_context,
        noLookaheadAssurance=_no_lookahead_assurance(),
        validationRules=[],
        validationMetrics=[],
        topSupportedHypotheses=[],
        unsupportedHypotheses=[],
        insufficientSampleHypotheses=[],
        hypothesesWithPositiveExcessVsBTC=[],
        stabilityWarnings=warnings,
        recommendations=[],
        nextStep="Rebuild full factor panel before validation.",
        dryRunApproved=False,
        liveTradingApproved=False,
        warnings=warnings,
        generatedAt=now,
        outputReportPath=output_report.as_posix(),
        outputSummaryPath=output_summary.as_posix(),
        outputSamplePath=output_sample.as_posix(),
        outputRecommendationsPath=output_recommendations.as_posix(),
    )


def _no_lookahead_assurance() -> list[str]:
    return [
        "Condition features are point-in-time and use current or historical data only.",
        "Cross-sectional ranks are computed within the same timestamp only.",
        "Forward labels are forward-looking for validation only.",
        "Forward labels are not used to construct conditions, select pairs, modify universe membership, create orders, or approve Dry-run.",
        "BTC forward returns are used only for excess-return evaluation.",
    ]
