"""Generate V13.5.14 historical robustness expansion report.

This report fixes the active V13.5.7 pool parameters and expands historical
diagnostics across time, pair, regime, factor, and cross-market public-data
contexts. It is historical research only. It is not forward validation,
exchange Dry-run, live trading, or an order-generation path.
"""

from __future__ import annotations

import argparse
import json
import math
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean, pstdev
from typing import Any

import pandas as pd

from alphapilot.cross_market.public_market_data import summarize_rows
from alphapilot.derivatives.feature_panel import DEFAULT_DATA_DIR, build_derivatives_feature_panel
from alphapilot.factors.alpha101_style_overlay import ALPHA101_STYLE_FACTOR_COLUMNS, add_alpha101_style_factors
from alphapilot.ml_gate.high_reward_event_setups import add_high_reward_event_setups
from alphapilot.ml_gate.high_reward_triple_barrier import build_high_reward_labeled_events
from alphapilot.ml_gate.probability_gate import evaluate_trades
from alphapilot.ml_gate.triple_barrier import BarrierConfig
from alphapilot.reports.generate_v13_5_1_expanded_relaxed_research_report import discover_local_pairs
from alphapilot.reports.generate_v13_5_7_external_alpha_overlay_report import _apply_overlay_filter
from alphapilot.reports.generate_v13_5_12_active_alpha_overlay_replay_report import (
    _load_active_pool_id,
    _parse_pool_id,
    _to_signal_rows,
)
from alphapilot.reports.generate_v13_5_derivatives_ml_strategy_report import _json_ready, write_json, write_text


VERSION = "V13.5.14"
REPORT_ID = "v13_5_14_historical_robustness_expansion_report"
DEFAULT_CONTROL_TOWER_REPORT = Path("reports/v13_5_9_strategy_control_tower_report.json")
DEFAULT_CROSS_MARKET_CACHE_DIR = Path("user_data/cross_market_data/v13_5_11")
DEFAULT_OUTPUT_REPORT = Path("reports/v13_5_14_historical_robustness_expansion_report.json")
DEFAULT_OUTPUT_SUMMARY = Path("reports/v13_5_14_historical_robustness_expansion_summary.md")
DEFAULT_OUTPUT_SIGNAL_LOG = Path("reports/v13_5_14_active_strategy_historical_signal_log.json")


def _round(value: Any, digits: int = 6) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return round(number, digits)


def _metric_row(label: str, events: pd.DataFrame) -> dict[str, Any]:
    metrics = evaluate_trades(events)
    return {"label": label, **metrics}


def _metrics_by_group(events: pd.DataFrame, column: str, limit: int = 40) -> list[dict[str, Any]]:
    if events.empty or column not in events.columns:
        return []
    rows: list[dict[str, Any]] = []
    for value, group in events.groupby(column, dropna=False):
        rows.append(_metric_row(str(value), group))
    return sorted(
        rows,
        key=lambda row: (row.get("tradeCount") or 0, row.get("profitFactor") or 0),
        reverse=True,
    )[:limit]


def _time_splits(events: pd.DataFrame) -> dict[str, Any]:
    if events.empty:
        return {
            "early60": _metric_row("early60", events),
            "middle20": _metric_row("middle20", events),
            "recent20": _metric_row("recent20", events),
        }
    ordered = events.sort_values("signalDate").reset_index(drop=True)
    early_end = int(len(ordered) * 0.6)
    middle_end = int(len(ordered) * 0.8)
    return {
        "early60": _metric_row("early60", ordered.iloc[:early_end].copy()),
        "middle20": _metric_row("middle20", ordered.iloc[early_end:middle_end].copy()),
        "recent20": _metric_row("recent20", ordered.iloc[middle_end:].copy()),
    }


def _year_splits(events: pd.DataFrame) -> list[dict[str, Any]]:
    if events.empty or "signalDate" not in events.columns:
        return []
    working = events.copy()
    working["signalYear"] = pd.to_datetime(working["signalDate"], utc=True, errors="coerce").dt.strftime("%Y")
    return _metrics_by_group(working, "signalYear")


def _quarter_splits(events: pd.DataFrame) -> list[dict[str, Any]]:
    if events.empty or "signalDate" not in events.columns:
        return []
    working = events.copy()
    dates = pd.to_datetime(working["signalDate"], utc=True, errors="coerce")
    working["signalQuarter"] = dates.dt.tz_convert(None).dt.to_period("Q").astype(str)
    return _metrics_by_group(working, "signalQuarter")


def _month_distribution(events: pd.DataFrame, limit: int = 24) -> list[dict[str, Any]]:
    if events.empty or "signalDate" not in events.columns:
        return []
    working = events.copy()
    working["signalMonth"] = pd.to_datetime(working["signalDate"], utc=True, errors="coerce").dt.strftime("%Y-%m")
    total = len(working)
    rows: list[dict[str, Any]] = []
    for value, count in working["signalMonth"].value_counts().head(limit).items():
        rows.append({"value": str(value), "count": int(count), "sharePct": _round(count / total * 100, 4)})
    return rows


def _bucket_column(events: pd.DataFrame, column: str, target: str) -> pd.DataFrame:
    working = events.copy()
    if working.empty or column not in working.columns:
        working[target] = "unknown"
        return working
    values = pd.to_numeric(working[column], errors="coerce")
    valid = values.dropna()
    if valid.empty or valid.nunique() < 3:
        working[target] = values.apply(lambda value: "known" if pd.notna(value) else "unknown")
        return working
    low = valid.quantile(0.33)
    high = valid.quantile(0.66)

    def bucket(value: float) -> str:
        if pd.isna(value):
            return "unknown"
        if value <= low:
            return "low"
        if value >= high:
            return "high"
        return "middle"

    working[target] = values.apply(bucket)
    return working


def _factor_snapshot(events: pd.DataFrame) -> dict[str, Any]:
    output: dict[str, Any] = {"eventCount": int(len(events)), "columns": {}}
    for column in ALPHA101_STYLE_FACTOR_COLUMNS:
        if column not in events.columns:
            output["columns"][column] = {"availabilityPct": 0.0, "mean": None, "median": None}
            continue
        series = pd.to_numeric(events[column], errors="coerce")
        output["columns"][column] = {
            "availabilityPct": _round(series.notna().mean() * 100, 4),
            "mean": _round(series.mean()),
            "median": _round(series.median()),
        }
    return output


def _factor_outcome_separation(events: pd.DataFrame) -> list[dict[str, Any]]:
    """Lightweight auditable factor extraction, not a predictive trading model."""

    if events.empty or "rMultiple" not in events.columns:
        return []
    rows: list[dict[str, Any]] = []
    winners = events[pd.to_numeric(events["rMultiple"], errors="coerce") > 0]
    losers = events[pd.to_numeric(events["rMultiple"], errors="coerce") <= 0]
    for column in ALPHA101_STYLE_FACTOR_COLUMNS:
        if column not in events.columns:
            continue
        series = pd.to_numeric(events[column], errors="coerce")
        if series.notna().sum() < 20:
            continue
        winner_values = pd.to_numeric(winners[column], errors="coerce").dropna() if not winners.empty else pd.Series(dtype=float)
        loser_values = pd.to_numeric(losers[column], errors="coerce").dropna() if not losers.empty else pd.Series(dtype=float)
        if winner_values.empty or loser_values.empty:
            continue
        winner_mean = float(winner_values.mean())
        loser_mean = float(loser_values.mean())
        pooled_std = float(series.std()) if series.std() else 0.0
        separation = (winner_mean - loser_mean) / pooled_std if pooled_std > 0 else None
        rows.append(
            {
                "factor": column,
                "availabilityPct": _round(series.notna().mean() * 100, 4),
                "winnerMean": _round(winner_mean),
                "loserMean": _round(loser_mean),
                "standardizedSeparation": _round(separation),
                "interpretation": "positive means winners had higher average factor values",
            }
        )
    return sorted(rows, key=lambda row: abs(row.get("standardizedSeparation") or 0), reverse=True)


def _add_market_state_labels(events: pd.DataFrame) -> pd.DataFrame:
    working = events.copy()
    if working.empty:
        working["marketState"] = "unknown"
        return working
    btc_regime = working.get("btc_regime", pd.Series(["unknown"] * len(working), index=working.index)).astype(str)
    btc_return_3 = pd.to_numeric(working.get("btc_return_3", pd.Series([None] * len(working), index=working.index)), errors="coerce")
    relative_return_6 = pd.to_numeric(
        working.get("relative_return_6", pd.Series([None] * len(working), index=working.index)),
        errors="coerce",
    )
    cs_return_rank = pd.to_numeric(
        working.get("cs_return_12_rank", pd.Series([None] * len(working), index=working.index)),
        errors="coerce",
    )
    labels: list[str] = []
    for index in working.index:
        if pd.notna(btc_return_3.loc[index]) and btc_return_3.loc[index] <= -0.04:
            labels.append("btc_sharp_drop")
        elif btc_regime.loc[index] == "bull":
            labels.append("bull")
        elif btc_regime.loc[index] == "bear":
            labels.append("bear")
        elif pd.notna(relative_return_6.loc[index]) and relative_return_6.loc[index] > 0.04 and pd.notna(cs_return_rank.loc[index]) and cs_return_rank.loc[index] >= 0.75:
            labels.append("alt_rotation_strength")
        elif btc_regime.loc[index] == "sideways":
            labels.append("sideways")
        else:
            labels.append("unknown")
    working["marketState"] = labels
    return working


def _stress_metrics(events: pd.DataFrame) -> list[dict[str, Any]]:
    if events.empty or "netReturnPct" not in events.columns:
        return []
    scenarios = [
        {"scenario": "base_recorded", "extraCostPct": 0.0, "delayPenaltyPct": 0.0, "gapLossMultiplier": 1.0},
        {"scenario": "fee_slippage_plus_0_10pct", "extraCostPct": 0.10, "delayPenaltyPct": 0.0, "gapLossMultiplier": 1.0},
        {"scenario": "fee_slippage_plus_0_30pct", "extraCostPct": 0.30, "delayPenaltyPct": 0.0, "gapLossMultiplier": 1.0},
        {"scenario": "entry_delay_plus_0_20pct", "extraCostPct": 0.0, "delayPenaltyPct": 0.20, "gapLossMultiplier": 1.0},
        {"scenario": "extreme_gap_losses_1_25x", "extraCostPct": 0.0, "delayPenaltyPct": 0.0, "gapLossMultiplier": 1.25},
        {"scenario": "combined_conservative", "extraCostPct": 0.30, "delayPenaltyPct": 0.20, "gapLossMultiplier": 1.25},
    ]
    base_returns = pd.to_numeric(events["netReturnPct"], errors="coerce").fillna(0.0)
    output: list[dict[str, Any]] = []
    for scenario in scenarios:
        adjusted = base_returns.copy() - float(scenario["extraCostPct"]) - float(scenario["delayPenaltyPct"])
        loss_mask = adjusted < 0
        adjusted.loc[loss_mask] = adjusted.loc[loss_mask] * float(scenario["gapLossMultiplier"])
        wins = adjusted[adjusted > 0]
        losses = adjusted[adjusted <= 0]
        gross_win = float(wins.sum()) if not wins.empty else 0.0
        gross_loss = abs(float(losses.sum())) if not losses.empty else 0.0
        output.append(
            {
                **scenario,
                "tradeCount": int(len(adjusted)),
                "winRatePct": _round((len(wins) / len(adjusted) * 100) if len(adjusted) else None, 4),
                "profitFactor": _round((gross_win / gross_loss) if gross_loss else None, 6),
                "totalReturnPctSimpleSum": _round(float(adjusted.sum()), 6),
                "averageReturnPct": _round(float(adjusted.mean()), 6) if len(adjusted) else None,
                "maxSingleLossPct": _round(float(adjusted.min()), 6) if len(adjusted) else None,
            }
        )
    return output


def _walk_forward_review(events: pd.DataFrame) -> dict[str, Any]:
    splits = _time_splits(events)
    train = splits["early60"]
    validation = splits["middle20"]
    test = splits["recent20"]
    gate_warnings: list[str] = []
    if (validation.get("profitFactor") or 0) < 1:
        gate_warnings.append("validation_profit_factor_below_1")
    if (test.get("profitFactor") or 0) < 0.9:
        gate_warnings.append("test_profit_factor_below_0_9")
    if (test.get("tradeCount") or 0) < 16:
        gate_warnings.append("test_trade_count_below_16")
    if (train.get("winRatePct") or 0) - (test.get("winRatePct") or 0) > 20:
        gate_warnings.append("train_test_win_rate_decay_above_20pct")
    return {
        "method": "chronological_60_20_20_fixed_parameters",
        "train": train,
        "validation": validation,
        "test": test,
        "gateWarnings": gate_warnings,
        "passed": not gate_warnings,
        "note": "No thresholds are selected from these splits in V13.5.14; this is a robustness review only.",
    }


def _data_coverage(events: pd.DataFrame, loaded_pairs: list[str], missing_pairs: list[str]) -> dict[str, Any]:
    if events.empty:
        return {
            "eventCount": 0,
            "eventPairCount": 0,
            "loadedPairCount": len(loaded_pairs),
            "missingPairs": missing_pairs,
            "firstSignalAt": None,
            "lastSignalAt": None,
            "uniqueMonths": 0,
        }
    dates = pd.to_datetime(events["signalDate"], utc=True, errors="coerce")
    return {
        "eventCount": int(len(events)),
        "eventPairCount": int(events["pair"].nunique()) if "pair" in events.columns else 0,
        "loadedPairCount": len(loaded_pairs),
        "missingPairs": missing_pairs,
        "firstSignalAt": dates.min().isoformat() if dates.notna().any() else None,
        "lastSignalAt": dates.max().isoformat() if dates.notna().any() else None,
        "uniqueMonths": int(dates.dt.strftime("%Y-%m").nunique()) if dates.notna().any() else 0,
    }


def _load_cross_market_cache(cache_dir: Path) -> list[dict[str, Any]]:
    if not cache_dir.exists():
        return []
    rows: list[dict[str, Any]] = []
    for path in sorted(cache_dir.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            rows.append({"cacheFile": str(path), "status": "failed", "error": str(exc)})
            continue
        metadata = payload.get("metadata") or {}
        market_rows = payload.get("rows") or []
        summary = summarize_rows(market_rows)
        factor_context = _cross_market_factor_context(market_rows)
        rows.append(
            {
                "cacheFile": str(path),
                "status": "ok" if market_rows else "empty",
                "metadata": metadata,
                "summary": summary,
                "factorContext": factor_context,
                "rawDataCommittedToGit": False,
            }
        )
    return rows


def _cross_market_factor_context(rows: list[dict[str, Any]]) -> dict[str, Any]:
    closes: list[float] = []
    volumes: list[float] = []
    for row in rows:
        close = row.get("close")
        if close is None:
            continue
        closes.append(float(close))
        volume = row.get("volume")
        if volume is not None:
            volumes.append(float(volume))
    if len(closes) < 2:
        return {
            "recent20ReturnPct": None,
            "recent60ReturnPct": None,
            "realizedVol60Pct": None,
            "volumeRatio20To60": None,
        }
    returns = [(closes[index] / closes[index - 1]) - 1 for index in range(1, len(closes)) if closes[index - 1] > 0]
    recent20_return = (closes[-1] / closes[-21] - 1) * 100 if len(closes) >= 21 and closes[-21] > 0 else None
    recent60_return = (closes[-1] / closes[-61] - 1) * 100 if len(closes) >= 61 and closes[-61] > 0 else None
    recent_returns = returns[-60:]
    realized_vol = pstdev(recent_returns) * math.sqrt(252) * 100 if len(recent_returns) > 2 else None
    volume_ratio = None
    if len(volumes) >= 60:
        avg20 = mean(volumes[-20:])
        avg60 = mean(volumes[-60:])
        volume_ratio = avg20 / avg60 if avg60 else None
    return {
        "recent20ReturnPct": _round(recent20_return),
        "recent60ReturnPct": _round(recent60_return),
        "realizedVol60AnnualizedPct": _round(realized_vol),
        "volumeRatio20To60": _round(volume_ratio),
    }


def _summarize_cross_market_by_market(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        market = ((item.get("metadata") or {}).get("market")) or "unknown"
        grouped.setdefault(market, []).append(item)
    output: list[dict[str, Any]] = []
    for market, values in sorted(grouped.items()):
        valid = [row for row in values if row.get("status") == "ok"]
        output.append(
            {
                "market": market,
                "symbolCount": len(values),
                "validSymbolCount": len(valid),
                "averageDataQualityScore": _round(
                    mean([(row.get("summary") or {}).get("dataQualityScore", 0) for row in valid])
                    if valid
                    else None
                ),
                "averageRecent60ReturnPct": _round(
                    mean(
                        [
                            (row.get("factorContext") or {}).get("recent60ReturnPct")
                            for row in valid
                            if (row.get("factorContext") or {}).get("recent60ReturnPct") is not None
                        ]
                    )
                    if any(
                        (row.get("factorContext") or {}).get("recent60ReturnPct") is not None for row in valid
                    )
                    else None
                ),
                "averageRealizedVol60AnnualizedPct": _round(
                    mean(
                        [
                            (row.get("factorContext") or {}).get("realizedVol60AnnualizedPct")
                            for row in valid
                            if (row.get("factorContext") or {}).get("realizedVol60AnnualizedPct") is not None
                        ]
                    )
                    if any(
                        (row.get("factorContext") or {}).get("realizedVol60AnnualizedPct") is not None for row in valid
                    )
                    else None
                ),
            }
        )
    return output


def _build_active_events(control_tower_report: Path, data_dir: Path) -> tuple[dict[str, Any], pd.DataFrame, dict[str, Any]]:
    pool_id = _load_active_pool_id(control_tower_report)
    pool = _parse_pool_id(pool_id)
    timeframe = pool["timeframe"]
    pairs = discover_local_pairs(timeframe, data_dir=data_dir)
    panel_result = build_derivatives_feature_panel(pairs=pairs, timeframe=timeframe, data_dir=data_dir)
    panel = add_high_reward_event_setups(add_alpha101_style_factors(panel_result.rows))
    barrier_config = BarrierConfig(
        stop_loss_pct=pool["stopLossPct"],
        reward_r_multiple=pool["rewardRMultiple"],
        horizon_bars=pool["horizonBars"],
        fee_rate_roundtrip=0.001,
        slippage_rate_roundtrip=0.001,
    )
    all_events = build_high_reward_labeled_events(panel, barrier_config)
    selected = all_events[_apply_overlay_filter(all_events, pool["overlayId"])].copy()
    selected["activePoolId"] = pool_id
    context = {
        "activePool": {"poolId": pool_id, **pool},
        "dataSource": {
            "localPublicDataDir": str(data_dir),
            "loadedPairs": panel_result.loaded_pairs,
            "missingPairs": panel_result.missing_pairs,
            "missingOptionalSources": panel_result.missing_optional_sources,
            "publicDataOnly": True,
        },
        "barrierConfig": {
            "stopLossPct": pool["stopLossPct"],
            "rewardRMultiple": pool["rewardRMultiple"],
            "horizonBars": pool["horizonBars"],
            "feeRateRoundtrip": barrier_config.fee_rate_roundtrip,
            "slippageRateRoundtrip": barrier_config.slippage_rate_roundtrip,
        },
        "allHighRewardEventCount": int(len(all_events)),
    }
    return pool, selected, context


def _robustness_decision(events: pd.DataFrame, overall_metrics: dict[str, Any], time_splits: dict[str, Any]) -> dict[str, Any]:
    coverage = {
        "tradeCount": int(overall_metrics.get("tradeCount") or 0),
        "uniquePairs": int(events["pair"].nunique()) if not events.empty and "pair" in events.columns else 0,
        "uniqueMonths": int(pd.to_datetime(events["signalDate"], utc=True).dt.strftime("%Y-%m").nunique())
        if not events.empty
        else 0,
        "recent20TradeCount": int((time_splits.get("recent20") or {}).get("tradeCount") or 0),
    }
    warnings: list[str] = []
    pass_checks: list[str] = []
    if coverage["tradeCount"] >= 100:
        pass_checks.append("trade_count_at_least_100")
    else:
        warnings.append("trade_count_below_100")
    if coverage["uniquePairs"] >= 12:
        pass_checks.append("pair_coverage_at_least_12")
    else:
        warnings.append("pair_coverage_below_12")
    if coverage["uniqueMonths"] >= 8:
        pass_checks.append("month_coverage_at_least_8")
    else:
        warnings.append("month_coverage_below_8")
    if (overall_metrics.get("profitFactor") or 0) >= 1.5:
        pass_checks.append("historical_profit_factor_at_least_1_5")
    else:
        warnings.append("historical_profit_factor_below_1_5")
    if (overall_metrics.get("winRatePct") or 0) >= 45:
        pass_checks.append("historical_win_rate_at_least_45")
    else:
        warnings.append("historical_win_rate_below_45")
    if (time_splits.get("recent20") or {}).get("profitFactor", 0) >= 0.9:
        pass_checks.append("recent20_profit_factor_at_least_0_9")
    else:
        warnings.append("recent20_profit_factor_below_0_9")
    historical_watch_passed = len(warnings) == 0
    return {
        "historicalRobustnessExpansionCompleted": True,
        "activeStrategyFixedParameters": True,
        "historicalRobustnessWatchPassed": historical_watch_passed,
        "passChecks": pass_checks,
        "warnings": warnings,
        "coverage": coverage,
        "forwardValidationStillRequired": True,
        "readyForExchangeDryRunReview": False,
        "exchangeDryRunApproved": False,
        "liveTradingApproved": False,
        "reason": (
            "historical_robustness_expanded_but_forward_samples_still_required"
            if historical_watch_passed
            else "historical_robustness_has_warnings_and_forward_samples_still_required"
        ),
    }


def build_historical_robustness_expansion(
    *,
    control_tower_report: Path = DEFAULT_CONTROL_TOWER_REPORT,
    data_dir: Path = DEFAULT_DATA_DIR,
    cross_market_cache_dir: Path = DEFAULT_CROSS_MARKET_CACHE_DIR,
) -> dict[str, Any]:
    pool, events, context = _build_active_events(control_tower_report, data_dir)
    overall_metrics = evaluate_trades(events)
    time_splits = _time_splits(events)
    event_bucket_inputs = _bucket_column(events, "atr_pct", "atrPctBucket")
    event_bucket_inputs = _bucket_column(event_bucket_inputs, "volume_ratio", "volumeRatioBucket")
    event_bucket_inputs = _bucket_column(event_bucket_inputs, "alpha_liquidity_quality", "liquidityQualityBucket")
    market_state_events = _add_market_state_labels(event_bucket_inputs)
    cross_market_items = _load_cross_market_cache(cross_market_cache_dir)
    decision = _robustness_decision(events, overall_metrics, time_splits)
    generated_at = datetime.now(UTC).isoformat()
    return {
        "version": VERSION,
        "reportId": REPORT_ID,
        "generatedAt": generated_at,
        "status": "completed",
        "objective": (
            "Use more historical crypto and cross-market public samples to test the fixed active "
            "strategy context without optimizing thresholds or granting execution authority."
        ),
        "activePool": context["activePool"],
        "dataSource": {
            **context["dataSource"],
            "crossMarketCacheDir": str(cross_market_cache_dir),
            "crossMarketRawDataCommittedToGit": False,
        },
        "barrierConfig": context["barrierConfig"],
        "eventSummary": {
            "allHighRewardEventCount": context["allHighRewardEventCount"],
            "activeOverlayEventCount": int(len(events)),
            "metrics": overall_metrics,
            "coverage": _data_coverage(events, context["dataSource"]["loadedPairs"], context["dataSource"]["missingPairs"]),
        },
        "historicalRobustness": {
            "timeSplits": time_splits,
            "walkForwardReview": _walk_forward_review(events),
            "stressTests": _stress_metrics(events),
            "yearSplits": _year_splits(events),
            "quarterSplits": _quarter_splits(events),
            "pairSplits": _metrics_by_group(events, "pair"),
            "btcRegimeSplits": _metrics_by_group(events, "btc_regime"),
            "marketStateSplits": _metrics_by_group(market_state_events, "marketState"),
            "exitReasonSplits": _metrics_by_group(events, "exitReason"),
            "atrPctBucketSplits": _metrics_by_group(market_state_events, "atrPctBucket"),
            "volumeRatioBucketSplits": _metrics_by_group(market_state_events, "volumeRatioBucket"),
            "liquidityQualityBucketSplits": _metrics_by_group(market_state_events, "liquidityQualityBucket"),
            "monthDistribution": _month_distribution(events),
            "factorSnapshot": _factor_snapshot(events),
            "factorOutcomeSeparation": _factor_outcome_separation(events),
        },
        "crossMarketContext": {
            "source": "v13_5_11_yahoo_public_chart_cache",
            "cacheDir": str(cross_market_cache_dir),
            "symbolCount": len(cross_market_items),
            "validSymbolCount": len([item for item in cross_market_items if item.get("status") == "ok"]),
            "symbols": cross_market_items,
            "byMarket": _summarize_cross_market_by_market(cross_market_items),
            "usageBoundary": {
                "usedForFactorInspirationOnly": True,
                "usedForCryptoExecution": False,
                "normalizationRequiredBeforeModelTraining": True,
            },
        },
        "signalRows": _to_signal_rows(events, context["activePool"]["poolId"]),
        "decision": decision,
        "recommendations": [
            "Keep the active pool parameters fixed; do not tune thresholds against this expanded historical report.",
            "Use cross-market public data as factor and regime inspiration only until normalization and separate validation are added.",
            "Continue waiting for closed post-selection 4h forward samples before any exchange Dry-run review.",
            "If historical warnings appear, treat them as robustness risks, not as a reason to lower the 2R target.",
        ],
        "safetyBoundary": {
            "usesPublicLocalDataOnly": True,
            "usesApiKey": False,
            "tradeApiUsed": False,
            "withdrawApiUsed": False,
            "readsRealAccount": False,
            "readsRealPositions": False,
            "createsOrders": False,
            "autoTrading": False,
            "exchangeDryRunApproved": False,
            "liveTradingApproved": False,
        },
    }


def build_summary(report: dict[str, Any]) -> str:
    active = report["activePool"]
    metrics = report["eventSummary"]["metrics"]
    coverage = report["eventSummary"]["coverage"]
    decision = report["decision"]
    cross = report["crossMarketContext"]
    lines = [
        "# V13.5.14 Historical Robustness Expansion",
        "",
        "This report expands historical diagnostics for the fixed active V13.5.7 strategy.",
        "It is historical research only. It is not forward validation, exchange Dry-run, or live trading.",
        "",
        "## Active Pool",
        "",
        f"- Pool id: `{active['poolId']}`",
        f"- Timeframe: `{active['timeframe']}`",
        f"- Overlay id: `{active['overlayId']}`",
        f"- Stop loss: `{active['stopLossPct']}`",
        f"- Target R: `{active['rewardRMultiple']}`",
        f"- Horizon bars: `{active['horizonBars']}`",
        "",
        "## Historical Event Metrics",
        "",
        f"- Active overlay events: `{report['eventSummary']['activeOverlayEventCount']}`",
        f"- Trade count: `{metrics.get('tradeCount')}`",
        f"- Win rate: `{metrics.get('winRatePct')}`",
        f"- Profit factor: `{metrics.get('profitFactor')}`",
        f"- Reward/risk: `{metrics.get('rewardRiskRatio')}`",
        f"- Total return: `{metrics.get('totalReturnPct')}`",
        f"- Max drawdown: `{metrics.get('maxDrawdownPct')}`",
        f"- Event pairs: `{coverage.get('eventPairCount')}`",
        f"- Unique months: `{coverage.get('uniqueMonths')}`",
        f"- Range: `{coverage.get('firstSignalAt')}` to `{coverage.get('lastSignalAt')}`",
        "",
        "## Robustness Slices",
        "",
    ]
    for label, row in report["historicalRobustness"]["timeSplits"].items():
        lines.append(
            f"- `{label}`: trades=`{row.get('tradeCount')}`, winRate=`{row.get('winRatePct')}`, "
            f"PF=`{row.get('profitFactor')}`, RR=`{row.get('rewardRiskRatio')}`"
        )
    walk = report["historicalRobustness"]["walkForwardReview"]
    lines.extend(
        [
            "",
            "## Walk-Forward Review",
            "",
            f"- Method: `{walk['method']}`",
            f"- Passed: `{walk['passed']}`",
            f"- Gate warnings: `{', '.join(walk['gateWarnings']) or 'none'}`",
            f"- Train PF: `{walk['train'].get('profitFactor')}`",
            f"- Validation PF: `{walk['validation'].get('profitFactor')}`",
            f"- Test PF: `{walk['test'].get('profitFactor')}`",
            "",
            "## Market-State Slices",
            "",
        ]
    )
    for row in report["historicalRobustness"]["marketStateSplits"]:
        lines.append(
            f"- `{row.get('label')}`: trades=`{row.get('tradeCount')}`, "
            f"winRate=`{row.get('winRatePct')}`, PF=`{row.get('profitFactor')}`, "
            f"return=`{row.get('totalReturnPct')}`"
        )
    lines.extend(["", "## Stress Tests", ""])
    for row in report["historicalRobustness"]["stressTests"]:
        lines.append(
            f"- `{row.get('scenario')}`: winRate=`{row.get('winRatePct')}`, "
            f"PF=`{row.get('profitFactor')}`, simpleReturn=`{row.get('totalReturnPctSimpleSum')}`, "
            f"maxSingleLoss=`{row.get('maxSingleLossPct')}`"
        )
    lines.extend(["", "## Factor Outcome Separation", ""])
    for row in report["historicalRobustness"]["factorOutcomeSeparation"][:10]:
        lines.append(
            f"- `{row.get('factor')}`: availability=`{row.get('availabilityPct')}`, "
            f"winnerMean=`{row.get('winnerMean')}`, loserMean=`{row.get('loserMean')}`, "
            f"separation=`{row.get('standardizedSeparation')}`"
        )
    lines.extend(["", "## Top Pair Slices", ""])
    for row in report["historicalRobustness"]["pairSplits"][:10]:
        lines.append(
            f"- `{row.get('label')}`: trades=`{row.get('tradeCount')}`, "
            f"winRate=`{row.get('winRatePct')}`, PF=`{row.get('profitFactor')}`, "
            f"return=`{row.get('totalReturnPct')}`"
        )
    lines.extend(["", "## Cross-Market Public Context", ""])
    lines.append(f"- Cache dir: `{cross['cacheDir']}`")
    lines.append(f"- Symbols loaded: `{cross['validSymbolCount']}` / `{cross['symbolCount']}`")
    for row in cross["byMarket"]:
        lines.append(
            f"- `{row['market']}`: valid=`{row['validSymbolCount']}`, "
            f"avgQuality=`{row['averageDataQualityScore']}`, "
            f"avg60dReturn=`{row['averageRecent60ReturnPct']}`, "
            f"avg60dVol=`{row['averageRealizedVol60AnnualizedPct']}`"
        )
    lines.extend(
        [
            "",
            "## Decision",
            "",
            f"- Historical robustness expansion completed: `{decision['historicalRobustnessExpansionCompleted']}`",
            f"- Active strategy fixed parameters: `{decision['activeStrategyFixedParameters']}`",
            f"- Historical robustness watch passed: `{decision['historicalRobustnessWatchPassed']}`",
            f"- Forward validation still required: `{decision['forwardValidationStillRequired']}`",
            f"- Ready for exchange Dry-run review: `{decision['readyForExchangeDryRunReview']}`",
            f"- Exchange Dry-run approved: `{decision['exchangeDryRunApproved']}`",
            f"- Live trading approved: `{decision['liveTradingApproved']}`",
            f"- Reason: `{decision['reason']}`",
            f"- Warnings: `{', '.join(decision['warnings']) or 'none'}`",
            "",
            "## Recommendations",
            "",
        ]
    )
    for item in report["recommendations"]:
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## Safety Boundary",
            "",
            "- Public local data only.",
            "- No Trade API.",
            "- No Withdraw API.",
            "- No API key storage.",
            "- No real account or position reads.",
            "- No real order creation.",
            "- No automatic trading.",
            "",
        ]
    )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate V13.5.14 historical robustness expansion report.")
    parser.add_argument("--control-tower-report", default=str(DEFAULT_CONTROL_TOWER_REPORT))
    parser.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR))
    parser.add_argument("--cross-market-cache-dir", default=str(DEFAULT_CROSS_MARKET_CACHE_DIR))
    parser.add_argument("--output-report", default=str(DEFAULT_OUTPUT_REPORT))
    parser.add_argument("--output-summary", default=str(DEFAULT_OUTPUT_SUMMARY))
    parser.add_argument("--output-signal-log", default=str(DEFAULT_OUTPUT_SIGNAL_LOG))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_historical_robustness_expansion(
        control_tower_report=Path(args.control_tower_report),
        data_dir=Path(args.data_dir),
        cross_market_cache_dir=Path(args.cross_market_cache_dir),
    )
    signal_rows = report.pop("signalRows")
    write_json(Path(args.output_report), _json_ready(report))
    write_json(Path(args.output_signal_log), _json_ready(signal_rows))
    write_text(Path(args.output_summary), build_summary(report))
    print(f"Wrote {args.output_report}")
    print(f"Wrote {args.output_signal_log}")
    print(f"Wrote {args.output_summary}")
    print(f"decision={report.get('decision')}")


if __name__ == "__main__":
    main()
