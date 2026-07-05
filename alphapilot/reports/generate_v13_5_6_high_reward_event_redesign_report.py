"""Generate V13.5.6 high-reward event redesign report.

V13.5.6 keeps the target at 2R, lowers the win-rate observation screen, and
redesigns event hypotheses toward structures that can naturally support a 2R
target. The report is research-only: it reads local public data, writes local
reports, and never uses API keys, account access, exchange order endpoints, or
automation.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from alphapilot.derivatives.feature_panel import DEFAULT_DATA_DIR, build_derivatives_feature_panel
from alphapilot.ml_gate.high_reward_event_setups import HIGH_REWARD_SETUP_NAMES, add_high_reward_event_setups
from alphapilot.ml_gate.high_reward_triple_barrier import build_high_reward_labeled_events
from alphapilot.ml_gate.probability_gate import evaluate_trades
from alphapilot.ml_gate.triple_barrier import BarrierConfig
from alphapilot.reports.generate_v13_5_1_expanded_relaxed_research_report import discover_local_pairs
from alphapilot.reports.generate_v13_5_derivatives_ml_strategy_report import _json_ready, write_json, write_text


REPORT_ID = "v13_5_6_high_reward_event_redesign_report"
VERSION = "V13.5.6"
DEFAULT_OUTPUT_REPORT = Path("reports/v13_5_6_high_reward_event_redesign_report.json")
DEFAULT_OUTPUT_SUMMARY = Path("reports/v13_5_6_high_reward_event_redesign_summary.md")
DEFAULT_OUTPUT_CANDIDATES = Path("reports/v13_5_6_high_reward_candidates.json")

TARGET_R_MULTIPLE = 2.0
MIN_OBSERVATION_WIN_RATE_PCT = 45.0
MIN_PROFIT_FACTOR = 1.35
MAX_DRAWDOWN_PCT = 30.0
MIN_COST_ADJUSTED_2R_CLOSENESS = 0.85
MIN_SAMPLE_EVENTS = 100
MIN_SAMPLE_PAIRS = 5
MIN_SAMPLE_MONTHS = 10
MIN_RECENT_HOLDOUT_EVENTS = 25
MAX_EXPLORATORY_WATCH_DRAWDOWN_PCT = 40.0


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def parse_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _empty_metrics() -> dict[str, Any]:
    return evaluate_trades(pd.DataFrame())


def _barrier_configs(timeframe: str) -> list[BarrierConfig]:
    """Fixed high-RR research configs, not optimized from results."""

    if timeframe == "1h":
        configs = [
            (0.02, 24),
            (0.025, 30),
            (0.03, 36),
            (0.04, 48),
            (0.05, 60),
        ]
    elif timeframe == "4h":
        configs = [
            (0.04, 12),
            (0.05, 18),
            (0.06, 24),
            (0.08, 30),
        ]
    else:
        configs = [
            (0.015, 32),
            (0.02, 48),
            (0.025, 64),
        ]
    return [
        BarrierConfig(
            stop_loss_pct=stop,
            reward_r_multiple=TARGET_R_MULTIPLE,
            horizon_bars=horizon,
            fee_rate_roundtrip=0.001,
            slippage_rate_roundtrip=0.001,
        )
        for stop, horizon in configs
    ]


def _cost_adjusted_2r_stats(config: BarrierConfig, metrics: dict[str, Any]) -> dict[str, Any]:
    cost = float(config.fee_rate_roundtrip + config.slippage_rate_roundtrip)
    gross_target_return = float(config.stop_loss_pct * config.reward_r_multiple)
    target_net_return = gross_target_return - cost
    stop_net_loss = float(config.stop_loss_pct + cost)
    theoretical_net_rr = target_net_return / stop_net_loss if stop_net_loss > 0 else None
    observed_rr = metrics.get("rewardRiskRatio")
    if theoretical_net_rr and observed_rr is not None:
        closeness = float(observed_rr) / theoretical_net_rr
    else:
        closeness = None
    return {
        "targetRMultiple": config.reward_r_multiple,
        "grossTargetReturnPct": round(gross_target_return * 100, 6),
        "modeledRoundtripCostPct": round(cost * 100, 6),
        "targetNetReturnPct": round(target_net_return * 100, 6),
        "stopNetLossPct": round(stop_net_loss * 100, 6),
        "costAdjustedTheoreticalRewardRiskRatio": round(theoretical_net_rr, 6)
        if theoretical_net_rr is not None
        else None,
        "observedToCostAdjusted2RCloseness": round(closeness, 6) if closeness is not None else None,
        "note": "Target remains fixed at 2R; modeled costs reduce the observed net reward/risk ceiling.",
    }


def _split_frame(events: pd.DataFrame, start_pct: float, end_pct: float) -> pd.DataFrame:
    if events.empty:
        return events
    ordered = events.sort_values("signalDate").reset_index(drop=True)
    start = int(len(ordered) * start_pct)
    end = int(len(ordered) * end_pct)
    return ordered.iloc[start:end].copy()


def _time_splits(events: pd.DataFrame) -> dict[str, Any]:
    if events.empty:
        return {
            "early60": _empty_metrics(),
            "middle20": _empty_metrics(),
            "recent20": _empty_metrics(),
            "year2024": _empty_metrics(),
            "year2025": _empty_metrics(),
            "year2026": _empty_metrics(),
        }
    signal_dates = pd.to_datetime(events["signalDate"], utc=True)
    return {
        "early60": evaluate_trades(_split_frame(events, 0.0, 0.6)),
        "middle20": evaluate_trades(_split_frame(events, 0.6, 0.8)),
        "recent20": evaluate_trades(_split_frame(events, 0.8, 1.0)),
        "year2024": evaluate_trades(events[(signal_dates >= "2024-01-01") & (signal_dates < "2025-01-01")]),
        "year2025": evaluate_trades(events[(signal_dates >= "2025-01-01") & (signal_dates < "2026-01-01")]),
        "year2026": evaluate_trades(events[signal_dates >= "2026-01-01"]),
    }


def _distribution(events: pd.DataFrame, column: str, limit: int = 12) -> list[dict[str, Any]]:
    if events.empty or column not in events.columns:
        return []
    total = len(events)
    rows: list[dict[str, Any]] = []
    for value, count in events[column].value_counts(dropna=False).head(limit).items():
        rows.append(
            {
                "value": str(value),
                "count": int(count),
                "sharePct": round(float(count / total * 100), 4) if total else 0.0,
            }
        )
    return rows


def _month_distribution(events: pd.DataFrame, limit: int = 18) -> list[dict[str, Any]]:
    if events.empty:
        return []
    frame = events.copy()
    frame["signalMonth"] = pd.to_datetime(frame["signalDate"], utc=True).dt.strftime("%Y-%m")
    return _distribution(frame, "signalMonth", limit=limit)


def _exit_reason_summary(events: pd.DataFrame) -> dict[str, Any]:
    if events.empty or "exitReason" not in events.columns:
        return {
            "takeProfitCount": 0,
            "stopLossCount": 0,
            "timeExitCount": 0,
            "sameCandleStopCount": 0,
            "takeProfitSharePct": 0.0,
            "stopLossSharePct": 0.0,
            "timeExitSharePct": 0.0,
            "sameCandleStopSharePct": 0.0,
            "distribution": [],
        }
    total = len(events)
    reasons = events["exitReason"].astype(str)
    take_profit = int((reasons == "take_profit_2r").sum())
    stop_loss = int(reasons.isin(["stop_loss", "stop_loss_same_candle"]).sum())
    time_exit = int((reasons == "time_exit").sum())
    same_candle = int((reasons == "stop_loss_same_candle").sum())
    return {
        "takeProfitCount": take_profit,
        "stopLossCount": stop_loss,
        "timeExitCount": time_exit,
        "sameCandleStopCount": same_candle,
        "takeProfitSharePct": round(take_profit / total * 100, 4) if total else 0.0,
        "stopLossSharePct": round(stop_loss / total * 100, 4) if total else 0.0,
        "timeExitSharePct": round(time_exit / total * 100, 4) if total else 0.0,
        "sameCandleStopSharePct": round(same_candle / total * 100, 4) if total else 0.0,
        "distribution": _distribution(events, "exitReason", limit=8),
    }


def _sample_quality(
    events: pd.DataFrame,
    metrics: dict[str, Any],
    splits: dict[str, Any],
    pair_distribution: list[dict[str, Any]],
    month_distribution: list[dict[str, Any]],
) -> dict[str, Any]:
    fail_reasons: list[str] = []
    warning_reasons: list[str] = []
    trade_count = int(metrics.get("tradeCount") or 0)
    unique_pairs = int(events["pair"].nunique()) if not events.empty and "pair" in events else 0
    unique_months = int(pd.to_datetime(events["signalDate"], utc=True).dt.strftime("%Y-%m").nunique()) if not events.empty else 0
    max_pair_share = pair_distribution[0]["sharePct"] if pair_distribution else 0.0
    max_month_share = month_distribution[0]["sharePct"] if month_distribution else 0.0
    recent_count = int((splits.get("recent20") or {}).get("tradeCount") or 0)

    if trade_count < MIN_SAMPLE_EVENTS:
        fail_reasons.append("event_count_below_100")
    if unique_pairs < MIN_SAMPLE_PAIRS:
        fail_reasons.append("pair_coverage_below_5")
    if unique_months < MIN_SAMPLE_MONTHS:
        fail_reasons.append("month_coverage_below_10")
    if max_pair_share > 45:
        fail_reasons.append("single_pair_concentration_above_45pct")
    elif max_pair_share > 35:
        warning_reasons.append("single_pair_concentration_above_35pct")
    if max_month_share > 35:
        fail_reasons.append("single_month_concentration_above_35pct")
    elif max_month_share > 25:
        warning_reasons.append("single_month_concentration_above_25pct")
    if recent_count < MIN_RECENT_HOLDOUT_EVENTS:
        fail_reasons.append("recent_holdout_sample_below_25")

    return {
        "sampleSufficiencyPassed": not fail_reasons,
        "failReasons": fail_reasons,
        "warningReasons": warning_reasons,
        "uniquePairs": unique_pairs,
        "uniqueMonths": unique_months,
        "maxPairSharePct": max_pair_share,
        "maxMonthSharePct": max_month_share,
        "recentHoldoutTradeCount": recent_count,
    }


def _target_quality(metrics: dict[str, Any], splits: dict[str, Any], cost_stats: dict[str, Any]) -> dict[str, Any]:
    fail_reasons: list[str] = []
    if (metrics.get("winRatePct") or 0) < MIN_OBSERVATION_WIN_RATE_PCT:
        fail_reasons.append("win_rate_below_45")
    if (metrics.get("profitFactor") or 0) < MIN_PROFIT_FACTOR:
        fail_reasons.append("profit_factor_below_1_35")
    if (metrics.get("maxDrawdownPct") or 999) > MAX_DRAWDOWN_PCT:
        fail_reasons.append("max_drawdown_above_30")
    if (metrics.get("totalReturnPct") or 0) <= 0:
        fail_reasons.append("total_return_not_positive")
    closeness = cost_stats.get("observedToCostAdjusted2RCloseness")
    if closeness is None or closeness < MIN_COST_ADJUSTED_2R_CLOSENESS:
        fail_reasons.append("observed_rr_not_close_to_cost_adjusted_2r")
    recent = splits.get("recent20") or {}
    if (recent.get("tradeCount") or 0) >= MIN_RECENT_HOLDOUT_EVENTS:
        if (recent.get("profitFactor") or 0) < 1:
            fail_reasons.append("recent_profit_factor_below_1")
        if (recent.get("winRatePct") or 0) < 40:
            fail_reasons.append("recent_win_rate_below_40")
    return {
        "targetMetricsPassed": not fail_reasons,
        "failReasons": fail_reasons,
    }


def _summarize_pool(
    events: pd.DataFrame,
    timeframe: str,
    config: BarrierConfig,
    setup_name: str | None,
) -> dict[str, Any]:
    selected = events if setup_name is None else events[events["setupName"] == setup_name].copy()
    metrics = evaluate_trades(selected)
    splits = _time_splits(selected)
    pair_dist = _distribution(selected, "pair", limit=12)
    setup_dist = _distribution(selected, "setupName", limit=8)
    month_dist = _month_distribution(selected, limit=18)
    exit_reasons = _exit_reason_summary(selected)
    sample = _sample_quality(selected, metrics, splits, pair_dist, month_dist)
    cost_stats = _cost_adjusted_2r_stats(config, metrics)
    target = _target_quality(metrics, splits, cost_stats)
    first_date = pd.to_datetime(selected["signalDate"], utc=True).min().isoformat() if not selected.empty else None
    last_date = pd.to_datetime(selected["signalDate"], utc=True).max().isoformat() if not selected.empty else None
    target_passed = bool(sample["sampleSufficiencyPassed"] and target["targetMetricsPassed"])
    return {
        "poolId": f"{timeframe}:{setup_name or 'all_high_reward_setups'}:sl{config.stop_loss_pct}:h{config.horizon_bars}",
        "timeframe": timeframe,
        "setupName": setup_name or "all_high_reward_setups",
        "barrierConfig": asdict(config),
        "firstSignalAt": first_date,
        "lastSignalAt": last_date,
        "metrics": metrics,
        "costAdjusted2R": cost_stats,
        "exitReasonSummary": exit_reasons,
        "timeSplitMetrics": splits,
        "pairDistribution": pair_dist,
        "setupDistribution": setup_dist,
        "monthDistribution": month_dist,
        "sampleQuality": sample,
        "targetQuality": target,
        "decision": {
            "targetRMultipleUnchanged": config.reward_r_multiple == TARGET_R_MULTIPLE,
            "candidateReadyForForwardConfirmation": bool(sample["sampleSufficiencyPassed"]),
            "newLocalPaperCandidateApproved": target_passed,
            "exchangeDryRunApproved": False,
            "liveTradingApproved": False,
        },
    }


def _filter_specs() -> list[dict[str, str]]:
    return [
        {
            "filterId": "hr_long_extreme_volume_btc_crash_rebound",
            "description": "Long rebound after extreme volume and BTC crash context.",
        },
        {
            "filterId": "hr_short_sideways_breakout_reject_btc_up",
            "description": "Short failed breakout rejection during sideways BTC regime and BTC upside impulse.",
        },
        {
            "filterId": "hr_short_extreme_volume_relative_strength_basis_low",
            "description": "Short exhaustion after relative strength, extreme volume, and slightly negative basis.",
        },
        {
            "filterId": "hr_short_overheated_extreme_volume_basis_low",
            "description": "Short overheated reversal context with extreme volume and slightly negative basis.",
        },
    ]


def _apply_filter(events: pd.DataFrame, filter_id: str) -> pd.Series:
    if events.empty:
        return pd.Series([], dtype=bool)
    if filter_id == "hr_long_extreme_volume_btc_crash_rebound":
        return (
            (events["direction"] == "long")
            & (events["volume_ratio"] >= 2.8)
            & (events["btc_return_3"] <= -0.04)
            & (events["bollinger_z"] <= -1.5)
        )
    if filter_id == "hr_short_sideways_breakout_reject_btc_up":
        return (
            (events["setupName"] == "hr_short_failed_breakout_rejection")
            & (events["btc_regime"] == "sideways")
            & (events["btc_return_3"] > 0.015)
            & (events["btc_return_3"] <= 0.04)
        )
    if filter_id == "hr_short_extreme_volume_relative_strength_basis_low":
        return (
            (events["direction"] == "short")
            & (events["volume_ratio"] >= 2.8)
            & (events["relative_return_6"] > 0.04)
            & (events["mark_basis_pct"] > -0.001)
            & (events["mark_basis_pct"] <= -0.0002)
        )
    if filter_id == "hr_short_overheated_extreme_volume_basis_low":
        return (
            (events["direction"] == "short")
            & (events["rsi14"] > 70)
            & (events["volume_ratio"] >= 2.8)
            & (events["mark_basis_pct"] > -0.001)
            & (events["mark_basis_pct"] <= -0.0002)
        )
    return pd.Series([False] * len(events), index=events.index)


def _summarize_exploratory_filter(
    events: pd.DataFrame,
    timeframe: str,
    config: BarrierConfig,
    filter_spec: dict[str, str],
) -> dict[str, Any] | None:
    mask = _apply_filter(events, filter_spec["filterId"])
    selected = events[mask].copy()
    if selected.empty:
        return None
    metrics = evaluate_trades(selected)
    splits = _time_splits(selected)
    pair_dist = _distribution(selected, "pair", limit=12)
    month_dist = _month_distribution(selected, limit=18)
    sample = _sample_quality(selected, metrics, splits, pair_dist, month_dist)
    cost_stats = _cost_adjusted_2r_stats(config, metrics)
    target = _target_quality(metrics, splits, cost_stats)
    recent = splits.get("recent20") or {}
    watch_fail_reasons: list[str] = []
    if not sample["sampleSufficiencyPassed"]:
        watch_fail_reasons.append("sample_sufficiency_failed")
    if (metrics.get("tradeCount") or 0) < 120:
        watch_fail_reasons.append("trade_count_below_120")
    if sample.get("uniquePairs", 0) < 20:
        watch_fail_reasons.append("pair_coverage_below_20")
    if (metrics.get("winRatePct") or 0) < 55:
        watch_fail_reasons.append("win_rate_below_55")
    if (metrics.get("profitFactor") or 0) < 2:
        watch_fail_reasons.append("profit_factor_below_2")
    if (metrics.get("maxDrawdownPct") or 999) > MAX_EXPLORATORY_WATCH_DRAWDOWN_PCT:
        watch_fail_reasons.append("max_drawdown_above_40")
    if (cost_stats.get("observedToCostAdjusted2RCloseness") or 0) < 0.9:
        watch_fail_reasons.append("observed_rr_not_close_enough_to_cost_adjusted_2r")
    if (recent.get("tradeCount") or 0) < MIN_RECENT_HOLDOUT_EVENTS:
        watch_fail_reasons.append("recent_holdout_sample_below_25")
    if (recent.get("profitFactor") or 0) < 1:
        watch_fail_reasons.append("recent_profit_factor_below_1")
    exploratory_watch_approved = not watch_fail_reasons
    return {
        "filterId": filter_spec["filterId"],
        "description": filter_spec["description"],
        "poolId": f"{timeframe}:{filter_spec['filterId']}:sl{config.stop_loss_pct}:h{config.horizon_bars}",
        "timeframe": timeframe,
        "barrierConfig": asdict(config),
        "metrics": metrics,
        "timeSplitMetrics": splits,
        "costAdjusted2R": cost_stats,
        "pairDistribution": pair_dist,
        "monthDistribution": month_dist,
        "sampleQuality": sample,
        "targetQuality": target,
        "exploratoryWatchQuality": {
            "exploratoryLocalPaperWatchApproved": exploratory_watch_approved,
            "failReasons": watch_fail_reasons,
            "note": "This only allows local paper observation, not exchange Dry-run or live trading.",
        },
        "decision": {
            "exploratoryOnly": True,
            "exploratoryLocalPaperWatchApproved": exploratory_watch_approved,
            "newLocalPaperCandidateApproved": False,
            "exchangeDryRunApproved": False,
            "liveTradingApproved": False,
            "reason": (
                "approved_for_local_paper_watch_only"
                if exploratory_watch_approved
                else "fixed exploratory filter; requires independent forward confirmation before any promotion"
            ),
        },
    }


def _coverage_for_panel(panel: pd.DataFrame) -> dict[str, Any]:
    if panel.empty:
        return {
            "panelRows": 0,
            "dateStart": None,
            "dateEnd": None,
            "pairCount": 0,
            "pairCoverage": [],
        }
    rows: list[dict[str, Any]] = []
    for pair, group in panel.groupby("pair", sort=True):
        rows.append(
            {
                "pair": pair,
                "rows": int(len(group)),
                "start": group["date"].min().isoformat(),
                "end": group["date"].max().isoformat(),
                "fundingCoveragePct": round(float(group["funding_rate"].notna().mean() * 100), 4),
                "markBasisCoveragePct": round(float(group["mark_basis_pct"].notna().mean() * 100), 4),
            }
        )
    return {
        "panelRows": int(len(panel)),
        "dateStart": panel["date"].min().isoformat(),
        "dateEnd": panel["date"].max().isoformat(),
        "pairCount": int(panel["pair"].nunique()),
        "pairCoverage": rows,
    }


def _rank_pools(pools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        pools,
        key=lambda row: (
            1 if row["targetQuality"]["targetMetricsPassed"] and row["sampleQuality"]["sampleSufficiencyPassed"] else 0,
            1 if row["sampleQuality"]["sampleSufficiencyPassed"] else 0,
            row["metrics"].get("profitFactor") or 0,
            row["metrics"].get("totalReturnPct") or -9999,
            row["costAdjusted2R"].get("observedToCostAdjusted2RCloseness") or 0,
            row["metrics"].get("tradeCount") or 0,
            -(row["sampleQuality"].get("maxPairSharePct") or 0),
        ),
        reverse=True,
    )


def _rank_exploratory_filters(filters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        filters,
        key=lambda row: (
            row["metrics"].get("profitFactor") or 0,
            row["timeSplitMetrics"].get("recent20", {}).get("profitFactor") or 0,
            row["metrics"].get("winRatePct") or 0,
            row["metrics"].get("tradeCount") or 0,
            -(row["metrics"].get("maxDrawdownPct") or 999),
        ),
        reverse=True,
    )


def _latest_candidate_sample(pools: list[dict[str, Any]], limit: int = 12) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for pool in pools[:limit]:
        metrics = pool.get("metrics") or {}
        rows.append(
            {
                "poolId": pool.get("poolId"),
                "timeframe": pool.get("timeframe"),
                "setupName": pool.get("setupName"),
                "tradeCount": metrics.get("tradeCount"),
                "winRatePct": metrics.get("winRatePct"),
                "rewardRiskRatio": metrics.get("rewardRiskRatio"),
                "profitFactor": metrics.get("profitFactor"),
                "totalReturnPct": metrics.get("totalReturnPct"),
                "maxDrawdownPct": metrics.get("maxDrawdownPct"),
                "targetRMultiple": (pool.get("costAdjusted2R") or {}).get("targetRMultiple"),
                "costAdjustedTheoreticalRewardRiskRatio": (pool.get("costAdjusted2R") or {}).get(
                    "costAdjustedTheoreticalRewardRiskRatio"
                ),
                "observedToCostAdjusted2RCloseness": (pool.get("costAdjusted2R") or {}).get(
                    "observedToCostAdjusted2RCloseness"
                ),
                "sampleSufficiencyPassed": (pool.get("sampleQuality") or {}).get("sampleSufficiencyPassed"),
                "targetMetricsPassed": (pool.get("targetQuality") or {}).get("targetMetricsPassed"),
            }
        )
    return rows


def _recommendations(
    sample_ready: list[dict[str, Any]],
    target_ready: list[dict[str, Any]],
    ranked: list[dict[str, Any]],
    exploratory_watch_ready: list[dict[str, Any]],
) -> list[str]:
    if target_ready:
        best = target_ready[0]
        metrics = best["metrics"]
        return [
            "A high-reward event pool passed the research screen, but it still requires forward confirmation before any exchange Dry-run review.",
            "Keep the 2R target unchanged; monitor whether cost-adjusted 2R closeness and recent holdout behavior remain stable after the next data refresh.",
            (
                f"Best pool {best['poolId']}: trades={metrics.get('tradeCount')}, "
                f"winRate={metrics.get('winRatePct')}, PF={metrics.get('profitFactor')}, "
                f"maxDD={metrics.get('maxDrawdownPct')}."
            ),
        ]
    if exploratory_watch_ready:
        best_watch = exploratory_watch_ready[0]
        metrics = best_watch["metrics"]
        return [
            "A fixed exploratory filter is approved for local paper watch only; it is not a new formal paper candidate and not exchange Dry-run.",
            "Keep the 2R target unchanged and monitor the next forward signals before any promotion decision.",
            (
                f"Paper-watch pool {best_watch['poolId']}: trades={metrics.get('tradeCount')}, "
                f"winRate={metrics.get('winRatePct')}, PF={metrics.get('profitFactor')}, "
                f"maxDD={metrics.get('maxDrawdownPct')}."
            ),
        ]
    if sample_ready:
        best = sample_ready[0]
        metrics = best["metrics"]
        return [
            "High-reward event pools have enough breadth for continued research, but none passed the full 2R quality screen.",
            "Do not promote a new paper candidate yet; refine event structure with additional execution and liquidity context instead of lowering the 2R target.",
            (
                f"Best sample-ready pool {best['poolId']}: trades={metrics.get('tradeCount')}, "
                f"winRate={metrics.get('winRatePct')}, PF={metrics.get('profitFactor')}, "
                f"RR={metrics.get('rewardRiskRatio')}."
            ),
        ]
    best = ranked[0] if ranked else {}
    metrics = best.get("metrics", {})
    return [
        "The redesigned high-reward events are still too sparse or concentrated for approval.",
        "Next research step should add stronger liquidity/execution context or broader history, not relax the 2R target.",
        (
            f"Best observed pool {best.get('poolId')}: trades={metrics.get('tradeCount')}, "
            f"winRate={metrics.get('winRatePct')}, PF={metrics.get('profitFactor')}, "
            f"RR={metrics.get('rewardRiskRatio')}."
            if best
            else "No high-reward event pools were created."
        ),
    ]


def run_high_reward_event_redesign(
    timeframes: list[str],
    pairs: list[str] | None = None,
    data_dir: Path = DEFAULT_DATA_DIR,
) -> dict[str, Any]:
    timeframe_reports: list[dict[str, Any]] = []
    all_pools: list[dict[str, Any]] = []
    all_exploratory_filters: list[dict[str, Any]] = []

    for timeframe in timeframes:
        timeframe_pairs = pairs or discover_local_pairs(timeframe, data_dir=data_dir)
        panel_result = build_derivatives_feature_panel(pairs=timeframe_pairs, timeframe=timeframe, data_dir=data_dir)
        panel = panel_result.rows.dropna(
            subset=[
                "close",
                "open",
                "high",
                "low",
                "rsi14",
                "volume_ratio",
                "atr_pct",
                "prior_high_48",
                "prior_low_48",
            ]
        ).copy()
        prepared_panel = add_high_reward_event_setups(panel) if not panel.empty else panel
        coverage = _coverage_for_panel(prepared_panel)
        pools: list[dict[str, Any]] = []
        setup_signal_counts: dict[str, int] = {}
        if not prepared_panel.empty:
            for setup_name in HIGH_REWARD_SETUP_NAMES:
                setup_signal_counts[setup_name] = int(prepared_panel[setup_name].fillna(False).sum())
            for barrier_config in _barrier_configs(timeframe):
                events = build_high_reward_labeled_events(prepared_panel, barrier_config)
                if events.empty:
                    continue
                pools.append(_summarize_pool(events, timeframe, barrier_config, setup_name=None))
                for setup_name in sorted(events["setupName"].dropna().unique()):
                    pools.append(_summarize_pool(events, timeframe, barrier_config, setup_name=str(setup_name)))
                for filter_spec in _filter_specs():
                    filter_summary = _summarize_exploratory_filter(events, timeframe, barrier_config, filter_spec)
                    if filter_summary is not None:
                        all_exploratory_filters.append(filter_summary)

        ranked = _rank_pools(pools)
        all_pools.extend(ranked)
        timeframe_reports.append(
            {
                "timeframe": timeframe,
                "requestedPairs": timeframe_pairs,
                "loadedPairs": panel_result.loaded_pairs,
                "missingPairs": panel_result.missing_pairs,
                "missingOptionalSources": panel_result.missing_optional_sources,
                "coverage": coverage,
                "setupSignalCounts": setup_signal_counts,
                "barrierConfigCount": len(_barrier_configs(timeframe)),
                "poolCount": len(pools),
                "topPools": ranked[:12],
            }
        )

    ranked_all = _rank_pools(all_pools)
    ranked_exploratory_filters = _rank_exploratory_filters(all_exploratory_filters)
    exploratory_watch_ready = [
        row
        for row in ranked_exploratory_filters
        if (row.get("exploratoryWatchQuality") or {}).get("exploratoryLocalPaperWatchApproved")
    ]
    target_ready = [
        row
        for row in ranked_all
        if row["sampleQuality"]["sampleSufficiencyPassed"] and row["targetQuality"]["targetMetricsPassed"]
    ]
    sample_ready = [row for row in ranked_all if row["sampleQuality"]["sampleSufficiencyPassed"]]
    closeness_ranked = sorted(
        ranked_all,
        key=lambda row: (
            row["costAdjusted2R"].get("observedToCostAdjusted2RCloseness") or 0,
            row["metrics"].get("tradeCount") or 0,
            row["metrics"].get("profitFactor") or 0,
        ),
        reverse=True,
    )
    generated_at = utc_now()
    return {
        "reportId": REPORT_ID,
        "version": VERSION,
        "status": "completed",
        "isMock": False,
        "generatedAt": generated_at,
        "objective": {
            "mode": "high_reward_event_redesign",
            "targetRMultiple": TARGET_R_MULTIPLE,
            "observationWinRateScreenPct": MIN_OBSERVATION_WIN_RATE_PCT,
            "profitFactorScreen": MIN_PROFIT_FACTOR,
            "maxDrawdownScreenPct": MAX_DRAWDOWN_PCT,
            "costAdjusted2RClosenessScreen": MIN_COST_ADJUSTED_2R_CLOSENESS,
            "antiOverfitRule": "Do not relax the 2R target; only accept broad samples with recent holdout stability.",
        },
        "dataSource": {
            "localPublicDataDir": str(data_dir),
            "timeframes": timeframes,
            "pairsMode": "explicit" if pairs else "discover_local_pairs",
            "openInterestStatus": "unavailable_not_fabricated",
            "fundingStatus": "used_when_local_public_files_exist",
        },
        "timeframes": timeframe_reports,
        "eventPoolSummary": {
            "totalPools": len(ranked_all),
            "sampleSufficientPoolCount": len(sample_ready),
            "targetMetricPoolCount": len(target_ready),
            "highestCostAdjusted2RCloseness": (
                closeness_ranked[0]["costAdjusted2R"].get("observedToCostAdjusted2RCloseness")
                if closeness_ranked
                else None
            ),
            "topPoolIds": [row["poolId"] for row in ranked_all[:10]],
        },
        "topEventPools": ranked_all[:30],
        "highest2RClosenessPools": closeness_ranked[:15],
        "exploratoryFixedFilters": ranked_exploratory_filters[:20],
        "candidateSample": _latest_candidate_sample(ranked_all, limit=20),
        "decision": {
            "highRewardEventRedesignCompleted": True,
            "targetRMultipleUnchanged": True,
            "sampleSufficiencyReady": bool(sample_ready),
            "forwardConfirmationCandidateFound": bool(target_ready),
            "newLocalPaperCandidateApproved": bool(target_ready),
            "exploratoryLocalPaperWatchApproved": bool(exploratory_watch_ready),
            "exploratoryLocalPaperWatchPoolId": exploratory_watch_ready[0]["poolId"] if exploratory_watch_ready else None,
            "exchangeDryRunApproved": False,
            "liveTradingApproved": False,
            "reason": (
                "high_reward_pool_requires_forward_confirmation"
                if target_ready
                else "exploratory_local_paper_watch_only"
                if exploratory_watch_ready
                else "sample_ready_but_no_full_2r_quality_pass"
                if sample_ready
                else "high_reward_events_still_sparse_or_concentrated"
            ),
        },
        "recommendations": _recommendations(sample_ready, target_ready, ranked_all, exploratory_watch_ready),
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


def write_summary(report: dict[str, Any], path: Path) -> None:
    decision = report["decision"]
    summary = report["eventPoolSummary"]
    lines = [
        "# V13.5.6 High Reward Event Redesign Report",
        "",
        "This report keeps the target at 2R and tests redesigned high-reward event structures on local public data.",
        "It is research-only and does not approve exchange Dry-run or live trading.",
        "",
        "## Decision",
        "",
        f"- High reward redesign completed: `{decision['highRewardEventRedesignCompleted']}`",
        f"- Target R multiple unchanged: `{decision['targetRMultipleUnchanged']}`",
        f"- Sample sufficiency ready: `{decision['sampleSufficiencyReady']}`",
        f"- Forward confirmation candidate found: `{decision['forwardConfirmationCandidateFound']}`",
        f"- New local paper candidate approved: `{decision['newLocalPaperCandidateApproved']}`",
        f"- Exploratory local paper watch approved: `{decision['exploratoryLocalPaperWatchApproved']}`",
        f"- Exploratory local paper watch pool: `{decision['exploratoryLocalPaperWatchPoolId']}`",
        f"- Exchange Dry-run approved: `{decision['exchangeDryRunApproved']}`",
        f"- Live trading approved: `{decision['liveTradingApproved']}`",
        f"- Reason: `{decision['reason']}`",
        "",
        "## Event Pool Summary",
        "",
        f"- Total pools: `{summary['totalPools']}`",
        f"- Sample-sufficient pools: `{summary['sampleSufficientPoolCount']}`",
        f"- Target-metric pools: `{summary['targetMetricPoolCount']}`",
        f"- Highest cost-adjusted 2R closeness: `{summary['highestCostAdjusted2RCloseness']}`",
        "",
        "## Timeframe Coverage",
        "",
    ]
    for item in report.get("timeframes", []):
        coverage = item.get("coverage") or {}
        lines.append(
            f"- `{item.get('timeframe')}`: pairs=`{coverage.get('pairCount')}`, "
            f"panelRows=`{coverage.get('panelRows')}`, "
            f"range=`{coverage.get('dateStart')}` to `{coverage.get('dateEnd')}`, "
            f"pools=`{item.get('poolCount')}`"
        )
    lines.extend(["", "## Top Event Pools", ""])
    for pool in report.get("topEventPools", [])[:12]:
        metrics = pool.get("metrics") or {}
        sample = pool.get("sampleQuality") or {}
        target = pool.get("targetQuality") or {}
        cost = pool.get("costAdjusted2R") or {}
        lines.append(
            f"- `{pool.get('poolId')}`: trades=`{metrics.get('tradeCount')}`, "
            f"winRate=`{metrics.get('winRatePct')}`, RR=`{metrics.get('rewardRiskRatio')}`, "
            f"PF=`{metrics.get('profitFactor')}`, maxDD=`{metrics.get('maxDrawdownPct')}`, "
            f"2Rclose=`{cost.get('observedToCostAdjusted2RCloseness')}`, "
            f"sampleReady=`{sample.get('sampleSufficiencyPassed')}`, "
            f"targetReady=`{target.get('targetMetricsPassed')}`, "
            f"fail=`{', '.join(sample.get('failReasons') or []) or 'none'}`, "
            f"targetFail=`{', '.join(target.get('failReasons') or []) or 'none'}`"
        )
    lines.extend(["", "## Exploratory Fixed Filters", ""])
    for item in report.get("exploratoryFixedFilters", [])[:8]:
        metrics = item.get("metrics") or {}
        recent = (item.get("timeSplitMetrics") or {}).get("recent20") or {}
        watch = item.get("exploratoryWatchQuality") or {}
        lines.append(
            f"- `{item.get('poolId')}`: trades=`{metrics.get('tradeCount')}`, "
            f"winRate=`{metrics.get('winRatePct')}`, RR=`{metrics.get('rewardRiskRatio')}`, "
            f"PF=`{metrics.get('profitFactor')}`, maxDD=`{metrics.get('maxDrawdownPct')}`, "
            f"recentTrades=`{recent.get('tradeCount')}`, recentPF=`{recent.get('profitFactor')}`, "
            f"paperWatch=`{watch.get('exploratoryLocalPaperWatchApproved')}`, "
            f"watchFail=`{', '.join(watch.get('failReasons') or []) or 'none'}`"
        )
    lines.extend(["", "## Recommendations", ""])
    for item in report.get("recommendations", []):
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
            "- No order creation.",
            "- No automatic trading.",
            "",
        ]
    )
    write_text(path, "\n".join(lines))


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate V13.5.6 high-reward event redesign report.")
    parser.add_argument("--timeframes", default="1h,4h")
    parser.add_argument("--pairs", default=None)
    parser.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR))
    parser.add_argument("--output-report", default=str(DEFAULT_OUTPUT_REPORT))
    parser.add_argument("--output-summary", default=str(DEFAULT_OUTPUT_SUMMARY))
    parser.add_argument("--output-candidates", default=str(DEFAULT_OUTPUT_CANDIDATES))
    args = parser.parse_args()

    report = run_high_reward_event_redesign(
        timeframes=parse_csv(args.timeframes),
        pairs=parse_csv(args.pairs) or None,
        data_dir=Path(args.data_dir),
    )
    write_json(Path(args.output_report), _json_ready(report))
    write_summary(report, Path(args.output_summary))
    write_json(
        Path(args.output_candidates),
        _json_ready(
            {
                "reportId": report["reportId"],
                "version": report["version"],
                "generatedAt": report["generatedAt"],
                "decision": report["decision"],
                "candidateSample": report["candidateSample"],
                "topEventPools": report["topEventPools"][:10],
                "exploratoryFixedFilters": report["exploratoryFixedFilters"][:10],
            }
        ),
    )


if __name__ == "__main__":
    main()
