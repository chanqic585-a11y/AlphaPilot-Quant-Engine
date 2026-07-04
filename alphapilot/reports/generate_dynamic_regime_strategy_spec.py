"""Generate V13.4.12 Dynamic Regime strategy specification artifacts.

This generator writes specification artifacts only. It does not write strategy
code, download data, run backtests, enter Dry-run, call exchange APIs, read
accounts, create orders, or auto trade.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from alphapilot.reports.dynamic_regime_strategy_schema import DynamicRegimeStrategySpecReport

DEFAULT_EXECUTION_REALITY_REPORT = Path("reports/v13_4_11_execution_reality_design_report.json")
DEFAULT_OUTPUT_JSON = Path("reports/v13_4_12_dynamic_regime_strategy_spec.json")
DEFAULT_OUTPUT_SUMMARY = Path("reports/v13_4_12_dynamic_regime_strategy_summary.md")

REPORT_ID = "v13_4_12_dynamic_regime_strategy_spec"
REPORT_VERSION = "V13.4.12"
STRATEGY_NAME = "AlphaPilot Dynamic Regime Strategy V0.1"
STRATEGY_NAME_CN = "AlphaPilot 动态市场状态策略 V0.1"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path, warnings: list[str]) -> dict[str, Any]:
    if not path.exists():
        warnings.append(f"Missing input report: {path}")
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        warnings.append(f"Unable to parse input report {path}: {exc}")
        return {}


def _source_documents(execution_reality_path: Path, execution_reality: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "key": "v13_4_11_execution_reality",
            "path": str(execution_reality_path),
            "exists": execution_reality_path.exists(),
            "dryRunApproved": execution_reality.get("dryRunApproved", "unavailable"),
            "liveTradingApproved": execution_reality.get("liveTradingApproved", "unavailable"),
        },
        {
            "key": "new_strategy_mainline",
            "path": "AlphaPilot_New_Strategy_Mainline_Dynamic_Regime.md",
            "exists": True,
            "role": "user-approved mainline direction document",
        },
    ]


def build_report(execution_reality_path: Path) -> DynamicRegimeStrategySpecReport:
    warnings: list[str] = []
    execution_reality = _read_json(execution_reality_path, warnings)
    if execution_reality.get("dryRunApproved") is not False:
        warnings.append("V13.4.11 execution reality report does not confirm dryRunApproved=false.")
    if execution_reality.get("liveTradingApproved") is not False:
        warnings.append("V13.4.11 execution reality report does not confirm liveTradingApproved=false.")

    return DynamicRegimeStrategySpecReport(
        reportId=REPORT_ID,
        version=REPORT_VERSION,
        strategyName=STRATEGY_NAME,
        strategyNameCn=STRATEGY_NAME_CN,
        purpose="Specify the new Dynamic Universe + Regime Router + Probability Score strategy mainline.",
        currentStatus="specification_only",
        sourceDocuments=_source_documents(execution_reality_path, execution_reality),
        architectureFlow=[
            "public_exchange_data",
            "dynamic_universe_builder",
            "historical_universe_snapshots",
            "market_regime_router",
            "trend_or_mean_reversion_module",
            "probability_score",
            "liquidity_gate",
            "risk_gate",
            "backtest_research",
        ],
        dynamicUniverse={
            "moduleId": "DynamicUniverseV01",
            "selectionSize": {"recommended": 10, "maximum": 15},
            "refreshCadenceCandidates": ["daily", "3d"],
            "baseFilters": [
                "okx_usdt_swap",
                "non_stablecoin",
                "not_delisting",
                "minimum_90d_history",
                "low_missing_candle_rate",
                "minimum_24h_quote_volume",
                "minimum_3d_average_quote_volume",
                "maximum_bid_ask_spread",
                "not_in_risk_blacklist",
            ],
            "rankFactors": [
                "quoteVolume24hRank",
                "quoteVolume3dRank",
                "absReturn24hRank",
                "absReturn3dRank",
                "volatility3dRank",
                "volumeExpansionRank",
                "liquidityStabilityRank",
            ],
            "biasControl": "backtests must use historical snapshots generated with data available at that time",
        },
        historicalUniverseSnapshots={
            "moduleId": "HistoricalDynamicUniverseSnapshotsV01",
            "snapshotKeys": [
                "snapshotDate",
                "lookbackWindow",
                "selectedPairs",
                "rankFactors",
                "excludedPairs",
                "warnings",
            ],
            "antiBiasRule": "never use today's hot coin list to backtest the past",
            "outputs": [
                "daily_universe_snapshots",
                "three_day_universe_snapshots",
            ],
        },
        regimeRouter={
            "moduleId": "MarketRegimeRouterV01",
            "regimes": ["trend", "mean_reversion", "avoid"],
            "futureRegimes": ["breakout"],
            "trendDraftRules": [
                "4h_close_above_ema200",
                "4h_ema20_above_ema50",
                "1h_close_above_ema50",
                "btc_1h_and_4h_not_weak",
                "trend_strength_threshold_met",
            ],
            "meanReversionDraftRules": [
                "4h_not_strong_bear",
                "price_deviated_from_ema20_or_bollinger_mid",
                "short_term_rsi_low",
                "volatility_moderate",
                "btc_not_crashing",
            ],
            "avoidRules": [
                "btc_crash",
                "4h_strong_bear",
                "spread_too_wide",
                "insufficient_liquidity",
                "abnormal_volume",
                "data_missing",
            ],
        },
        trendModule={
            "moduleId": "TrendContinuationModuleV01",
            "entryDraft": [
                "regime_trend",
                "4h_uptrend",
                "1h_pullback_to_ema20_or_ema50_area",
                "1h_reclaim_ema20",
                "macd_histogram_improving",
                "healthy_volume_ratio",
                "no_chase_passed",
                "btc_safe",
                "liquidity_gate_passed",
                "probability_score_passed",
            ],
            "exitDraft": {
                "stoplossPct": [-2.5, -2.0],
                "takeProfitPct": [4.0, 5.0],
                "minimumRewardRisk": 1.5,
                "timeStopBars1h": [8, 12],
                "momentumExit": "profit_state_only",
            },
        },
        meanReversionModule={
            "moduleId": "MeanReversionModuleV01",
            "entryDraft": [
                "regime_mean_reversion",
                "4h_not_strong_bear",
                "btc_not_crashing",
                "price_near_or_below_bollinger_lower",
                "rsi_low_but_recovering",
                "close_reclaims_bollinger_lower",
                "volume_not_drying_up",
                "atr_not_extreme",
                "liquidity_gate_passed",
                "probability_score_passed",
            ],
            "exitDraft": {
                "takeProfit": "bollinger_middle_or_2_5_to_3_pct",
                "stoploss": "structure_break_or_minus_2_pct",
                "timeStop": "shorter_than_trend_module",
            },
        },
        breakoutModule={
            "moduleId": "BreakoutRetestModuleV01",
            "status": "reserved_for_later_version",
            "notImplementedIn": REPORT_VERSION,
        },
        probabilityScore={
            "moduleId": "ProbabilityScoreV01",
            "futureWindows": ["8 candles", "12 candles", "24 candles"],
            "labels": [
                "hit_tp_before_sl",
                "hit_sl_before_tp",
                "mfe",
                "mae",
                "final_return",
                "holding_time",
            ],
            "conditionBuckets": [
                "regime",
                "pair_liquidity_bucket",
                "volume_rank_bucket",
                "volatility_bucket",
                "rsi_bucket",
                "distance_to_ema20_bucket",
                "distance_to_bollinger_bucket",
                "btc_state",
                "time_of_day",
                "day_of_week",
            ],
            "passThresholds": {
                "sampleCount": 50,
                "hitTpBeforeSlProbability": 0.45,
                "profitFactor": 1.2,
                "expectancy": "greater_than_zero",
            },
            "insufficientSampleDecision": "observe_only",
        },
        liquidityGateIntegration={
            "sourceVersion": "V13.4.11",
            "requiredBeforeBacktestTrade": True,
            "requiredBeforeDryRunOrLive": True,
            "missingLiquidityDataDecision": "observe_only_or_rejected",
        },
        riskGateIntegration={
            "requiredChecks": [
                "single_trade_risk",
                "daily_risk",
                "max_drawdown",
                "max_open_positions",
                "same_pair_cooldown",
                "btc_crash",
                "market_regime",
                "liquidity_gate",
                "probability_score",
                "signal_age",
            ],
            "decisions": ["approved", "rejected", "observe_only", "needs_human_confirmation"],
        },
        backtestPlan={
            "stage": "plan_only",
            "firstSmokeUniverse": ["BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT", "active_top5"],
            "expandedValidation": [
                "dynamic_top10_daily",
                "dynamic_top10_3d",
                "dynamic_top15_daily",
                "static_top30_baseline_comparison",
            ],
            "mustCompare": [
                "dynamic_universe_vs_static_top30",
                "trend_module_vs_mean_reversion_module",
                "raw_vs_slippage_adjusted",
                "with_liquidity_gate_vs_without_liquidity_gate",
            ],
        },
        roadmap=[
            {"version": "V13.4.13", "goal": "Historical Dynamic Universe Builder"},
            {"version": "V13.4.14", "goal": "Probability Score Dataset and Label Builder"},
            {"version": "V13.4.15", "goal": "Dynamic Regime Strategy V0.1 Implementation"},
            {"version": "V13.4.16", "goal": "Dynamic Regime Strategy Smoke Backtest"},
            {"version": "V13.4.17", "goal": "Expanded Validation + Slippage + Liquidity Gate"},
            {"version": "V13.5", "goal": "Shadow Trading Skeleton"},
        ],
        doNotProceed=[
            "do_not_continue_small_parameter_tweaks_on_volume_rebound",
            "do_not_continue_small_parameter_tweaks_on_trend_pullback",
            "do_not_enter_dry_run",
            "do_not_connect_real_api_keys",
            "do_not_auto_trade",
            "do_not_backtest_past_with_today_hot_coin_list",
            "do_not_skip_liquidity_gate",
            "do_not_trade_without_probability_statistics",
        ],
        dryRunApproved=False,
        liveTradingApproved=False,
        nextStepRecommendation="V13.4.13 - Historical Dynamic Universe Builder",
        warnings=warnings,
        generatedAt=_utc_now(),
    )


def _write_summary(report: dict[str, Any], path: Path) -> None:
    lines = [
        "# V13.4.12 Dynamic Regime Strategy Summary",
        "",
        "## Decision",
        "",
        f"- strategyName: {report['strategyName']}",
        f"- currentStatus: {report['currentStatus']}",
        f"- dryRunApproved: {report['dryRunApproved']}",
        f"- liveTradingApproved: {report['liveTradingApproved']}",
        f"- nextStepRecommendation: {report['nextStepRecommendation']}",
        "",
        "## Architecture Flow",
        "",
    ]
    lines.extend(f"- {step}" for step in report["architectureFlow"])
    lines.extend(
        [
            "",
            "## Dynamic Universe",
            "",
            f"- moduleId: {report['dynamicUniverse']['moduleId']}",
            f"- recommended selection size: {report['dynamicUniverse']['selectionSize']['recommended']}",
            f"- maximum selection size: {report['dynamicUniverse']['selectionSize']['maximum']}",
            "- historical snapshots are required to avoid lookahead bias.",
            "",
            "## Regime Router",
            "",
            f"- regimes: {', '.join(report['regimeRouter']['regimes'])}",
            "- breakout is reserved for a later version.",
            "",
            "## Strategy Modules",
            "",
            f"- trend: {report['trendModule']['moduleId']}",
            f"- mean reversion: {report['meanReversionModule']['moduleId']}",
            f"- breakout: {report['breakoutModule']['status']}",
            "",
            "## Probability Score",
            "",
            f"- moduleId: {report['probabilityScore']['moduleId']}",
            f"- minimum sample count: {report['probabilityScore']['passThresholds']['sampleCount']}",
            f"- minimum hit TP before SL probability: {report['probabilityScore']['passThresholds']['hitTpBeforeSlProbability']}",
            f"- minimum profit factor: {report['probabilityScore']['passThresholds']['profitFactor']}",
            "- insufficient samples return observe_only.",
            "",
            "## Liquidity and Risk Gates",
            "",
            "- V13.4.11 Liquidity Gate is required before future Dry-run or live review.",
            "- Risk Gate remains the final veto layer.",
            "",
            "## Safety",
            "",
            "V13.4.12 is a specification-only version. No strategy code, data download, backtest, Dry-run, real API key, Trade API, Withdraw API, account read, position read, order creation, or auto trading was added.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def export_report(execution_reality_path: Path, output_json: Path, output_summary: Path) -> tuple[Path, Path]:
    report = build_report(execution_reality_path).to_dict()
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_summary(report, output_summary)
    return output_json, output_summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate V13.4.12 Dynamic Regime strategy spec report.")
    parser.add_argument("--execution-reality-report", type=Path, default=DEFAULT_EXECUTION_REALITY_REPORT)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-summary", type=Path, default=DEFAULT_OUTPUT_SUMMARY)
    args = parser.parse_args()

    output_json, output_summary = export_report(args.execution_reality_report, args.output_json, args.output_summary)
    print(f"Exported dynamic regime strategy spec report: {output_json}")
    print(f"Exported dynamic regime strategy summary: {output_summary}")


if __name__ == "__main__":
    main()

