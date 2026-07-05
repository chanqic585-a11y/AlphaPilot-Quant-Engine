"""Generate V13.5.5 public-data event pool expansion report.

V13.5.5 expands the amount of public historical data used for AlphaPilot
research and reports whether candidate-event pools have enough breadth to keep
local paper monitoring meaningful. It deliberately does not tune a live
strategy for win rate and does not approve exchange Dry-run or live trading.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from alphapilot.derivatives.feature_panel import DEFAULT_DATA_DIR, build_derivatives_feature_panel
from alphapilot.ml_gate.probability_gate import evaluate_trades
from alphapilot.ml_gate.triple_barrier import BarrierConfig, build_labeled_events
from alphapilot.reports.generate_v13_5_1_expanded_relaxed_research_report import discover_local_pairs
from alphapilot.reports.generate_v13_5_derivatives_ml_strategy_report import _json_ready, write_json, write_text


REPORT_ID = "v13_5_5_event_pool_expansion_report"
VERSION = "V13.5.5"
DEFAULT_OUTPUT_REPORT = Path("reports/v13_5_5_event_pool_expansion_report.json")
DEFAULT_OUTPUT_SUMMARY = Path("reports/v13_5_5_event_pool_expansion_summary.md")
DEFAULT_OUTPUT_CANDIDATES = Path("reports/v13_5_5_event_pool_candidates.json")
MIN_TARGET_WIN_RATE_PCT = 45
MIN_TARGET_REWARD_RISK_RATIO = 2.0
MIN_TARGET_PROFIT_FACTOR = 1.35
MAX_TARGET_DRAWDOWN_PCT = 25


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def parse_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _safe_pct(value: float) -> float:
    return round(float(value) * 100, 4)


def _barrier_configs(timeframe: str) -> list[BarrierConfig]:
    """Fixed research configs, not tuned per result."""

    if timeframe == "15m":
        configs = [
            (0.015, 24),
            (0.02, 32),
            (0.025, 48),
        ]
    elif timeframe == "1h":
        configs = [
            (0.02, 12),
            (0.025, 18),
            (0.03, 24),
            (0.04, 30),
        ]
    else:
        configs = [
            (0.04, 12),
            (0.05, 18),
            (0.06, 24),
        ]
    return [
        BarrierConfig(
            stop_loss_pct=stop,
            reward_r_multiple=2.0,
            horizon_bars=horizon,
            fee_rate_roundtrip=0.001,
            slippage_rate_roundtrip=0.001,
        )
        for stop, horizon in configs
    ]


def _empty_metrics() -> dict[str, Any]:
    return evaluate_trades(pd.DataFrame())


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


def _distribution(events: pd.DataFrame, column: str, limit: int = 10) -> list[dict[str, Any]]:
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


def _month_distribution(events: pd.DataFrame, limit: int = 12) -> list[dict[str, Any]]:
    if events.empty:
        return []
    months = pd.to_datetime(events["signalDate"], utc=True).dt.strftime("%Y-%m")
    frame = events.copy()
    frame["signalMonth"] = months
    return _distribution(frame, "signalMonth", limit=limit)


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

    if trade_count < 300:
        fail_reasons.append("event_count_below_300")
    if unique_pairs < 8:
        fail_reasons.append("pair_coverage_below_8")
    if unique_months < 12:
        fail_reasons.append("month_coverage_below_12")
    if max_pair_share > 35:
        fail_reasons.append("single_pair_concentration_above_35pct")
    elif max_pair_share > 25:
        warning_reasons.append("single_pair_concentration_above_25pct")
    if max_month_share > 25:
        fail_reasons.append("single_month_concentration_above_25pct")
    elif max_month_share > 18:
        warning_reasons.append("single_month_concentration_above_18pct")
    if recent_count < 50:
        fail_reasons.append("recent_holdout_sample_below_50")

    target_reasons: list[str] = []
    if (metrics.get("winRatePct") or 0) < MIN_TARGET_WIN_RATE_PCT:
        target_reasons.append("win_rate_below_45")
    if (metrics.get("rewardRiskRatio") or 0) < MIN_TARGET_REWARD_RISK_RATIO:
        target_reasons.append("reward_risk_below_2_0")
    if (metrics.get("profitFactor") or 0) < MIN_TARGET_PROFIT_FACTOR:
        target_reasons.append("profit_factor_below_1_35")
    if (metrics.get("maxDrawdownPct") or 999) > MAX_TARGET_DRAWDOWN_PCT:
        target_reasons.append("max_drawdown_above_25")
    if (metrics.get("totalReturnPct") or 0) <= 0:
        target_reasons.append("total_return_not_positive")
    if (splits.get("recent20") or {}).get("tradeCount", 0) >= 50:
        if ((splits.get("recent20") or {}).get("winRatePct") or 0) < 50:
            target_reasons.append("recent_win_rate_below_50")
        if ((splits.get("recent20") or {}).get("profitFactor") or 0) < 1:
            target_reasons.append("recent_profit_factor_below_1")

    sample_passed = not fail_reasons
    target_passed = sample_passed and not target_reasons
    return {
        "sampleSufficiencyPassed": sample_passed,
        "targetMetricsPassed": target_passed,
        "failReasons": fail_reasons,
        "warningReasons": warning_reasons,
        "targetFailReasons": target_reasons,
        "uniquePairs": unique_pairs,
        "uniqueMonths": unique_months,
        "maxPairSharePct": max_pair_share,
        "maxMonthSharePct": max_month_share,
        "recentHoldoutTradeCount": recent_count,
    }


def _summarize_event_pool(
    events: pd.DataFrame,
    timeframe: str,
    barrier_config: BarrierConfig,
    setup_name: str | None = None,
) -> dict[str, Any]:
    selected = events if setup_name is None else events[events["setupName"] == setup_name].copy()
    metrics = evaluate_trades(selected)
    splits = _time_splits(selected)
    pair_dist = _distribution(selected, "pair", limit=12)
    setup_dist = _distribution(selected, "setupName", limit=8)
    month_dist = _month_distribution(selected, limit=18)
    quality = _sample_quality(selected, metrics, splits, pair_dist, month_dist)
    first_date = pd.to_datetime(selected["signalDate"], utc=True).min().isoformat() if not selected.empty else None
    last_date = pd.to_datetime(selected["signalDate"], utc=True).max().isoformat() if not selected.empty else None
    return {
        "poolId": f"{timeframe}:{setup_name or 'all_setups'}:sl{barrier_config.stop_loss_pct}:h{barrier_config.horizon_bars}",
        "timeframe": timeframe,
        "setupName": setup_name or "all_setups",
        "barrierConfig": asdict(barrier_config),
        "firstSignalAt": first_date,
        "lastSignalAt": last_date,
        "metrics": metrics,
        "timeSplitMetrics": splits,
        "pairDistribution": pair_dist,
        "setupDistribution": setup_dist,
        "monthDistribution": month_dist,
        "sampleQuality": quality,
        "decision": {
            "candidateReadyForForwardConfirmation": bool(quality["sampleSufficiencyPassed"]),
            "localPaperCandidateApproved": bool(quality["targetMetricsPassed"]),
            "exchangeDryRunApproved": False,
            "liveTradingApproved": False,
        },
    }


def _rank_pools(pools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        pools,
        key=lambda row: (
            1 if row["sampleQuality"]["targetMetricsPassed"] else 0,
            1 if row["sampleQuality"]["sampleSufficiencyPassed"] else 0,
            row["metrics"].get("tradeCount") or 0,
            row["metrics"].get("profitFactor") or 0,
            row["metrics"].get("winRatePct") or 0,
            -(row["sampleQuality"].get("maxPairSharePct") or 0),
        ),
        reverse=True,
    )


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
                "fundingCoveragePct": _safe_pct(group["funding_rate"].notna().mean()),
                "markBasisCoveragePct": _safe_pct(group["mark_basis_pct"].notna().mean()),
            }
        )
    return {
        "panelRows": int(len(panel)),
        "dateStart": panel["date"].min().isoformat(),
        "dateEnd": panel["date"].max().isoformat(),
        "pairCount": int(panel["pair"].nunique()),
        "pairCoverage": rows,
    }


def run_event_pool_expansion(
    timeframes: list[str],
    pairs: list[str] | None = None,
    data_dir: Path = DEFAULT_DATA_DIR,
) -> dict[str, Any]:
    timeframe_reports: list[dict[str, Any]] = []
    all_pools: list[dict[str, Any]] = []

    for timeframe in timeframes:
        timeframe_pairs = pairs or discover_local_pairs(timeframe, data_dir=data_dir)
        panel_result = build_derivatives_feature_panel(pairs=timeframe_pairs, timeframe=timeframe, data_dir=data_dir)
        panel = panel_result.rows.dropna(subset=["close", "rsi14", "volume_ratio", "atr_pct"]).copy()
        coverage = _coverage_for_panel(panel)
        pools: list[dict[str, Any]] = []
        if not panel.empty:
            for barrier_config in _barrier_configs(timeframe):
                events = build_labeled_events(panel, barrier_config)
                if events.empty:
                    continue
                pools.append(_summarize_event_pool(events, timeframe, barrier_config, setup_name=None))
                for setup_name in sorted(events["setupName"].dropna().unique()):
                    pools.append(_summarize_event_pool(events, timeframe, barrier_config, setup_name=str(setup_name)))

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
                "barrierConfigCount": len(_barrier_configs(timeframe)),
                "poolCount": len(pools),
                "topPools": ranked[:12],
            }
        )

    ranked_all = _rank_pools(all_pools)
    reward_risk_ranked = sorted(
        ranked_all,
        key=lambda row: (
            row["metrics"].get("rewardRiskRatio") or 0,
            row["metrics"].get("tradeCount") or 0,
            row["metrics"].get("profitFactor") or 0,
        ),
        reverse=True,
    )
    sample_ready = [row for row in ranked_all if row["sampleQuality"]["sampleSufficiencyPassed"]]
    target_ready = [row for row in ranked_all if row["sampleQuality"]["targetMetricsPassed"]]
    generated_at = utc_now()
    return {
        "reportId": REPORT_ID,
        "version": VERSION,
        "status": "completed",
        "isMock": False,
        "generatedAt": generated_at,
        "objective": {
            "mode": "public_data_expansion_event_pool_diagnostics",
            "targetWinRatePct": MIN_TARGET_WIN_RATE_PCT,
            "targetRewardRiskRatio": MIN_TARGET_REWARD_RISK_RATIO,
            "antiOverfitRule": "Prefer broad sample coverage and stable holdout behavior over high in-sample win rate.",
            "note": "Win-rate target is intentionally lower than 55% because 2R reward/risk is not relaxed.",
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
            "highestRewardRiskRatio": (
                reward_risk_ranked[0]["metrics"].get("rewardRiskRatio") if reward_risk_ranked else None
            ),
            "topPoolIds": [row["poolId"] for row in ranked_all[:10]],
        },
        "topEventPools": ranked_all[:30],
        "highestRewardRiskPools": reward_risk_ranked[:15],
        "decision": {
            "eventPoolExpanded": True,
            "sampleSufficiencyReady": bool(sample_ready),
            "newLocalPaperCandidateApproved": False,
            "continueExistingLocalPaperMonitoring": True,
            "exchangeDryRunApproved": False,
            "liveTradingApproved": False,
            "reason": (
                "target_metrics_seen_but_requires_forward_confirmation"
                if target_ready
                else "sample_sufficient_event_pools_available"
                if sample_ready
                else "event_pool_still_too_sparse_or_concentrated"
            ),
        },
        "recommendations": _recommendations(sample_ready, target_ready, ranked_all),
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


def _recommendations(
    sample_ready: list[dict[str, Any]],
    target_ready: list[dict[str, Any]],
    ranked_all: list[dict[str, Any]],
) -> list[str]:
    if target_ready:
        best = target_ready[0]
        metrics = best["metrics"]
        return [
            "Do not promote this directly to exchange Dry-run; target metrics from event pools need forward confirmation.",
            (
                "Start a new forward-confirmation shadow/paper candidate only if the same pool remains stable "
                "after the next public-data refresh."
            ),
            (
                f"Best target-ready pool {best['poolId']}: trades={metrics.get('tradeCount')}, "
                f"winRate={metrics.get('winRatePct')}, rewardRisk={metrics.get('rewardRiskRatio')}, "
                f"profitFactor={metrics.get('profitFactor')}, maxDrawdown={metrics.get('maxDrawdownPct')}."
            ),
        ]
    if sample_ready:
        best = sample_ready[0]
        metrics = best["metrics"]
        return [
            "Event sample breadth is now enough for forward research, but target metrics did not fully pass.",
            "Keep local paper monitoring active and refresh public data again before any Dry-run review.",
            (
                f"Best sample-sufficient pool {best['poolId']}: trades={metrics.get('tradeCount')}, "
                f"winRate={metrics.get('winRatePct')}, rewardRisk={metrics.get('rewardRiskRatio')}, "
                f"profitFactor={metrics.get('profitFactor')}, maxDrawdown={metrics.get('maxDrawdownPct')}."
            ),
        ]
    best = ranked_all[0] if ranked_all else {}
    metrics = best.get("metrics", {})
    return [
        "The event pool is still too sparse or too concentrated for stronger conclusions.",
        "Download more public history and include more liquid OKX futures pairs before testing new candidate rules.",
        (
            f"Best observed pool {best.get('poolId')}: trades={metrics.get('tradeCount')}, "
            f"winRate={metrics.get('winRatePct')}, rewardRisk={metrics.get('rewardRiskRatio')}, "
            f"profitFactor={metrics.get('profitFactor')}."
            if best
            else "No event pools were created."
        ),
    ]


def write_summary(report: dict[str, Any], path: Path) -> None:
    decision = report["decision"]
    summary = report["eventPoolSummary"]
    lines = [
        "# V13.5.5 Event Pool Expansion Report",
        "",
        "This report expands public historical event samples and checks anti-overfit coverage. It does not approve exchange Dry-run or live trading.",
        "",
        "## Decision",
        "",
        f"- Event pool expanded: `{decision['eventPoolExpanded']}`",
        f"- Sample sufficiency ready: `{decision['sampleSufficiencyReady']}`",
        f"- New local paper candidate approved: `{decision['newLocalPaperCandidateApproved']}`",
        f"- Continue existing local paper monitoring: `{decision['continueExistingLocalPaperMonitoring']}`",
        f"- Exchange Dry-run approved: `{decision['exchangeDryRunApproved']}`",
        f"- Live trading approved: `{decision['liveTradingApproved']}`",
        f"- Reason: `{decision['reason']}`",
        "",
        "## Event Pool Summary",
        "",
        f"- Total pools: `{summary['totalPools']}`",
        f"- Sample-sufficient pools: `{summary['sampleSufficientPoolCount']}`",
        f"- Target-metric pools: `{summary['targetMetricPoolCount']}`",
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
    for pool in report.get("topEventPools", [])[:10]:
        metrics = pool.get("metrics") or {}
        quality = pool.get("sampleQuality") or {}
        lines.append(
            f"- `{pool.get('poolId')}`: trades=`{metrics.get('tradeCount')}`, "
            f"winRate=`{metrics.get('winRatePct')}`, RR=`{metrics.get('rewardRiskRatio')}`, "
            f"PF=`{metrics.get('profitFactor')}`, maxDD=`{metrics.get('maxDrawdownPct')}`, "
            f"sampleReady=`{quality.get('sampleSufficiencyPassed')}`, "
            f"targetReady=`{quality.get('targetMetricsPassed')}`, "
            f"fail=`{', '.join(quality.get('failReasons') or []) or 'none'}`, "
            f"targetFail=`{', '.join(quality.get('targetFailReasons') or []) or 'none'}`"
        )
    lines.extend(["", "## Highest Reward/Risk Pools", ""])
    for pool in report.get("highestRewardRiskPools", [])[:10]:
        metrics = pool.get("metrics") or {}
        quality = pool.get("sampleQuality") or {}
        lines.append(
            f"- `{pool.get('poolId')}`: trades=`{metrics.get('tradeCount')}`, "
            f"winRate=`{metrics.get('winRatePct')}`, RR=`{metrics.get('rewardRiskRatio')}`, "
            f"PF=`{metrics.get('profitFactor')}`, maxDD=`{metrics.get('maxDrawdownPct')}`, "
            f"targetReady=`{quality.get('targetMetricsPassed')}`, "
            f"targetFail=`{', '.join(quality.get('targetFailReasons') or []) or 'none'}`"
        )
    lines.extend(
        [
            "",
            "## Recommendations",
            "",
            *[f"- {item}" for item in report.get("recommendations", [])],
            "",
            "## Safety Boundary",
            "",
            "- Public local market data only.",
            "- No API key storage.",
            "- No Trade API.",
            "- No Withdraw API.",
            "- No real account reads.",
            "- No real position reads.",
            "- No real orders.",
            "- No automatic trading.",
            "- Exchange Dry-run remains disabled.",
            "",
        ]
    )
    write_text(path, "\n".join(lines))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeframes", default="1h,4h")
    parser.add_argument("--pairs", default=None)
    parser.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR))
    parser.add_argument("--output-report", default=str(DEFAULT_OUTPUT_REPORT))
    parser.add_argument("--output-summary", default=str(DEFAULT_OUTPUT_SUMMARY))
    parser.add_argument("--output-candidates", default=str(DEFAULT_OUTPUT_CANDIDATES))
    args = parser.parse_args()

    report = run_event_pool_expansion(
        timeframes=parse_csv(args.timeframes),
        pairs=parse_csv(args.pairs) or None,
        data_dir=Path(args.data_dir),
    )
    output_report = Path(args.output_report)
    output_summary = Path(args.output_summary)
    output_candidates = Path(args.output_candidates)
    write_json(output_report, _json_ready(report))
    write_summary(report, output_summary)
    write_json(output_candidates, _json_ready(report.get("topEventPools", [])))
    print(f"Wrote {output_report}")
    print(f"Wrote {output_summary}")
    print(f"Wrote {output_candidates}")
    print(f"decision={report.get('decision')}")
    print(f"eventPoolSummary={report.get('eventPoolSummary')}")


if __name__ == "__main__":
    main()
