"""Generate V13.5.8 adaptive ML factor discovery report.

This report adds an auditable machine-learning layer without external ML
dependencies. It learns factor threshold rules from past folds only, applies
them to later folds, and reports whether any learned candidate is suitable for
local paper watch. It does not use API keys, account data, order endpoints, or
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
from alphapilot.factors.alpha101_style_overlay import add_alpha101_style_factors
from alphapilot.ml_gate.adaptive_factor_learner import (
    ADAPTIVE_FACTOR_COLUMNS,
    AdaptiveFactorLearnerConfig,
    learn_adaptive_factor_rules,
)
from alphapilot.ml_gate.high_reward_event_setups import HIGH_REWARD_SETUP_NAMES, add_high_reward_event_setups
from alphapilot.ml_gate.high_reward_triple_barrier import build_high_reward_labeled_events
from alphapilot.ml_gate.probability_gate import evaluate_trades
from alphapilot.ml_gate.strategy_evolution_schema import build_strategy_evolution_schema
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


REPORT_ID = "v13_5_8_adaptive_ml_factor_report"
VERSION = "V13.5.8"
DEFAULT_OUTPUT_REPORT = Path("reports/v13_5_8_adaptive_ml_factor_report.json")
DEFAULT_OUTPUT_SUMMARY = Path("reports/v13_5_8_adaptive_ml_factor_summary.md")
DEFAULT_OUTPUT_CANDIDATES = Path("reports/v13_5_8_adaptive_ml_candidates.json")
DEFAULT_OUTPUT_EVOLUTION_SCHEMA = Path("reports/v13_5_8_strategy_evolution_sample_schema.json")

TARGET_R_MULTIPLE = 2.0
MIN_WATCH_TRADES = 80
MIN_WATCH_PAIRS = 10
MIN_WATCH_MONTHS = 8
MIN_WATCH_WIN_RATE_PCT = 45.0
MIN_WATCH_PROFIT_FACTOR = 1.45
MAX_WATCH_DRAWDOWN_PCT = 45.0
MIN_WATCH_2R_CLOSENESS = 0.70
MIN_FOLDS_WITH_TRADES = 3
MAX_SINGLE_FOLD_SHARE_PCT = 55.0


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


def _fold_stability(selected: pd.DataFrame) -> dict[str, Any]:
    if selected.empty or "adaptiveFold" not in selected.columns:
        return {
            "foldsWithTrades": 0,
            "maxSingleFoldSharePct": 0.0,
            "foldDistribution": [],
            "stableEnoughForWatch": False,
            "failReasons": ["no_adaptive_fold_trades"],
        }
    total = len(selected)
    distribution = []
    for fold, count in selected["adaptiveFold"].value_counts().sort_index().items():
        distribution.append({"fold": int(fold), "tradeCount": int(count), "sharePct": round(float(count / total * 100), 4)})
    folds = len(distribution)
    max_share = max([row["sharePct"] for row in distribution], default=0.0)
    fail_reasons: list[str] = []
    if folds < MIN_FOLDS_WITH_TRADES:
        fail_reasons.append("folds_with_trades_below_3")
    if max_share > MAX_SINGLE_FOLD_SHARE_PCT:
        fail_reasons.append("single_fold_share_above_55pct")
    return {
        "foldsWithTrades": folds,
        "maxSingleFoldSharePct": max_share,
        "foldDistribution": distribution,
        "stableEnoughForWatch": not fail_reasons,
        "failReasons": fail_reasons,
    }


def _sample_quality(selected: pd.DataFrame, metrics: dict[str, Any], cost_stats: dict[str, Any]) -> dict[str, Any]:
    fail_reasons: list[str] = []
    if selected.empty:
        return {
            "watchSamplePassed": False,
            "failReasons": ["no_selected_events"],
            "uniquePairs": 0,
            "uniqueMonths": 0,
        }
    trade_count = int(metrics.get("tradeCount") or 0)
    unique_pairs = int(selected["pair"].nunique()) if "pair" in selected.columns else 0
    unique_months = int(pd.to_datetime(selected["signalDate"], utc=True).dt.strftime("%Y-%m").nunique())
    if trade_count < MIN_WATCH_TRADES:
        fail_reasons.append("trade_count_below_80")
    if unique_pairs < MIN_WATCH_PAIRS:
        fail_reasons.append("pair_coverage_below_10")
    if unique_months < MIN_WATCH_MONTHS:
        fail_reasons.append("month_coverage_below_8")
    if (metrics.get("winRatePct") or 0) < MIN_WATCH_WIN_RATE_PCT:
        fail_reasons.append("win_rate_below_45")
    if (metrics.get("profitFactor") or 0) < MIN_WATCH_PROFIT_FACTOR:
        fail_reasons.append("profit_factor_below_1_45")
    if (metrics.get("maxDrawdownPct") or 999) > MAX_WATCH_DRAWDOWN_PCT:
        fail_reasons.append("max_drawdown_above_45")
    if (metrics.get("totalReturnPct") or 0) <= 0:
        fail_reasons.append("total_return_not_positive")
    closeness = cost_stats.get("observedToCostAdjusted2RCloseness")
    if closeness is None or closeness < MIN_WATCH_2R_CLOSENESS:
        fail_reasons.append("observed_rr_not_close_to_cost_adjusted_2r")
    return {
        "watchSamplePassed": not fail_reasons,
        "failReasons": fail_reasons,
        "uniquePairs": unique_pairs,
        "uniqueMonths": unique_months,
    }


def _latest_training_samples(selected: pd.DataFrame, limit: int = 60) -> list[dict[str, Any]]:
    if selected.empty:
        return []
    columns = [
        "pair",
        "timeframe",
        "setupName",
        "direction",
        "signalDate",
        "entryDate",
        "exitDate",
        "exitReason",
        "netReturnPct",
        "rMultiple",
        "isWin",
        "adaptiveFold",
        "adaptiveRuleHits",
        "adaptiveRuleHitCount",
        "rsi14",
        "return_12",
        "volume_ratio",
        "bollinger_z",
        "btc_return_3",
        "relative_return_6",
        "alpha_rebound_pressure",
        "alpha_exhaustion_pressure",
        "alpha_liquidity_quality",
    ]
    available = [column for column in columns if column in selected.columns]
    sample = selected.sort_values("signalDate", ascending=False).head(limit)[available]
    return _json_ready(sample.to_dict(orient="records"))


def _summarize_adaptive_candidate(
    events: pd.DataFrame,
    timeframe: str,
    config: BarrierConfig,
    learner_config: AdaptiveFactorLearnerConfig,
) -> dict[str, Any] | None:
    if events.empty:
        return None
    learned = learn_adaptive_factor_rules(events, factor_columns=ADAPTIVE_FACTOR_COLUMNS, config=learner_config)
    selected = learned["selectedEvents"]
    metrics = learned["selectedMetrics"]
    if selected.empty:
        return {
            "poolId": f"{timeframe}:adaptive_ml_all_high_reward:sl{config.stop_loss_pct}:h{config.horizon_bars}",
            "timeframe": timeframe,
            "barrierConfig": asdict(config),
            "learnerConfig": asdict(learner_config),
            "selectedMetrics": metrics,
            "baselineTestMetrics": learned["baselineTestMetrics"],
            "sampleQuality": {"watchSamplePassed": False, "failReasons": ["no_selected_events"]},
            "foldStability": _fold_stability(selected),
            "learnedRules": learned["learnedRules"],
            "rulePerformance": learned["rulePerformance"],
            "decision": {
                "adaptiveMLComputed": True,
                "localPaperWatchApproved": False,
                "exchangeDryRunApproved": False,
                "liveTradingApproved": False,
                "reason": "no_selected_events",
            },
        }
    splits = _time_splits(selected)
    cost_stats = _cost_adjusted_2r_stats(config, metrics)
    sample = _sample_quality(selected, metrics, cost_stats)
    stability = _fold_stability(selected)
    fail_reasons = [*sample.get("failReasons", []), *stability.get("failReasons", [])]
    approved = not fail_reasons
    return {
        "poolId": f"{timeframe}:adaptive_ml_all_high_reward:sl{config.stop_loss_pct}:h{config.horizon_bars}",
        "timeframe": timeframe,
        "barrierConfig": asdict(config),
        "learnerConfig": asdict(learner_config),
        "selectedMetrics": metrics,
        "baselineTestMetrics": learned["baselineTestMetrics"],
        "costAdjusted2R": cost_stats,
        "timeSplitMetrics": splits,
        "sampleQuality": sample,
        "foldStability": stability,
        "pairDistribution": _distribution(selected, "pair", limit=15),
        "setupDistribution": _distribution(selected, "setupName", limit=8),
        "monthDistribution": _month_distribution(selected, limit=18),
        "learnedRules": learned["learnedRules"][:50],
        "rulePerformance": learned["rulePerformance"][:30],
        "trainingSamplePreview": _latest_training_samples(selected, limit=25),
        "decision": {
            "adaptiveMLComputed": True,
            "targetRMultipleUnchanged": True,
            "localPaperWatchApproved": approved,
            "newFormalPaperCandidateApproved": False,
            "exchangeDryRunApproved": False,
            "liveTradingApproved": False,
            "failReasons": fail_reasons,
            "reason": "adaptive_ml_local_paper_watch_only" if approved else "adaptive_ml_requires_more_stability",
        },
    }


def _rank_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        candidates,
        key=lambda row: (
            1 if row["decision"].get("localPaperWatchApproved") else 0,
            row["selectedMetrics"].get("profitFactor") or 0,
            row["selectedMetrics"].get("winRatePct") or 0,
            row.get("costAdjusted2R", {}).get("observedToCostAdjusted2RCloseness") or 0,
            row["selectedMetrics"].get("tradeCount") or 0,
            -(row["selectedMetrics"].get("maxDrawdownPct") or 999),
        ),
        reverse=True,
    )


def _recommendations(approved: list[dict[str, Any]], ranked: list[dict[str, Any]]) -> list[str]:
    if approved:
        best = approved[0]
        metrics = best["selectedMetrics"]
        return [
            "Start local paper watch for the best adaptive ML candidate only; keep exchange Dry-run disabled.",
            "Use the strategy evolution sample schema to collect future local paper and manual-review outcomes.",
            "Retrain offline only after fresh samples accumulate; do not let the learner create orders or bypass risk review.",
            (
                f"Best adaptive pool {best['poolId']}: trades={metrics.get('tradeCount')}, "
                f"winRate={metrics.get('winRatePct')}, PF={metrics.get('profitFactor')}, "
                f"RR={metrics.get('rewardRiskRatio')}, maxDD={metrics.get('maxDrawdownPct')}."
            ),
        ]
    if ranked:
        best = ranked[0]
        metrics = best["selectedMetrics"]
        return [
            "Adaptive factor learning ran, but no candidate passed the local paper watch gate.",
            "Keep collecting public data and use paper/manual outcomes as future training samples after independent validation.",
            (
                f"Best observed adaptive pool {best['poolId']}: trades={metrics.get('tradeCount')}, "
                f"winRate={metrics.get('winRatePct')}, PF={metrics.get('profitFactor')}, "
                f"RR={metrics.get('rewardRiskRatio')}, maxDD={metrics.get('maxDrawdownPct')}."
            ),
        ]
    return ["No adaptive ML candidates were generated from the current event universe."]


def run_adaptive_ml_factor_report(
    timeframes: list[str],
    pairs: list[str] | None = None,
    data_dir: Path = DEFAULT_DATA_DIR,
) -> dict[str, Any]:
    learner_config = AdaptiveFactorLearnerConfig()
    timeframe_reports: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []

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
        timeframe_candidates: list[dict[str, Any]] = []
        if not prepared_panel.empty:
            for setup_name in HIGH_REWARD_SETUP_NAMES:
                setup_signal_counts[setup_name] = int(prepared_panel[setup_name].fillna(False).sum())
            for barrier_config in _barrier_configs(timeframe):
                events = build_high_reward_labeled_events(prepared_panel, barrier_config)
                summary = _summarize_adaptive_candidate(events, timeframe, barrier_config, learner_config)
                if summary is not None:
                    timeframe_candidates.append(summary)

        ranked_timeframe = _rank_candidates(timeframe_candidates)
        candidates.extend(ranked_timeframe)
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
                "adaptiveCandidateCount": len(ranked_timeframe),
                "topAdaptiveCandidates": ranked_timeframe[:8],
            }
        )

    ranked = _rank_candidates(candidates)
    approved = [row for row in ranked if row["decision"].get("localPaperWatchApproved")]
    return {
        "reportId": REPORT_ID,
        "version": VERSION,
        "status": "completed",
        "isMock": False,
        "generatedAt": utc_now(),
        "objective": {
            "mode": "adaptive_ml_factor_discovery",
            "targetRMultiple": TARGET_R_MULTIPLE,
            "mlApproach": "train-only quantile threshold learner with walk-forward validation",
            "externalMLPackagesUsed": False,
            "antiOverfitRule": (
                "Rules are learned only from prior folds and evaluated on later folds. "
                "Approval is limited to local paper watch and cannot create orders."
            ),
        },
        "dataSource": {
            "localPublicDataDir": str(data_dir),
            "timeframes": timeframes,
            "pairsMode": "explicit" if pairs else "discover_local_pairs",
            "publicDataOnly": True,
            "externalWebsiteDataDownloadedInThisRun": False,
            "futureDataExpansionRecommended": "Add independent Binance/Bybit public history in a separate version before exchange Dry-run review.",
        },
        "strategyEvolution": {
            "sampleSchema": build_strategy_evolution_schema(),
            "actualTradingSamplesFabricated": False,
            "futureUse": (
                "Local paper outcomes and manually reviewed trade outcomes can be appended as research samples, "
                "then retrained offline. They must not trigger automatic orders."
            ),
        },
        "timeframes": timeframe_reports,
        "adaptiveSummary": {
            "totalCandidates": len(ranked),
            "localPaperWatchApprovedCount": len(approved),
            "topCandidateIds": [row["poolId"] for row in ranked[:10]],
        },
        "topAdaptiveCandidates": ranked[:20],
        "approvedLocalPaperWatchCandidates": approved[:10],
        "decision": {
            "adaptiveMLComputed": True,
            "targetRMultipleUnchanged": True,
            "localPaperWatchApproved": bool(approved),
            "localPaperWatchPoolId": approved[0]["poolId"] if approved else None,
            "newFormalPaperCandidateApproved": False,
            "exchangeDryRunApproved": False,
            "liveTradingApproved": False,
            "reason": "adaptive_ml_local_paper_watch_only" if approved else "adaptive_ml_no_watch_candidate_passed",
        },
        "recommendations": _recommendations(approved, ranked),
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
    summary = report["adaptiveSummary"]
    lines = [
        "# V13.5.8 Adaptive ML Factor Discovery Report",
        "",
        "This report adds an auditable adaptive ML layer. It learns train-only factor threshold rules and validates them on later folds.",
        "",
        "## Decision",
        "",
        f"- Adaptive ML computed: `{decision['adaptiveMLComputed']}`",
        f"- Target R multiple unchanged: `{decision['targetRMultipleUnchanged']}`",
        f"- Local paper watch approved: `{decision['localPaperWatchApproved']}`",
        f"- Local paper watch pool: `{decision['localPaperWatchPoolId']}`",
        f"- New formal paper candidate approved: `{decision['newFormalPaperCandidateApproved']}`",
        f"- Exchange Dry-run approved: `{decision['exchangeDryRunApproved']}`",
        f"- Live trading approved: `{decision['liveTradingApproved']}`",
        f"- Reason: `{decision['reason']}`",
        "",
        "## Adaptive Summary",
        "",
        f"- Total candidates: `{summary['totalCandidates']}`",
        f"- Local paper watch approved count: `{summary['localPaperWatchApprovedCount']}`",
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
            f"adaptiveCandidates=`{item.get('adaptiveCandidateCount')}`"
        )
    lines.extend(["", "## Top Adaptive Candidates", ""])
    for row in report.get("topAdaptiveCandidates", [])[:10]:
        metrics = row.get("selectedMetrics") or {}
        baseline = row.get("baselineTestMetrics") or {}
        decision_row = row.get("decision") or {}
        stability = row.get("foldStability") or {}
        cost = row.get("costAdjusted2R") or {}
        lines.append(
            f"- `{row.get('poolId')}`: selectedTrades=`{metrics.get('tradeCount')}`, "
            f"winRate=`{metrics.get('winRatePct')}`, RR=`{metrics.get('rewardRiskRatio')}`, "
            f"PF=`{metrics.get('profitFactor')}`, maxDD=`{metrics.get('maxDrawdownPct')}`, "
            f"baselinePF=`{baseline.get('profitFactor')}`, folds=`{stability.get('foldsWithTrades')}`, "
            f"2Rclose=`{cost.get('observedToCostAdjusted2RCloseness')}`, "
            f"watch=`{decision_row.get('localPaperWatchApproved')}`, "
            f"fail=`{', '.join(decision_row.get('failReasons') or []) or 'none'}`"
        )
    lines.extend(["", "## Strategy Evolution", ""])
    lines.append("- Future local paper and manual-review outcomes can be stored with `strategy_evolution_sample_v1`.")
    lines.append("- Historical labels are not fabricated actual trades.")
    lines.append("- Retraining must remain offline and cannot create orders.")
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
    parser = argparse.ArgumentParser(description="Generate V13.5.8 adaptive ML factor report.")
    parser.add_argument("--timeframes", default="1h,4h")
    parser.add_argument("--pairs", default=None)
    parser.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR))
    parser.add_argument("--output-report", default=str(DEFAULT_OUTPUT_REPORT))
    parser.add_argument("--output-summary", default=str(DEFAULT_OUTPUT_SUMMARY))
    parser.add_argument("--output-candidates", default=str(DEFAULT_OUTPUT_CANDIDATES))
    parser.add_argument("--output-evolution-schema", default=str(DEFAULT_OUTPUT_EVOLUTION_SCHEMA))
    args = parser.parse_args()

    report = run_adaptive_ml_factor_report(
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
                "approvedLocalPaperWatchCandidates": report["approvedLocalPaperWatchCandidates"],
                "topAdaptiveCandidates": report["topAdaptiveCandidates"][:10],
            }
        ),
    )
    write_json(Path(args.output_evolution_schema), _json_ready(report["strategyEvolution"]["sampleSchema"]))
    print(f"Wrote {args.output_report}")
    print(f"Wrote {args.output_summary}")
    print(f"Wrote {args.output_candidates}")
    print(f"Wrote {args.output_evolution_schema}")
    print(f"decision={report.get('decision')}")
    print(f"adaptiveSummary={report.get('adaptiveSummary')}")


if __name__ == "__main__":
    main()
