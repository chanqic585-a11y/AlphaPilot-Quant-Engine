"""Generate V13.5 derivative ML-gated strategy research report.

This command builds local features, labels candidate events with a 2R/1R
triple barrier, applies a walk-forward probability gate, and reports whether
any candidate clears the hard research-to-paper threshold.

It uses local public data only. It does not run Dry-run, use API keys, call
Trade API or Withdraw API, read accounts, create orders, or auto trade.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import UTC, datetime
from itertools import combinations
from pathlib import Path
from typing import Any

import pandas as pd

from alphapilot.derivatives.feature_panel import build_derivatives_feature_panel
from alphapilot.ml_gate.probability_gate import (
    add_probability_buckets,
    ProbabilityGateConfig,
    apply_walk_forward_probability_gate,
    evaluate_trades,
)
from alphapilot.ml_gate.triple_barrier import BarrierConfig, build_labeled_events


REPORT_ID = "v13_5_derivatives_ml_strategy_report"
VERSION = "V13.5"
DEFAULT_OUTPUT_REPORT = Path("reports/v13_5_derivatives_ml_strategy_report.json")
DEFAULT_OUTPUT_SUMMARY = Path("reports/v13_5_derivatives_ml_strategy_summary.md")
DEFAULT_OUTPUT_SIGNALS = Path("reports/v13_5_derivatives_ml_shadow_signals_sample.json")

MINING_BUCKET_COLUMNS = [
    "bucket_setupName",
    "bucket_pair",
    "bucket_btc_regime",
    "bucket_rsi14",
    "bucket_return_3",
    "bucket_volume_ratio",
    "bucket_bollinger_z",
    "bucket_funding_z_60",
    "bucket_mark_basis_pct",
    "bucket_btc_return_3",
    "bucket_relative_return_6",
    "bucket_atr_pct",
]


DEFAULT_PAIRS = [
    "BTC/USDT:USDT",
    "ETH/USDT:USDT",
    "SOL/USDT:USDT",
    "DOGE/USDT:USDT",
    "XRP/USDT:USDT",
    "ADA/USDT:USDT",
    "AVAX/USDT:USDT",
    "LINK/USDT:USDT",
    "SUI/USDT:USDT",
    "APT/USDT:USDT",
]


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")


def parse_pairs(value: str | None) -> list[str]:
    if not value:
        return DEFAULT_PAIRS
    return [item.strip() for item in value.split(",") if item.strip()]


def _json_ready(value: Any) -> Any:
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            return str(value)
    return value


def _summarize_by(events: pd.DataFrame, column: str) -> list[dict[str, Any]]:
    rows = []
    if events.empty or column not in events.columns:
        return rows
    for value, group in events.groupby(column):
        metrics = evaluate_trades(group)
        rows.append({"value": str(value), **metrics})
    return sorted(rows, key=lambda row: (row.get("profitFactor") or 0, row.get("totalReturnPct") or -999), reverse=True)


def _latest_signal_sample(trades: pd.DataFrame, limit: int = 30) -> list[dict[str, Any]]:
    if trades.empty:
        return []
    columns = [
        "pair",
        "setupName",
        "direction",
        "signalDate",
        "entryDate",
        "exitDate",
        "entryPrice",
        "exitPrice",
        "exitReason",
        "netReturnPct",
        "rMultiple",
        "probabilityScore",
        "probabilityComponents",
        "btc_regime",
        "funding_rate",
        "funding_z_60",
        "mark_basis_pct",
    ]
    available = [column for column in columns if column in trades.columns]
    sample = trades.sort_values("signalDate", ascending=False).head(limit)[available]
    return [_json_ready(row) for row in sample.to_dict(orient="records")]


def _run_one_config(
    events: pd.DataFrame,
    barrier_config: BarrierConfig,
    gate_config: ProbabilityGateConfig,
    folds: int,
) -> dict[str, Any]:
    gated = apply_walk_forward_probability_gate(events, gate_config, folds=folds)
    passed = gated[gated["probabilityGatePassed"] == True].copy() if not gated.empty else gated
    raw_metrics = evaluate_trades(events)
    gated_metrics = evaluate_trades(passed)
    return {
        "barrierConfig": asdict(barrier_config),
        "gateConfig": asdict(gate_config),
        "candidateEventCount": int(len(events)),
        "gatedTradeCount": int(len(passed)),
        "rawMetrics": raw_metrics,
        "gatedMetrics": gated_metrics,
        "bySetup": _summarize_by(passed, "setupName"),
        "byPair": _summarize_by(passed, "pair"),
        "gatedEvents": passed,
    }


def _period_metrics(events: pd.DataFrame) -> dict[str, Any]:
    periods = {
        "before2025": events[events["signalDate"] < pd.Timestamp("2025-01-01", tz="UTC")],
        "year2025": events[
            (events["signalDate"] >= pd.Timestamp("2025-01-01", tz="UTC"))
            & (events["signalDate"] < pd.Timestamp("2026-01-01", tz="UTC"))
        ],
        "year2026": events[events["signalDate"] >= pd.Timestamp("2026-01-01", tz="UTC")],
    }
    return {name: evaluate_trades(frame) for name, frame in periods.items()}


def _candidate_hard_gate(metrics: dict[str, Any], recent_metrics: dict[str, Any]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if (metrics.get("tradeCount") or 0) < 100:
        reasons.append("trade_count_below_100")
    if (metrics.get("winRatePct") or 0) < 55:
        reasons.append("win_rate_below_55")
    if (metrics.get("rewardRiskRatio") or 0) < 1.8:
        reasons.append("reward_risk_below_1_8")
    if (metrics.get("profitFactor") or 0) < 1.35:
        reasons.append("profit_factor_below_1_35")
    if (metrics.get("maxDrawdownPct") or 999) > 20:
        reasons.append("max_drawdown_above_20")
    if (metrics.get("totalReturnPct") or 0) <= 0:
        reasons.append("total_return_not_positive")
    if (recent_metrics.get("tradeCount") or 0) >= 10:
        if (recent_metrics.get("winRatePct") or 0) < 50:
            reasons.append("recent_2026_win_rate_below_50")
        if (recent_metrics.get("profitFactor") or 0) < 1:
            reasons.append("recent_2026_profit_factor_below_1")
    else:
        reasons.append("recent_2026_sample_below_10")
    return len(reasons) == 0, reasons


def _mine_deterministic_candidates(events: pd.DataFrame, limit: int = 20) -> list[dict[str, Any]]:
    if events.empty:
        return []
    prepared = add_probability_buckets(events)
    mined: list[dict[str, Any]] = []
    for size in [1, 2, 3]:
        for columns in combinations(MINING_BUCKET_COLUMNS, size):
            for key, group in prepared.groupby(list(columns), dropna=False):
                if len(group) < 80:
                    continue
                metrics = evaluate_trades(group)
                if (metrics.get("profitFactor") or 0) < 1.2:
                    continue
                period_metrics = _period_metrics(group)
                passed, fail_reasons = _candidate_hard_gate(metrics, period_metrics["year2026"])
                mined.append(
                    {
                        "columns": list(columns),
                        "values": [str(item) for item in (key if isinstance(key, tuple) else (key,))],
                        "metrics": metrics,
                        "periodMetrics": period_metrics,
                        "hardGatePassed": passed,
                        "hardGateFailReasons": fail_reasons,
                    }
                )
    mined = sorted(
        mined,
        key=lambda row: (
            1 if row["hardGatePassed"] else 0,
            row["metrics"].get("profitFactor") or 0,
            row["metrics"].get("winRatePct") or 0,
            row["metrics"].get("rewardRiskRatio") or 0,
            row["metrics"].get("tradeCount") or 0,
        ),
        reverse=True,
    )
    return mined[:limit]


def _barrier_configs_for_timeframe(timeframe: str) -> list[BarrierConfig]:
    if timeframe == "1h":
        return [
            BarrierConfig(stop_loss_pct=0.018, reward_r_multiple=2.0, horizon_bars=12),
            BarrierConfig(stop_loss_pct=0.02, reward_r_multiple=2.0, horizon_bars=12),
            BarrierConfig(stop_loss_pct=0.025, reward_r_multiple=2.0, horizon_bars=18),
            BarrierConfig(stop_loss_pct=0.03, reward_r_multiple=2.0, horizon_bars=18),
            BarrierConfig(stop_loss_pct=0.035, reward_r_multiple=2.0, horizon_bars=24),
            BarrierConfig(stop_loss_pct=0.04, reward_r_multiple=2.0, horizon_bars=24),
            BarrierConfig(stop_loss_pct=0.045, reward_r_multiple=2.0, horizon_bars=30),
            BarrierConfig(stop_loss_pct=0.05, reward_r_multiple=2.0, horizon_bars=36),
        ]
    return [
        BarrierConfig(stop_loss_pct=0.035, reward_r_multiple=2.0, horizon_bars=24),
        BarrierConfig(stop_loss_pct=0.04, reward_r_multiple=2.0, horizon_bars=24),
        BarrierConfig(stop_loss_pct=0.045, reward_r_multiple=2.0, horizon_bars=18),
        BarrierConfig(stop_loss_pct=0.045, reward_r_multiple=2.0, horizon_bars=24),
        BarrierConfig(stop_loss_pct=0.045, reward_r_multiple=2.0, horizon_bars=30),
        BarrierConfig(stop_loss_pct=0.05, reward_r_multiple=2.0, horizon_bars=18),
        BarrierConfig(stop_loss_pct=0.05, reward_r_multiple=2.0, horizon_bars=24),
        BarrierConfig(stop_loss_pct=0.05, reward_r_multiple=2.0, horizon_bars=30),
        BarrierConfig(stop_loss_pct=0.05, reward_r_multiple=2.0, horizon_bars=36),
        BarrierConfig(stop_loss_pct=0.055, reward_r_multiple=2.0, horizon_bars=18),
        BarrierConfig(stop_loss_pct=0.055, reward_r_multiple=2.0, horizon_bars=24),
        BarrierConfig(stop_loss_pct=0.06, reward_r_multiple=2.0, horizon_bars=18),
    ]


def run_research(
    pairs: list[str],
    timeframe: str,
    folds: int,
    max_configs: int | None = None,
) -> dict[str, Any]:
    panel_result = build_derivatives_feature_panel(pairs=pairs, timeframe=timeframe)
    panel = panel_result.rows
    barrier_configs = _barrier_configs_for_timeframe(timeframe)
    configs: list[tuple[BarrierConfig, ProbabilityGateConfig]] = []
    for barrier_config in barrier_configs:
        for probability_threshold in [0.40, 0.45, 0.50, 0.54, 0.57]:
                configs.append(
                    (
                        barrier_config,
                        ProbabilityGateConfig(
                            train_min_events=80,
                            min_bucket_events=8,
                            probability_threshold=probability_threshold,
                            min_score_components=4,
                        ),
                    )
                )
    if max_configs:
        configs = configs[:max_configs]

    results = []
    best_passed_events = pd.DataFrame()
    mined_candidates: list[dict[str, Any]] = []
    events_cache: dict[tuple[float, int], pd.DataFrame] = {}
    for index, (barrier_config, gate_config) in enumerate(configs, start=1):
        cache_key = (barrier_config.stop_loss_pct, barrier_config.horizon_bars)
        if cache_key not in events_cache:
            events_cache[cache_key] = build_labeled_events(panel, barrier_config)
            for candidate in _mine_deterministic_candidates(events_cache[cache_key], limit=5):
                candidate["barrierConfig"] = asdict(barrier_config)
                mined_candidates.append(candidate)
        events = events_cache[cache_key]
        result = _run_one_config(events, barrier_config, gate_config, folds=folds)
        result["configRankInputOrder"] = index
        gated_events = result.pop("gatedEvents")
        results.append(result)
        if result["gatedMetrics"]["researchWorthContinuing"]:
            if best_passed_events.empty or result["gatedMetrics"]["profitFactor"] > evaluate_trades(best_passed_events).get("profitFactor", 0):
                best_passed_events = gated_events.copy()

    ranked = sorted(
        results,
        key=lambda row: (
            1 if row["gatedMetrics"]["researchWorthContinuing"] else 0,
            row["gatedMetrics"].get("profitFactor") or 0,
            row["gatedMetrics"].get("winRatePct") or 0,
            row["gatedMetrics"].get("totalReturnPct") or -999,
        ),
        reverse=True,
    )
    best = ranked[0] if ranked else None
    passing = [row for row in ranked if row["gatedMetrics"]["researchWorthContinuing"]]
    mined_candidates = sorted(
        mined_candidates,
        key=lambda row: (
            1 if row["hardGatePassed"] else 0,
            row["metrics"].get("profitFactor") or 0,
            row["metrics"].get("winRatePct") or 0,
            row["metrics"].get("rewardRiskRatio") or 0,
            row["metrics"].get("tradeCount") or 0,
        ),
        reverse=True,
    )[:20]
    mined_passing = [row for row in mined_candidates if row["hardGatePassed"]]
    signal_sample = _latest_signal_sample(best_passed_events if not best_passed_events.empty else pd.DataFrame())

    return {
        "reportId": REPORT_ID,
        "version": VERSION,
        "status": "completed",
        "isMock": False,
        "generatedAt": utc_now(),
        "pairs": pairs,
        "timeframe": timeframe,
        "objective": {
            "targetWinRatePct": 55,
            "targetRewardRiskRatio": 2.0,
            "hardGate": "A candidate must pass walk-forward, friction-adjusted metrics before paper testing.",
        },
        "dataSummary": {
            "panelRows": int(len(panel)),
            "loadedPairs": panel_result.loaded_pairs,
            "missingPairs": panel_result.missing_pairs,
            "missingOptionalSources": panel_result.missing_optional_sources,
            "openInterestStatus": "unavailable_not_fabricated",
            "fundingRateCoverageNote": "Funding files are used when local public data exists; missing values are not fabricated.",
        },
        "searchSummary": {
            "configCount": len(configs),
            "passingConfigCount": len(passing),
            "folds": folds,
        },
        "hardGateCriteria": {
            "minTradeCount": 100,
            "minWinRatePct": 55,
            "minRewardRiskRatio": 1.8,
            "targetRewardRiskRatio": 2.0,
            "minProfitFactor": 1.35,
            "maxDrawdownPct": 20,
            "mustBePositiveAfterFeesAndSlippage": True,
        },
        "bestCandidate": best,
        "passingCandidates": passing[:10],
        "topCandidates": ranked[:20],
        "bestDeterministicMinedCandidate": mined_candidates[0] if mined_candidates else None,
        "deterministicMinedCandidates": mined_candidates,
        "deterministicMinedPassingCount": len(mined_passing),
        "shadowSignalSamplePath": str(DEFAULT_OUTPUT_SIGNALS) if signal_sample else None,
        "shadowOrPaperDecision": {
            "shadowApproved": bool(passing or mined_passing),
            "paperApproved": bool(passing or mined_passing),
            "dryRunApproved": False,
            "liveTradingApproved": False,
            "reason": "paper_candidate_found" if (passing or mined_passing) else "no_candidate_passed_55pct_winrate_2r_hard_gate",
        },
        "recommendations": _recommendations(passing, best, mined_candidates),
        "safetyBoundary": {
            "usesPublicLocalDataOnly": True,
            "usesApiKey": False,
            "tradeApiUsed": False,
            "withdrawApiUsed": False,
            "readsRealAccount": False,
            "readsRealPositions": False,
            "createsOrders": False,
            "autoTrading": False,
            "dryRunApproved": False,
            "liveTradingApproved": False,
        },
        "_shadowSignalSample": signal_sample,
    }


def _recommendations(
    passing: list[dict[str, Any]],
    best: dict[str, Any] | None,
    mined_candidates: list[dict[str, Any]] | None = None,
) -> list[str]:
    if passing:
        return [
            "A candidate cleared the research-to-paper hard gate; start shadow signal logging before any exchange dry-run.",
            "Do not enter live trading. Keep Trade API and Withdraw API disabled.",
            "Use the generated shadow signal sample schema for paper monitoring.",
        ]
    if not best:
        return ["No candidate events were produced; expand data coverage and candidate definitions."]
    metrics = best.get("gatedMetrics", {})
    mined = (mined_candidates or [None])[0]
    mined_note = ""
    if mined:
        mined_metrics = mined.get("metrics", {})
        mined_note = (
            " Best deterministic mined candidate: "
            f"trades={mined_metrics.get('tradeCount')}, "
            f"winRate={mined_metrics.get('winRatePct')}, "
            f"rewardRisk={mined_metrics.get('rewardRiskRatio')}, "
            f"profitFactor={mined_metrics.get('profitFactor')}, "
            f"failReasons={mined.get('hardGateFailReasons')}."
        )
    return [
        "No V13.5 candidate cleared the 55% win-rate and 2R hard gate.",
        "Do not start paper or Dry-run from this result.",
        "Prioritize richer derivatives data: open interest, liquidation proxies, order-book/liquidity spread, and longer funding history.",
        f"Best observed gated metrics: trades={metrics.get('tradeCount')}, winRate={metrics.get('winRatePct')}, rewardRisk={metrics.get('rewardRiskRatio')}, profitFactor={metrics.get('profitFactor')}.{mined_note}",
    ]


def write_summary(report: dict[str, Any], path: Path) -> None:
    best = report.get("bestCandidate") or {}
    metrics = best.get("gatedMetrics", {})
    lines = [
        "# V13.5 Derivatives ML-Gated Strategy Report",
        "",
        "This report is research-only. It does not approve live trading, does not use API keys, and does not create orders.",
        "",
        "## Decision",
        "",
        f"- Shadow approved: `{report['shadowOrPaperDecision']['shadowApproved']}`",
        f"- Paper approved: `{report['shadowOrPaperDecision']['paperApproved']}`",
        f"- Dry-run approved: `{report['shadowOrPaperDecision']['dryRunApproved']}`",
        f"- Live trading approved: `{report['shadowOrPaperDecision']['liveTradingApproved']}`",
        f"- Reason: `{report['shadowOrPaperDecision']['reason']}`",
        "",
        "## Best Candidate",
        "",
        f"- Trade count: `{metrics.get('tradeCount')}`",
        f"- Win rate: `{metrics.get('winRatePct')}`",
        f"- Reward/risk: `{metrics.get('rewardRiskRatio')}`",
        f"- Profit factor: `{metrics.get('profitFactor')}`",
        f"- Total return: `{metrics.get('totalReturnPct')}`",
        f"- Max drawdown: `{metrics.get('maxDrawdownPct')}`",
        f"- Research worth continuing: `{metrics.get('researchWorthContinuing')}`",
        "",
        "## Best Deterministic Mined Candidate",
        "",
    ]
    mined = report.get("bestDeterministicMinedCandidate") or {}
    mined_metrics = mined.get("metrics", {})
    lines.extend(
        [
            f"- Columns: `{', '.join(mined.get('columns', [])) if mined else 'none'}`",
            f"- Values: `{', '.join(mined.get('values', [])) if mined else 'none'}`",
            f"- Trade count: `{mined_metrics.get('tradeCount')}`",
            f"- Win rate: `{mined_metrics.get('winRatePct')}`",
            f"- Reward/risk: `{mined_metrics.get('rewardRiskRatio')}`",
            f"- Profit factor: `{mined_metrics.get('profitFactor')}`",
            f"- Max drawdown: `{mined_metrics.get('maxDrawdownPct')}`",
            f"- Hard gate passed: `{mined.get('hardGatePassed') if mined else False}`",
            f"- Fail reasons: `{', '.join(mined.get('hardGateFailReasons', [])) if mined else 'none'}`",
            "",
        ]
    )
    lines.extend(
        [
        "## Data",
        "",
        f"- Panel rows: `{report['dataSummary']['panelRows']}`",
        f"- Loaded pairs: `{', '.join(report['dataSummary']['loadedPairs'])}`",
        f"- Missing pairs: `{', '.join(report['dataSummary']['missingPairs']) or 'none'}`",
        f"- Open interest status: `{report['dataSummary']['openInterestStatus']}`",
        "",
        "## Recommendations",
        "",
        *[f"- {item}" for item in report.get("recommendations", [])],
        "",
        ]
    )
    write_text(path, "\n".join(lines))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pairs", default=None)
    parser.add_argument("--timeframe", default="4h", choices=["1h", "4h"])
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--max-configs", type=int, default=None)
    parser.add_argument("--output-report", default=str(DEFAULT_OUTPUT_REPORT))
    parser.add_argument("--output-summary", default=str(DEFAULT_OUTPUT_SUMMARY))
    parser.add_argument("--output-signals", default=str(DEFAULT_OUTPUT_SIGNALS))
    args = parser.parse_args()

    pairs = parse_pairs(args.pairs)
    report = run_research(pairs=pairs, timeframe=args.timeframe, folds=args.folds, max_configs=args.max_configs)
    signal_sample = report.pop("_shadowSignalSample")
    output_report = Path(args.output_report)
    output_summary = Path(args.output_summary)
    output_signals = Path(args.output_signals)
    if signal_sample:
        write_json(output_signals, signal_sample)
        report["shadowSignalSamplePath"] = str(output_signals)
    write_json(output_report, _json_ready(report))
    write_summary(report, output_summary)
    print(f"Wrote {output_report}")
    print(f"Wrote {output_summary}")
    if signal_sample:
        print(f"Wrote {output_signals}")
    decision = report["shadowOrPaperDecision"]
    print(f"shadowApproved={decision['shadowApproved']}")
    print(f"paperApproved={decision['paperApproved']}")
    best = report.get("bestCandidate") or {}
    print(f"bestGatedMetrics={best.get('gatedMetrics')}")


if __name__ == "__main__":
    main()
