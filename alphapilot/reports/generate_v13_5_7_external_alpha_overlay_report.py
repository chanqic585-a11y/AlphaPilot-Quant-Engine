"""Generate V13.5.7 external-reference Alpha101-style overlay report.

The report uses ideas from public projects as research inspiration only. It
does not copy external code or long text. It reads AlphaPilot local public data,
adds a compact Alpha101-style factor overlay, and tests fixed filters against
the existing high-reward event framework. It never uses API keys, reads real
accounts, creates orders, or auto trades.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from alphapilot.derivatives.feature_panel import DEFAULT_DATA_DIR, build_derivatives_feature_panel
from alphapilot.factors.alpha101_style_overlay import ALPHA101_STYLE_FACTOR_COLUMNS, add_alpha101_style_factors
from alphapilot.ml_gate.high_reward_event_setups import HIGH_REWARD_SETUP_NAMES, add_high_reward_event_setups
from alphapilot.ml_gate.high_reward_triple_barrier import build_high_reward_labeled_events
from alphapilot.ml_gate.probability_gate import evaluate_trades
from alphapilot.ml_gate.triple_barrier import BarrierConfig
from alphapilot.reports.generate_v13_5_1_expanded_relaxed_research_report import discover_local_pairs
from alphapilot.reports.generate_v13_5_6_high_reward_event_redesign_report import (
    _cost_adjusted_2r_stats,
    _coverage_for_panel,
    _distribution,
    _month_distribution,
    _time_splits,
)
from alphapilot.reports.generate_v13_5_derivatives_ml_strategy_report import _json_ready, write_json, write_text


REPORT_ID = "v13_5_7_external_alpha_overlay_report"
VERSION = "V13.5.7"
DEFAULT_OUTPUT_REPORT = Path("reports/v13_5_7_external_alpha_overlay_report.json")
DEFAULT_OUTPUT_SUMMARY = Path("reports/v13_5_7_external_alpha_overlay_summary.md")
DEFAULT_OUTPUT_CANDIDATES = Path("reports/v13_5_7_alpha_overlay_candidates.json")

TARGET_R_MULTIPLE = 2.0
MIN_OVERLAY_TRADES = 80
MIN_OVERLAY_PAIRS = 12
MIN_OVERLAY_MONTHS = 8
MIN_OVERLAY_WIN_RATE_PCT = 45.0
MIN_OVERLAY_PROFIT_FACTOR = 1.5
MAX_OVERLAY_DRAWDOWN_PCT = 45.0
MIN_RECENT_HOLDOUT_TRADES = 16
MIN_RECENT_PROFIT_FACTOR = 0.9
MIN_COST_ADJUSTED_2R_CLOSENESS = 0.75


EXTERNAL_REFERENCE_METADATA = [
    {
        "name": "yydhYYDH/alpha101",
        "url": "https://github.com/yydhYYDH/alpha101",
        "license": "unknown_from_raw_license_fetch",
        "summary": (
            "Crypto factor research toolkit with Alpha101-style expressions, factor panels, "
            "factor evaluation, search, backtesting, and Freqtrade-based public kline data ingestion."
        ),
        "citation": "GitHub repository README and file tree reviewed on 2026-07-06.",
        "usageInAlphaPilot": (
            "Concept reference only: cross-sectional ranks, time-series ranks, rolling correlation, "
            "decay-style factors, and explicit research-only boundaries."
        ),
        "copiedCodeOrLongText": False,
    },
    {
        "name": "ryckli/CryptoAgentPro.beta",
        "url": "https://github.com/ryckli/CryptoAgentPro.beta",
        "license": "MIT",
        "summary": (
            "Crypto strategy research architecture with strategy modules, backtesting, AI context, "
            "paper/testnet separation, and a risk gateway concept."
        ),
        "citation": "GitHub repository README, license, and test-report references reviewed on 2026-07-06.",
        "usageInAlphaPilot": (
            "Concept reference only: strict mode separation, risk gateway thinking, and public-data-first "
            "research workflows. No execution integration was adopted."
        ),
        "copiedCodeOrLongText": False,
    },
]


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def parse_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _barrier_configs(timeframe: str) -> list[BarrierConfig]:
    if timeframe == "1h":
        configs = [(0.02, 24), (0.025, 30), (0.03, 36)]
    elif timeframe == "4h":
        configs = [(0.04, 12), (0.05, 18), (0.06, 24), (0.08, 30)]
    else:
        configs = [(0.02, 32), (0.025, 48)]
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


def _overlay_specs() -> list[dict[str, Any]]:
    return [
        {
            "overlayId": "alpha_long_rebound_pressure_watch",
            "direction": "long",
            "description": "Extreme-volume rebound context with weak cross-sectional returns and high rebound pressure.",
        },
        {
            "overlayId": "alpha_long_liquid_rebound_confirmed",
            "direction": "long",
            "description": "Rebound context requiring cross-sectional liquidity quality and non-crowded return-volume behavior.",
        },
        {
            "overlayId": "alpha_short_exhaustion_pressure_watch",
            "direction": "short",
            "description": "Relative-strength exhaustion context with high cross-sectional return and volume pressure.",
        },
        {
            "overlayId": "alpha_short_liquid_exhaustion_confirmed",
            "direction": "short",
            "description": "Short exhaustion context with liquidity quality and upper-tail Bollinger pressure.",
        },
        {
            "overlayId": "alpha_sideways_rejection_control",
            "direction": "short",
            "description": "Sideways BTC failed-breakout rejection with high Bollinger rank and stable liquidity quality.",
        },
    ]


def _apply_overlay_filter(events: pd.DataFrame, overlay_id: str) -> pd.Series:
    if events.empty:
        return pd.Series([], dtype=bool)

    if overlay_id == "alpha_long_rebound_pressure_watch":
        return (
            (events["direction"] == "long")
            & (events["volume_ratio"] >= 2.8)
            & (events["btc_return_3"] <= -0.04)
            & (events["bollinger_z"] <= -1.5)
            & (events["cs_return_12_rank"] <= 0.25)
            & (events["cs_volume_ratio_rank"] >= 0.75)
            & (events["alpha_rebound_pressure"] >= 0.18)
            & (events["alpha_liquidity_quality"] >= 0.35)
        )
    if overlay_id == "alpha_long_liquid_rebound_confirmed":
        return (
            (events["direction"] == "long")
            & (events["volume_ratio"] >= 2.4)
            & (events["bollinger_z"] <= -1.2)
            & (events["cs_return_12_rank"] <= 0.35)
            & (events["ts_close_location_rank_24"] >= 0.5)
            & (events["ts_return_volume_corr_24"] <= 0.35)
            & (events["alpha_liquidity_quality"] >= 0.45)
        )
    if overlay_id == "alpha_short_exhaustion_pressure_watch":
        return (
            (events["direction"] == "short")
            & (events["volume_ratio"] >= 2.8)
            & (events["relative_return_6"] > 0.04)
            & (events["mark_basis_pct"] > -0.001)
            & (events["mark_basis_pct"] <= -0.0002)
            & (events["cs_return_12_rank"] >= 0.75)
            & (events["cs_volume_ratio_rank"] >= 0.75)
            & (events["alpha_exhaustion_pressure"] >= 0.15)
        )
    if overlay_id == "alpha_short_liquid_exhaustion_confirmed":
        return (
            (events["direction"] == "short")
            & (events["rsi14"] > 68)
            & (events["volume_ratio"] >= 2.2)
            & (events["cs_return_12_rank"] >= 0.7)
            & (events["ts_bollinger_z_rank_24"] >= 0.6)
            & (events["alpha_exhaustion_pressure"] >= 0.12)
            & (events["alpha_liquidity_quality"] >= 0.35)
        )
    if overlay_id == "alpha_sideways_rejection_control":
        return (
            (events["setupName"] == "hr_short_failed_breakout_rejection")
            & (events["btc_regime"] == "sideways")
            & (events["btc_return_3"] > 0.015)
            & (events["btc_return_3"] <= 0.04)
            & (events["cs_bollinger_z_rank"] >= 0.72)
            & (events["alpha_liquidity_quality"] >= 0.35)
        )
    return pd.Series([False] * len(events), index=events.index)


def _factor_snapshot(events: pd.DataFrame) -> dict[str, Any]:
    if events.empty:
        return {"factorColumns": ALPHA101_STYLE_FACTOR_COLUMNS, "availableRows": 0, "means": {}, "medians": {}}
    means: dict[str, Any] = {}
    medians: dict[str, Any] = {}
    availability: dict[str, Any] = {}
    for column in ALPHA101_STYLE_FACTOR_COLUMNS:
        if column not in events.columns:
            means[column] = None
            medians[column] = None
            availability[column] = 0.0
            continue
        series = pd.to_numeric(events[column], errors="coerce")
        means[column] = round(float(series.mean()), 6) if series.notna().any() else None
        medians[column] = round(float(series.median()), 6) if series.notna().any() else None
        availability[column] = round(float(series.notna().mean() * 100), 4)
    return {
        "factorColumns": ALPHA101_STYLE_FACTOR_COLUMNS,
        "availableRows": int(len(events)),
        "availabilityPct": availability,
        "means": means,
        "medians": medians,
    }


def _sample_quality(events: pd.DataFrame, metrics: dict[str, Any], splits: dict[str, Any]) -> dict[str, Any]:
    fail_reasons: list[str] = []
    warning_reasons: list[str] = []
    trade_count = int(metrics.get("tradeCount") or 0)
    unique_pairs = int(events["pair"].nunique()) if not events.empty and "pair" in events else 0
    unique_months = int(pd.to_datetime(events["signalDate"], utc=True).dt.strftime("%Y-%m").nunique()) if not events.empty else 0
    recent = splits.get("recent20") or {}
    recent_trades = int(recent.get("tradeCount") or 0)

    if trade_count < MIN_OVERLAY_TRADES:
        fail_reasons.append("trade_count_below_80")
    if unique_pairs < MIN_OVERLAY_PAIRS:
        fail_reasons.append("pair_coverage_below_12")
    if unique_months < MIN_OVERLAY_MONTHS:
        fail_reasons.append("month_coverage_below_8")
    if recent_trades < MIN_RECENT_HOLDOUT_TRADES:
        fail_reasons.append("recent_holdout_sample_below_16")
    if (metrics.get("winRatePct") or 0) < MIN_OVERLAY_WIN_RATE_PCT:
        fail_reasons.append("win_rate_below_45")
    if (metrics.get("profitFactor") or 0) < MIN_OVERLAY_PROFIT_FACTOR:
        fail_reasons.append("profit_factor_below_1_5")
    if (metrics.get("maxDrawdownPct") or 999) > MAX_OVERLAY_DRAWDOWN_PCT:
        fail_reasons.append("max_drawdown_above_45")
    if (metrics.get("totalReturnPct") or 0) <= 0:
        fail_reasons.append("total_return_not_positive")
    if recent_trades >= MIN_RECENT_HOLDOUT_TRADES and (recent.get("profitFactor") or 0) < MIN_RECENT_PROFIT_FACTOR:
        fail_reasons.append("recent_profit_factor_below_0_9")
    elif recent_trades < MIN_RECENT_HOLDOUT_TRADES:
        warning_reasons.append("recent_holdout_small")

    return {
        "overlaySamplePassed": not fail_reasons,
        "failReasons": fail_reasons,
        "warningReasons": warning_reasons,
        "tradeCount": trade_count,
        "uniquePairs": unique_pairs,
        "uniqueMonths": unique_months,
        "recentHoldoutTradeCount": recent_trades,
    }


def _overlay_decision(
    metrics: dict[str, Any],
    sample: dict[str, Any],
    cost_stats: dict[str, Any],
) -> dict[str, Any]:
    fail_reasons = list(sample.get("failReasons") or [])
    closeness = cost_stats.get("observedToCostAdjusted2RCloseness")
    if closeness is None or closeness < MIN_COST_ADJUSTED_2R_CLOSENESS:
        fail_reasons.append("observed_rr_not_close_to_cost_adjusted_2r")
    approved = not fail_reasons
    return {
        "targetRMultipleUnchanged": True,
        "alphaOverlayComputed": True,
        "localPaperWatchApproved": approved,
        "newFormalPaperCandidateApproved": False,
        "exchangeDryRunApproved": False,
        "liveTradingApproved": False,
        "failReasons": fail_reasons,
        "reason": (
            "approved_for_local_paper_watch_only"
            if approved
            else "alpha_overlay_filter_requires_more_forward_evidence"
        ),
        "note": "Approval here can only mean local paper watch; it is not exchange Dry-run or live trading.",
        "observedMetrics": {
            "tradeCount": metrics.get("tradeCount"),
            "winRatePct": metrics.get("winRatePct"),
            "rewardRiskRatio": metrics.get("rewardRiskRatio"),
            "profitFactor": metrics.get("profitFactor"),
            "maxDrawdownPct": metrics.get("maxDrawdownPct"),
        },
    }


def _summarize_overlay(
    events: pd.DataFrame,
    timeframe: str,
    config: BarrierConfig,
    overlay_spec: dict[str, Any],
) -> dict[str, Any] | None:
    mask = _apply_overlay_filter(events, overlay_spec["overlayId"])
    selected = events[mask].copy()
    if selected.empty:
        return None
    metrics = evaluate_trades(selected)
    splits = _time_splits(selected)
    pair_dist = _distribution(selected, "pair", limit=15)
    month_dist = _month_distribution(selected, limit=18)
    setup_dist = _distribution(selected, "setupName", limit=8)
    cost_stats = _cost_adjusted_2r_stats(config, metrics)
    sample = _sample_quality(selected, metrics, splits)
    decision = _overlay_decision(metrics, sample, cost_stats)
    return {
        "overlayId": overlay_spec["overlayId"],
        "poolId": f"{timeframe}:{overlay_spec['overlayId']}:sl{config.stop_loss_pct}:h{config.horizon_bars}",
        "description": overlay_spec["description"],
        "direction": overlay_spec["direction"],
        "timeframe": timeframe,
        "barrierConfig": asdict(config),
        "metrics": metrics,
        "timeSplitMetrics": splits,
        "costAdjusted2R": cost_stats,
        "factorSnapshot": _factor_snapshot(selected),
        "pairDistribution": pair_dist,
        "monthDistribution": month_dist,
        "setupDistribution": setup_dist,
        "sampleQuality": sample,
        "decision": decision,
    }


def _rank_overlays(overlays: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        overlays,
        key=lambda row: (
            1 if row["decision"].get("localPaperWatchApproved") else 0,
            row["metrics"].get("profitFactor") or 0,
            row["timeSplitMetrics"].get("recent20", {}).get("profitFactor") or 0,
            row["metrics"].get("winRatePct") or 0,
            row["costAdjusted2R"].get("observedToCostAdjusted2RCloseness") or 0,
            row["metrics"].get("tradeCount") or 0,
            -(row["metrics"].get("maxDrawdownPct") or 999),
        ),
        reverse=True,
    )


def _recommendations(approved: list[dict[str, Any]], ranked: list[dict[str, Any]]) -> list[str]:
    if approved:
        best = approved[0]
        metrics = best["metrics"]
        return [
            "Keep the existing 2R barrier unchanged and start local paper watch for the best Alpha101-style overlay only.",
            "Do not promote this to exchange Dry-run until a fresh forward sample confirms the same behavior.",
            (
                f"Best overlay {best['poolId']}: trades={metrics.get('tradeCount')}, "
                f"winRate={metrics.get('winRatePct')}, PF={metrics.get('profitFactor')}, "
                f"RR={metrics.get('rewardRiskRatio')}, maxDD={metrics.get('maxDrawdownPct')}."
            ),
        ]
    if ranked:
        best = ranked[0]
        metrics = best["metrics"]
        return [
            "The Alpha101-style overlay produced measurable filters, but none are strong enough for local paper watch approval.",
            "Next step should expand public data sources or add independent liquidity/open-interest context, not lower the 2R target.",
            (
                f"Best observed overlay {best['poolId']}: trades={metrics.get('tradeCount')}, "
                f"winRate={metrics.get('winRatePct')}, PF={metrics.get('profitFactor')}, "
                f"RR={metrics.get('rewardRiskRatio')}, maxDD={metrics.get('maxDrawdownPct')}."
            ),
        ]
    return [
        "No Alpha101-style overlay filters produced enough events.",
        "Keep V13.5.6 exploratory local paper watch only and gather more public data before changing strategy direction.",
    ]


def run_external_alpha_overlay(
    timeframes: list[str],
    pairs: list[str] | None = None,
    data_dir: Path = DEFAULT_DATA_DIR,
) -> dict[str, Any]:
    timeframe_reports: list[dict[str, Any]] = []
    all_overlays: list[dict[str, Any]] = []

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
        factor_panel = add_alpha101_style_factors(panel) if not panel.empty else panel
        prepared_panel = add_high_reward_event_setups(factor_panel) if not factor_panel.empty else factor_panel
        coverage = _coverage_for_panel(prepared_panel)
        setup_signal_counts: dict[str, int] = {}
        overlays: list[dict[str, Any]] = []
        if not prepared_panel.empty:
            for setup_name in HIGH_REWARD_SETUP_NAMES:
                setup_signal_counts[setup_name] = int(prepared_panel[setup_name].fillna(False).sum())
            for barrier_config in _barrier_configs(timeframe):
                events = build_high_reward_labeled_events(prepared_panel, barrier_config)
                if events.empty:
                    continue
                for overlay_spec in _overlay_specs():
                    overlay_summary = _summarize_overlay(events, timeframe, barrier_config, overlay_spec)
                    if overlay_summary is not None:
                        overlays.append(overlay_summary)

        ranked = _rank_overlays(overlays)
        all_overlays.extend(ranked)
        timeframe_reports.append(
            {
                "timeframe": timeframe,
                "requestedPairs": timeframe_pairs,
                "loadedPairs": panel_result.loaded_pairs,
                "missingPairs": panel_result.missing_pairs,
                "missingOptionalSources": panel_result.missing_optional_sources,
                "coverage": coverage,
                "factorColumns": ALPHA101_STYLE_FACTOR_COLUMNS,
                "setupSignalCounts": setup_signal_counts,
                "barrierConfigCount": len(_barrier_configs(timeframe)),
                "overlayFilterCount": len(_overlay_specs()),
                "overlayPoolCount": len(ranked),
                "topOverlays": ranked[:12],
            }
        )

    ranked_all = _rank_overlays(all_overlays)
    approved = [row for row in ranked_all if row["decision"].get("localPaperWatchApproved")]
    generated_at = utc_now()
    return {
        "reportId": REPORT_ID,
        "version": VERSION,
        "status": "completed",
        "isMock": False,
        "generatedAt": generated_at,
        "objective": {
            "mode": "external_reference_alpha101_style_overlay",
            "targetRMultiple": TARGET_R_MULTIPLE,
            "fixedOverlayFilters": True,
            "antiOverfitRule": (
                "External references are used as concept inspiration only; fixed filters are evaluated "
                "against local public history without in-sample threshold search."
            ),
        },
        "externalReferenceMetadata": EXTERNAL_REFERENCE_METADATA,
        "dataSource": {
            "localPublicDataDir": str(data_dir),
            "timeframes": timeframes,
            "pairsMode": "explicit" if pairs else "discover_local_pairs",
            "publicDataOnly": True,
            "externalWebsiteDataDownloadedInThisRun": False,
            "openInterestStatus": "unavailable_not_fabricated",
            "fundingStatus": "used_when_local_public_files_exist",
        },
        "timeframes": timeframe_reports,
        "overlaySummary": {
            "totalOverlayPools": len(ranked_all),
            "localPaperWatchApprovedCount": len(approved),
            "topOverlayIds": [row["poolId"] for row in ranked_all[:10]],
        },
        "topAlphaOverlayPools": ranked_all[:30],
        "approvedLocalPaperWatchPools": approved[:10],
        "decision": {
            "externalReferencesReviewed": True,
            "alpha101StyleOverlayComputed": True,
            "targetRMultipleUnchanged": True,
            "localPaperWatchApproved": bool(approved),
            "localPaperWatchPoolId": approved[0]["poolId"] if approved else None,
            "newFormalPaperCandidateApproved": False,
            "exchangeDryRunApproved": False,
            "liveTradingApproved": False,
            "reason": (
                "alpha_overlay_local_paper_watch_only"
                if approved
                else "alpha_overlay_no_local_paper_watch_pass"
            ),
        },
        "recommendations": _recommendations(approved, ranked_all),
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
    summary = report["overlaySummary"]
    lines = [
        "# V13.5.7 External Alpha Overlay Report",
        "",
        "This report references public GitHub projects as research inspiration only. It stores URL, license, summary, and citation metadata, and does not copy external code or long text.",
        "",
        "## Decision",
        "",
        f"- External references reviewed: `{decision['externalReferencesReviewed']}`",
        f"- Alpha101-style overlay computed: `{decision['alpha101StyleOverlayComputed']}`",
        f"- Target R multiple unchanged: `{decision['targetRMultipleUnchanged']}`",
        f"- Local paper watch approved: `{decision['localPaperWatchApproved']}`",
        f"- Local paper watch pool: `{decision['localPaperWatchPoolId']}`",
        f"- New formal paper candidate approved: `{decision['newFormalPaperCandidateApproved']}`",
        f"- Exchange Dry-run approved: `{decision['exchangeDryRunApproved']}`",
        f"- Live trading approved: `{decision['liveTradingApproved']}`",
        f"- Reason: `{decision['reason']}`",
        "",
        "## External References",
        "",
    ]
    for reference in report.get("externalReferenceMetadata", []):
        lines.append(
            f"- `{reference['name']}`: url=`{reference['url']}`, license=`{reference['license']}`, "
            f"usage=`{reference['usageInAlphaPilot']}`"
        )
    lines.extend(
        [
            "",
            "## Overlay Summary",
            "",
            f"- Total overlay pools: `{summary['totalOverlayPools']}`",
            f"- Local paper watch approved count: `{summary['localPaperWatchApprovedCount']}`",
            "",
            "## Timeframe Coverage",
            "",
        ]
    )
    for item in report.get("timeframes", []):
        coverage = item.get("coverage") or {}
        lines.append(
            f"- `{item.get('timeframe')}`: pairs=`{coverage.get('pairCount')}`, "
            f"panelRows=`{coverage.get('panelRows')}`, "
            f"range=`{coverage.get('dateStart')}` to `{coverage.get('dateEnd')}`, "
            f"overlayPools=`{item.get('overlayPoolCount')}`"
        )
    lines.extend(["", "## Top Alpha Overlay Pools", ""])
    for pool in report.get("topAlphaOverlayPools", [])[:12]:
        metrics = pool.get("metrics") or {}
        decision_row = pool.get("decision") or {}
        cost = pool.get("costAdjusted2R") or {}
        recent = (pool.get("timeSplitMetrics") or {}).get("recent20") or {}
        lines.append(
            f"- `{pool.get('poolId')}`: trades=`{metrics.get('tradeCount')}`, "
            f"winRate=`{metrics.get('winRatePct')}`, RR=`{metrics.get('rewardRiskRatio')}`, "
            f"PF=`{metrics.get('profitFactor')}`, maxDD=`{metrics.get('maxDrawdownPct')}`, "
            f"recentPF=`{recent.get('profitFactor')}`, "
            f"2Rclose=`{cost.get('observedToCostAdjusted2RCloseness')}`, "
            f"watch=`{decision_row.get('localPaperWatchApproved')}`, "
            f"fail=`{', '.join(decision_row.get('failReasons') or []) or 'none'}`"
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
    parser = argparse.ArgumentParser(description="Generate V13.5.7 external Alpha overlay report.")
    parser.add_argument("--timeframes", default="1h,4h")
    parser.add_argument("--pairs", default=None)
    parser.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR))
    parser.add_argument("--output-report", default=str(DEFAULT_OUTPUT_REPORT))
    parser.add_argument("--output-summary", default=str(DEFAULT_OUTPUT_SUMMARY))
    parser.add_argument("--output-candidates", default=str(DEFAULT_OUTPUT_CANDIDATES))
    args = parser.parse_args()

    report = run_external_alpha_overlay(
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
                "approvedLocalPaperWatchPools": report["approvedLocalPaperWatchPools"],
                "topAlphaOverlayPools": report["topAlphaOverlayPools"][:10],
            }
        ),
    )
    print(f"Wrote {args.output_report}")
    print(f"Wrote {args.output_summary}")
    print(f"Wrote {args.output_candidates}")
    print(f"decision={report.get('decision')}")
    print(f"overlaySummary={report.get('overlaySummary')}")


if __name__ == "__main__":
    main()
