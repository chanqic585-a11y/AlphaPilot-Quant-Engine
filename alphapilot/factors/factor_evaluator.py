"""Research-only factor evaluator for V13.4.22.

The evaluator measures statistical relationships between point-in-time factors
and forward labels. It does not create strategy entries, trade signals, orders,
Dry-run settings, or live-trading approvals.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import pandas as pd

from alphapilot.factors.manual_factor_library import build_manual_factor_library_v01, manual_factor_output_columns


@dataclass(frozen=True)
class FactorEvaluationConfig:
    horizons: list[int] = field(default_factory=lambda: [4, 8, 12, 24])
    quantiles: int = 5
    tpPct: float = 0.05
    slPct: float = 0.025
    primaryHorizon: int = 12
    minIcCrossSectionSize: int = 5


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _safe_number(value: Any, digits: int = 8) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return round(number, digits)


def _safe_ratio(numerator: float, denominator: float, digits: int = 8) -> float | None:
    if denominator == 0:
        return None
    return _safe_number(numerator / denominator, digits)


def _corr(left: pd.Series, right: pd.Series, rank: bool = False) -> float | None:
    values = pd.concat([left, right], axis=1).dropna()
    if len(values) < 2:
        return None
    a = values.iloc[:, 0]
    b = values.iloc[:, 1]
    if a.nunique(dropna=True) < 2 or b.nunique(dropna=True) < 2:
        return None
    if rank:
        a = a.rank(method="average")
        b = b.rank(method="average")
    return _safe_number(a.corr(b))


def _cross_sectional_ic(panel: pd.DataFrame, factor: str, label: str, min_size: int) -> dict[str, Any]:
    valid = panel[["timestamp", factor, label]].copy()
    valid[factor] = pd.to_numeric(valid[factor], errors="coerce")
    valid[label] = pd.to_numeric(valid[label], errors="coerce")
    valid = valid.dropna(subset=[factor, label])
    if valid.empty:
        ic_values: list[float] = []
        rank_ic_values: list[float] = []
        valid_groups = 0
        skipped_groups = int(panel["timestamp"].nunique()) if "timestamp" in panel else 0
    else:
        def grouped_corr(frame: pd.DataFrame, left: str, right: str) -> pd.Series:
            group_key = frame["timestamp"]
            grouped = frame.groupby(group_key, sort=False)
            count = grouped[left].count()
            sum_x = grouped[left].sum()
            sum_y = grouped[right].sum()
            sum_xy = (frame[left] * frame[right]).groupby(group_key, sort=False).sum()
            sum_x2 = (frame[left] * frame[left]).groupby(group_key, sort=False).sum()
            sum_y2 = (frame[right] * frame[right]).groupby(group_key, sort=False).sum()
            covariance = sum_xy - (sum_x * sum_y / count)
            var_x = sum_x2 - ((sum_x * sum_x) / count)
            var_y = sum_y2 - ((sum_y * sum_y) / count)
            corr = covariance / (var_x * var_y).pow(0.5)
            return corr.where((count >= min_size) & (var_x > 0) & (var_y > 0))

        ic_series = grouped_corr(valid, factor, label).dropna()
        ranked = valid.copy()
        ranked["_factorRank"] = ranked.groupby("timestamp", sort=False)[factor].rank(method="average")
        ranked["_labelRank"] = ranked.groupby("timestamp", sort=False)[label].rank(method="average")
        rank_ic_series = grouped_corr(ranked, "_factorRank", "_labelRank").dropna()
        ic_values = [_safe_number(value) for value in ic_series.tolist() if _safe_number(value) is not None]
        rank_ic_values = [_safe_number(value) for value in rank_ic_series.tolist() if _safe_number(value) is not None]
        valid_groups = int(max(len(ic_values), len(rank_ic_values)))
        skipped_groups = int(valid["timestamp"].nunique()) - valid_groups

    def summarize(values: list[float], prefix: str) -> dict[str, Any]:
        if not values:
            return {
                f"mean{prefix}": None,
                f"median{prefix}": None,
                f"positive{prefix}Ratio": None,
                f"{prefix.lower()}ObservationCount": 0,
            }
        series = pd.Series(values)
        return {
            f"mean{prefix}": _safe_number(series.mean()),
            f"median{prefix}": _safe_number(series.median()),
            f"positive{prefix}Ratio": _safe_number((series > 0).mean()),
            f"{prefix.lower()}ObservationCount": int(len(values)),
        }

    payload = summarize(ic_values, "IC")
    payload.update(summarize(rank_ic_values, "RankIC"))
    payload["validCrossSections"] = valid_groups
    payload["skippedCrossSections"] = skipped_groups
    return payload


def _assign_cross_sectional_quantiles(panel: pd.DataFrame, factor: str, quantiles: int) -> pd.Series:
    values = pd.to_numeric(panel[factor], errors="coerce")
    grouped = values.groupby(panel["timestamp"], sort=False)
    counts = grouped.transform("count")
    uniques = grouped.transform("nunique")
    rank_pct = grouped.rank(method="first", pct=True)
    raw_buckets = (rank_pct * quantiles).fillna(0)
    buckets = raw_buckets.apply(math.ceil).replace(0, pd.NA).clip(lower=1, upper=quantiles)
    return buckets.where((counts >= quantiles) & (uniques >= 2)).astype("Float64")


def _quantile_analysis(panel: pd.DataFrame, factor: str, label: str, quantiles: int) -> dict[str, Any]:
    valid = panel[["timestamp", factor, label]].copy()
    valid[factor] = pd.to_numeric(valid[factor], errors="coerce")
    valid[label] = pd.to_numeric(valid[label], errors="coerce")
    valid = valid.dropna(subset=[factor, label])
    if valid.empty:
        return {
            "quantileCount": quantiles,
            "quantileReturns": {},
            "topBottomSpread": None,
            "monotonicityScore": None,
            "bucketedSampleCount": 0,
        }
    if "factorQuantile" in panel:
        valid["factorQuantile"] = panel.loc[valid.index, "factorQuantile"]
    else:
        valid["factorQuantile"] = _assign_cross_sectional_quantiles(valid, factor, quantiles)
    bucketed = valid.dropna(subset=["factorQuantile"]).copy()
    if bucketed.empty:
        return {
            "quantileCount": quantiles,
            "quantileReturns": {},
            "topBottomSpread": None,
            "monotonicityScore": None,
            "bucketedSampleCount": 0,
        }

    quantile_returns: dict[str, dict[str, Any]] = {}
    means: list[float | None] = []
    for quantile in range(1, quantiles + 1):
        rows = bucketed[bucketed["factorQuantile"] == quantile]
        mean_value = _safe_number(rows[label].mean()) if not rows.empty else None
        means.append(mean_value)
        quantile_returns[f"Q{quantile}"] = {
            "sampleCount": int(len(rows)),
            "meanForwardReturn": mean_value,
            "medianForwardReturn": _safe_number(rows[label].median()) if not rows.empty else None,
        }

    top = means[-1]
    bottom = means[0]
    spread = _safe_number(top - bottom) if top is not None and bottom is not None else None
    adjacent_pairs = [
        (left, right)
        for left, right in zip(means, means[1:], strict=False)
        if left is not None and right is not None
    ]
    monotonicity = _safe_number(sum(1 for left, right in adjacent_pairs if right >= left) / len(adjacent_pairs)) if adjacent_pairs else None
    return {
        "quantileCount": quantiles,
        "quantileReturns": quantile_returns,
        "topBottomSpread": spread,
        "monotonicityScore": monotonicity,
        "bucketedSampleCount": int(len(bucketed)),
    }


def _bucketed_panel(panel: pd.DataFrame, factor: str, label: str, quantiles: int) -> pd.DataFrame:
    valid = panel.copy()
    valid[factor] = pd.to_numeric(valid[factor], errors="coerce")
    valid[label] = pd.to_numeric(valid[label], errors="coerce")
    valid = valid.dropna(subset=[factor, label])
    if valid.empty:
        valid["factorQuantile"] = pd.NA
        return valid
    if "factorQuantile" in panel:
        valid["factorQuantile"] = panel.loc[valid.index, "factorQuantile"]
    else:
        valid["factorQuantile"] = _assign_cross_sectional_quantiles(valid, factor, quantiles)
    return valid.dropna(subset=["factorQuantile"]).copy()


def _profit_factor_and_expectancy(returns: pd.Series) -> dict[str, Any]:
    values = pd.to_numeric(returns, errors="coerce").dropna()
    if values.empty:
        return {"profitFactor": None, "expectancy": None, "winRate": None}
    wins = float(values[values > 0].sum())
    losses = float(values[values < 0].sum())
    profit_factor = _safe_ratio(wins, abs(losses)) if losses < 0 else None
    return {
        "profitFactor": profit_factor,
        "expectancy": _safe_number(values.mean()),
        "winRate": _safe_number((values > 0).mean()),
    }


def _hit_probabilities(panel: pd.DataFrame, horizon: int, sample_mask: pd.Series | None = None) -> dict[str, Any]:
    working = panel if sample_mask is None else panel.loc[sample_mask]
    tp_column = f"hitTpBeforeSl_{horizon}"
    sl_column = f"hitSlBeforeTp_{horizon}"
    if tp_column not in working or sl_column not in working or working.empty:
        return {
            "hitTpBeforeSlProbability": None,
            "hitSlBeforeTpProbability": None,
            "outcomeSampleCount": 0,
        }
    tp_values = working[tp_column].dropna()
    sl_values = working[sl_column].dropna()
    outcome_count = int(max(len(tp_values), len(sl_values)))
    return {
        "hitTpBeforeSlProbability": _safe_number(tp_values.astype(bool).mean()) if len(tp_values) else None,
        "hitSlBeforeTpProbability": _safe_number(sl_values.astype(bool).mean()) if len(sl_values) else None,
        "outcomeSampleCount": outcome_count,
    }


def _spread_by_group(bucketed: pd.DataFrame, label: str, group_column: str, quantiles: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if group_column not in bucketed or bucketed.empty:
        return rows
    for group_value, frame in bucketed.groupby(group_column, dropna=False, sort=True):
        bottom = frame[frame["factorQuantile"] == 1][label]
        top = frame[frame["factorQuantile"] == quantiles][label]
        top_mean = _safe_number(top.mean()) if not top.empty else None
        bottom_mean = _safe_number(bottom.mean()) if not bottom.empty else None
        spread = _safe_number(top_mean - bottom_mean) if top_mean is not None and bottom_mean is not None else None
        rows.append(
            {
                "group": str(group_value),
                "sampleCount": int(len(frame)),
                "topMean": top_mean,
                "bottomMean": bottom_mean,
                "topBottomSpread": spread,
            }
        )
    return rows


def _stability(panel: pd.DataFrame, bucketed: pd.DataFrame, factor: str, label: str, quantiles: int) -> dict[str, Any]:
    if bucketed.empty:
        return {
            "byMonth": [],
            "byPair": [],
            "byRegime": [],
            "byUniverseMembership": [],
            "stableAcrossMonths": False,
            "stableAcrossPairs": False,
            "stableAcrossRegimes": False,
            "concentrationWarnings": ["No bucketed samples available for stability analysis."],
        }
    working = bucketed.copy()
    working["timestampDt"] = pd.to_datetime(working["timestamp"], utc=True, errors="coerce")
    working["month"] = working["timestampDt"].dt.strftime("%Y-%m")
    by_month = _spread_by_group(working, label, "month", quantiles)
    by_pair = _spread_by_group(working, label, "pair", quantiles)
    by_regime = _spread_by_group(working, label, "regimeLabel", quantiles)
    by_universe = _spread_by_group(working, label, "universeMember", quantiles)

    def positive_ratio(rows: list[dict[str, Any]]) -> float | None:
        usable = [row for row in rows if row.get("topBottomSpread") is not None]
        if not usable:
            return None
        return sum(1 for row in usable if float(row["topBottomSpread"]) > 0) / len(usable)

    month_ratio = positive_ratio(by_month)
    pair_ratio = positive_ratio(by_pair)
    regime_ratio = positive_ratio(by_regime)
    concentration_warnings: list[str] = []
    if by_pair:
        total = sum(int(row["sampleCount"]) for row in by_pair)
        largest = max(int(row["sampleCount"]) for row in by_pair)
        if total and largest / total > 0.35:
            concentration_warnings.append("Pair-level samples are concentrated in one pair.")
    if len(by_month) < 3:
        concentration_warnings.append("Fewer than three calendar months available for stability analysis.")
    if len(by_regime) < 2:
        concentration_warnings.append("Fewer than two regimes available for stability analysis.")

    return {
        "byMonth": by_month,
        "byPair": by_pair,
        "byRegime": by_regime,
        "byUniverseMembership": by_universe,
        "stableAcrossMonths": bool(month_ratio is not None and len(by_month) >= 3 and month_ratio >= 0.55),
        "stableAcrossPairs": bool(pair_ratio is not None and len(by_pair) >= 5 and pair_ratio >= 0.55),
        "stableAcrossRegimes": bool(regime_ratio is not None and len(by_regime) >= 2 and regime_ratio >= 0.5),
        "positiveMonthRatio": _safe_number(month_ratio) if month_ratio is not None else None,
        "positivePairRatio": _safe_number(pair_ratio) if pair_ratio is not None else None,
        "positiveRegimeRatio": _safe_number(regime_ratio) if regime_ratio is not None else None,
        "concentrationWarnings": concentration_warnings,
    }


def _horizon_return_stats(panel: pd.DataFrame, horizons: list[int]) -> dict[str, dict[str, Any]]:
    stats: dict[str, dict[str, Any]] = {}
    for horizon in horizons:
        label = f"forwardReturn_{horizon}"
        if label not in panel:
            stats[str(horizon)] = {"mean": None, "median": None, "validLabelCount": 0}
            continue
        values = pd.to_numeric(panel[label], errors="coerce").dropna()
        stats[str(horizon)] = {
            "mean": _safe_number(values.mean()) if not values.empty else None,
            "median": _safe_number(values.median()) if not values.empty else None,
            "validLabelCount": int(len(values)),
        }
    return stats


def _candidate_status(factor_report: dict[str, Any]) -> dict[str, Any]:
    primary = factor_report["primaryHorizonMetrics"]
    stability = factor_report["stability"]
    candidate_checks = {
        "coveragePct>=80": bool(factor_report["coveragePct"] >= 80),
        "validSampleCount>=1000": bool(primary["validSampleCount"] >= 1000),
        "abs(meanRankIC)>=0.02": bool(primary["meanRankIC"] is not None and abs(float(primary["meanRankIC"])) >= 0.02),
        "positiveRankICRatio>=0.55": bool(primary["positiveRankICRatio"] is not None and float(primary["positiveRankICRatio"]) >= 0.55),
        "topBottomSpread>0": bool(primary["topBottomSpread"] is not None and float(primary["topBottomSpread"]) > 0),
        "profitFactor>1.05": bool(primary["profitFactor"] is not None and float(primary["profitFactor"]) > 1.05),
    }
    strict_checks = {
        "abs(meanRankIC)>=0.03": bool(primary["meanRankIC"] is not None and abs(float(primary["meanRankIC"])) >= 0.03),
        "profitFactor>=1.15": bool(primary["profitFactor"] is not None and float(primary["profitFactor"]) >= 1.15),
        "stableAcrossMonths": bool(stability["stableAcrossMonths"]),
        "stableAcrossPairs": bool(stability["stableAcrossPairs"]),
    }
    research_candidate = all(candidate_checks.values())
    strict_candidate = research_candidate and all(strict_checks.values())
    return {
        "researchCandidate": research_candidate,
        "strictCandidate": strict_candidate,
        "checks": candidate_checks,
        "strictChecks": strict_checks,
    }


def _evaluate_one_factor(panel: pd.DataFrame, factor: str, expected_direction: str, config: FactorEvaluationConfig) -> dict[str, Any]:
    warnings: list[str] = []
    factor_values = pd.to_numeric(panel[factor], errors="coerce") if factor in panel else pd.Series(dtype=float)
    sample_count = int(len(panel))
    non_null_count = int(factor_values.notna().sum())
    coverage = round((non_null_count / sample_count) * 100, 4) if sample_count else 0.0
    missing_rate = round(100 - coverage, 4) if sample_count else 100.0
    if factor not in panel:
        warnings.append("Factor column is missing from the panel.")

    primary_horizon = config.primaryHorizon if config.primaryHorizon in config.horizons else config.horizons[0]
    primary_label = f"forwardReturn_{primary_horizon}"
    working_panel = panel.copy()
    if factor in working_panel:
        working_panel["factorQuantile"] = _assign_cross_sectional_quantiles(working_panel, factor, config.quantiles)
    horizon_stats = _horizon_return_stats(working_panel.dropna(subset=[factor]) if factor in working_panel else working_panel, config.horizons)

    horizon_metrics: dict[str, Any] = {}
    for horizon in config.horizons:
        label = f"forwardReturn_{horizon}"
        if factor not in panel or label not in panel:
            horizon_metrics[str(horizon)] = {
                "meanIC": None,
                "medianIC": None,
                "positiveICRatio": None,
                "meanRankIC": None,
                "medianRankIC": None,
                "positiveRankICRatio": None,
                "topBottomSpread": None,
                "profitFactor": None,
                "expectancy": None,
                "validSampleCount": 0,
            }
            warnings.append(f"Metrics unavailable for horizon {horizon}; missing factor or label column.")
            continue

        valid = panel[[factor, label, "timestamp"]].dropna()
        quantile = _quantile_analysis(working_panel, factor, label, config.quantiles)
        bucketed = _bucketed_panel(working_panel, factor, label, config.quantiles)
        top_bucket = bucketed[bucketed["factorQuantile"] == config.quantiles]
        pf = _profit_factor_and_expectancy(top_bucket[label])
        top_mask = pd.Series(working_panel.index.isin(top_bucket.index), index=working_panel.index)
        hit_probability = _hit_probabilities(working_panel, horizon, top_mask)
        ic = _cross_sectional_ic(working_panel, factor, label, config.minIcCrossSectionSize)
        horizon_metrics[str(horizon)] = {
            **ic,
            "forwardReturnMean": _safe_number(valid[label].mean()) if not valid.empty else None,
            "forwardReturnMedian": _safe_number(valid[label].median()) if not valid.empty else None,
            "quantileAnalysis": quantile,
            "topQuantileReturn": quantile["quantileReturns"].get(f"Q{config.quantiles}", {}).get("meanForwardReturn"),
            "bottomQuantileReturn": quantile["quantileReturns"].get("Q1", {}).get("meanForwardReturn"),
            "topBottomSpread": quantile["topBottomSpread"],
            "monotonicityScore": quantile["monotonicityScore"],
            **hit_probability,
            **pf,
            "validSampleCount": int(len(valid)),
            "bucketedSampleCount": int(quantile["bucketedSampleCount"]),
        }

    primary_metrics = horizon_metrics[str(primary_horizon)]
    primary_bucketed = _bucketed_panel(working_panel, factor, primary_label, config.quantiles) if factor in working_panel and primary_label in working_panel else pd.DataFrame()
    stability = _stability(working_panel, primary_bucketed, factor, primary_label, config.quantiles)
    factor_report = {
        "factorId": factor,
        "expectedDirection": expected_direction,
        "factorDirectionAdjusted": False,
        "coveragePct": coverage,
        "missingRate": missing_rate,
        "sampleCount": sample_count,
        "nonNullCount": non_null_count,
        "forwardReturnStats": horizon_stats,
        "horizonMetrics": horizon_metrics,
        "primaryHorizon": primary_horizon,
        "primaryHorizonMetrics": primary_metrics,
        "stability": stability,
        "warnings": warnings + stability.get("concentrationWarnings", []),
        "researchOnly": True,
        "notTradeReady": True,
        "notDryRunReady": True,
    }
    factor_report["candidateStatus"] = _candidate_status(factor_report)
    return factor_report


def _candidate_payload(factor_report: dict[str, Any]) -> dict[str, Any]:
    primary = factor_report["primaryHorizonMetrics"]
    return {
        "factorId": factor_report["factorId"],
        "primaryHorizon": factor_report["primaryHorizon"],
        "coveragePct": factor_report["coveragePct"],
        "validSampleCount": primary["validSampleCount"],
        "meanRankIC": primary["meanRankIC"],
        "positiveRankICRatio": primary["positiveRankICRatio"],
        "topBottomSpread": primary["topBottomSpread"],
        "profitFactor": primary["profitFactor"],
        "expectancy": primary["expectancy"],
        "stableAcrossMonths": factor_report["stability"]["stableAcrossMonths"],
        "stableAcrossPairs": factor_report["stability"]["stableAcrossPairs"],
        "strictCandidate": factor_report["candidateStatus"]["strictCandidate"],
        "status": ["research_only", "not_trade_ready", "not_dry_run_ready"],
        "warnings": factor_report["warnings"],
    }


def evaluate_factors(panel: pd.DataFrame, config: FactorEvaluationConfig | None = None) -> dict[str, Any]:
    config = config or FactorEvaluationConfig()
    warnings = [
        "Research-only factor evaluation. No strategy code, backtest, Dry-run, API key, account read, order, or auto trading was used.",
        "Forward labels are evaluation-only and do not feed back into factor computation or sample selection.",
    ]
    factor_columns = manual_factor_output_columns()
    factor_specs = {item["factorId"]: item for item in build_manual_factor_library_v01()}
    if panel.empty:
        return {
            "reportId": "v13_4_22_factor_evaluation_report",
            "version": "V13.4.22",
            "status": "blocked_empty_panel",
            "factorCount": len(factor_columns),
            "evaluatedFactorCount": 0,
            "sampleCount": 0,
            "validLabelCount": 0,
            "config": config.__dict__,
            "factorReports": [],
            "candidateFactors": [],
            "warnings": warnings + ["Input panel was empty."],
            "dryRunApproved": False,
            "liveTradingApproved": False,
            "generatedAt": utc_now(),
        }

    factor_reports = [
        _evaluate_one_factor(panel, factor, factor_specs.get(factor, {}).get("expectedDirection", "unknown"), config)
        for factor in factor_columns
    ]
    candidate_factors = [_candidate_payload(report) for report in factor_reports if report["candidateStatus"]["researchCandidate"]]
    primary_horizon = config.primaryHorizon if config.primaryHorizon in config.horizons else config.horizons[0]
    primary_label = f"forwardReturn_{primary_horizon}"
    valid_label_count = int(pd.to_numeric(panel[primary_label], errors="coerce").notna().sum()) if primary_label in panel else 0

    def top_by(field: str, reverse: bool = True, abs_value: bool = False) -> list[dict[str, Any]]:
        rows = []
        for report in factor_reports:
            value = report["primaryHorizonMetrics"].get(field)
            if value is None:
                continue
            rows.append({"factorId": report["factorId"], field: value})
        return sorted(rows, key=lambda row: abs(float(row[field])) if abs_value else float(row[field]), reverse=reverse)[:8]

    low_coverage = sorted(
        [{"factorId": report["factorId"], "coveragePct": report["coveragePct"]} for report in factor_reports],
        key=lambda row: row["coveragePct"],
    )[:8]
    unstable = [
        {
            "factorId": report["factorId"],
            "stableAcrossMonths": report["stability"]["stableAcrossMonths"],
            "stableAcrossPairs": report["stability"]["stableAcrossPairs"],
            "stableAcrossRegimes": report["stability"]["stableAcrossRegimes"],
            "warnings": report["warnings"],
        }
        for report in factor_reports
        if not report["stability"]["stableAcrossMonths"] or not report["stability"]["stableAcrossPairs"]
    ]

    return {
        "reportId": "v13_4_22_factor_evaluation_report",
        "version": "V13.4.22",
        "status": "success",
        "factorCount": len(factor_columns),
        "evaluatedFactorCount": len(factor_reports),
        "sampleCount": int(len(panel)),
        "validLabelCount": valid_label_count,
        "horizons": config.horizons,
        "primaryHorizon": primary_horizon,
        "quantiles": config.quantiles,
        "tpPct": config.tpPct,
        "slPct": config.slPct,
        "factorReports": factor_reports,
        "candidateFactors": candidate_factors,
        "topFactorsByRankIC": top_by("meanRankIC", abs_value=True),
        "topFactorsBySpread": top_by("topBottomSpread"),
        "topFactorsByProfitFactor": top_by("profitFactor"),
        "lowCoverageFactors": low_coverage,
        "unstableFactors": unstable,
        "warnings": warnings,
        "dryRunApproved": False,
        "liveTradingApproved": False,
        "nextStepRecommendation": "V13.4.23 should implement a benchmark strategy suite or design factor-based hypotheses only after research review.",
        "generatedAt": utc_now(),
    }
