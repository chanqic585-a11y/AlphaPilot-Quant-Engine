"""Generate V13.5.1 expanded-universe relaxed research report.

This command expands the V13.5 derivatives research pipeline to all locally
available futures pairs and adds a relaxed shadow-watchlist gate. It is still
research-only: no Dry-run approval, no live trading, no API keys, no account
reads, no positions, and no orders.
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

from alphapilot.derivatives.feature_panel import DEFAULT_DATA_DIR, build_derivatives_feature_panel
from alphapilot.ml_gate.probability_gate import (
    ProbabilityGateConfig,
    add_probability_buckets,
    apply_walk_forward_probability_gate,
    evaluate_trades,
)
from alphapilot.ml_gate.research_gates import (
    HARD_RESEARCH_GATE,
    OBSERVATION_GATE,
    RELAXED_SHADOW_WATCHLIST_GATE,
    ResearchGateCriteria,
    evaluate_research_gate,
)
from alphapilot.ml_gate.triple_barrier import BarrierConfig, build_labeled_events
from alphapilot.reports.generate_v13_5_derivatives_ml_strategy_report import (
    MINING_BUCKET_COLUMNS,
    _json_ready,
    _latest_signal_sample,
    _period_metrics,
    _summarize_by,
    parse_pairs,
    write_json,
    write_text,
)


REPORT_ID = "v13_5_1_expanded_relaxed_derivatives_research_report"
VERSION = "V13.5.1"
DEFAULT_OUTPUT_REPORT = Path("reports/v13_5_1_expanded_relaxed_research_report.json")
DEFAULT_OUTPUT_SUMMARY = Path("reports/v13_5_1_expanded_relaxed_research_summary.md")
DEFAULT_OUTPUT_SIGNALS = Path("reports/v13_5_1_relaxed_shadow_watchlist_sample.json")


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def discover_local_pairs(timeframe: str, data_dir: Path = DEFAULT_DATA_DIR) -> list[str]:
    pairs: list[str] = []
    suffix = f"-{timeframe}-futures.feather"
    for path in sorted(data_dir.glob(f"*{suffix}")):
        symbol = path.name.removesuffix(suffix)
        parts = symbol.split("_")
        if len(parts) >= 3 and parts[-2:] == ["USDT", "USDT"]:
            base = "_".join(parts[:-2])
            pairs.append(f"{base}/USDT:USDT")
    return pairs


def _barrier_configs(timeframe: str) -> list[BarrierConfig]:
    if timeframe == "1h":
        stops = [0.025, 0.03, 0.035, 0.045]
        horizons = [18, 24, 30, 36]
    else:
        stops = [0.04, 0.05, 0.06]
        horizons = [18, 24, 30]
    return [
        BarrierConfig(
            stop_loss_pct=stop,
            reward_r_multiple=2.0,
            horizon_bars=horizon,
            fee_rate_roundtrip=0.001,
            slippage_rate_roundtrip=0.001,
        )
        for stop in stops
        for horizon in horizons
    ]


def _gate_configs() -> list[ProbabilityGateConfig]:
    return [
        ProbabilityGateConfig(train_min_events=60, min_bucket_events=6, probability_threshold=0.35, min_score_components=3),
        ProbabilityGateConfig(train_min_events=60, min_bucket_events=8, probability_threshold=0.38, min_score_components=3),
        ProbabilityGateConfig(train_min_events=80, min_bucket_events=8, probability_threshold=0.40, min_score_components=4),
        ProbabilityGateConfig(train_min_events=80, min_bucket_events=8, probability_threshold=0.43, min_score_components=4),
        ProbabilityGateConfig(train_min_events=100, min_bucket_events=10, probability_threshold=0.45, min_score_components=4),
    ]


def _gate_status(
    metrics: dict[str, Any],
    recent_metrics: dict[str, Any],
) -> dict[str, Any]:
    hard_passed, hard_reasons = evaluate_research_gate(metrics, recent_metrics, HARD_RESEARCH_GATE)
    relaxed_passed, relaxed_reasons = evaluate_research_gate(metrics, recent_metrics, RELAXED_SHADOW_WATCHLIST_GATE)
    observation_passed, observation_reasons = evaluate_research_gate(metrics, recent_metrics, OBSERVATION_GATE)
    return {
        "hardGatePassed": hard_passed,
        "hardGateFailReasons": hard_reasons,
        "relaxedShadowWatchlistPassed": relaxed_passed,
        "relaxedShadowWatchlistFailReasons": relaxed_reasons,
        "observationGatePassed": observation_passed,
        "observationGateFailReasons": observation_reasons,
    }


def _holdout_metrics(events: pd.DataFrame) -> dict[str, Any]:
    if events.empty:
        return evaluate_trades(events)
    ordered = events.sort_values("signalDate").reset_index(drop=True)
    split_index = max(1, int(len(ordered) * 0.70))
    holdout = ordered.iloc[split_index:].copy()
    return evaluate_trades(holdout)


def _classify_config_result(
    events: pd.DataFrame,
    barrier_config: BarrierConfig,
    gate_config: ProbabilityGateConfig,
    folds: int,
    rank: int,
) -> tuple[dict[str, Any], pd.DataFrame]:
    gated = apply_walk_forward_probability_gate(events, gate_config, folds=folds)
    passed = gated[gated["probabilityGatePassed"] == True].copy() if not gated.empty else gated
    raw_metrics = evaluate_trades(events)
    gated_metrics = evaluate_trades(passed)
    recent_metrics = _period_metrics(passed).get("year2026", evaluate_trades(pd.DataFrame()))
    status = _gate_status(gated_metrics, recent_metrics)
    result = {
        "configRankInputOrder": rank,
        "barrierConfig": asdict(barrier_config),
        "gateConfig": asdict(gate_config),
        "candidateEventCount": int(len(events)),
        "gatedTradeCount": int(len(passed)),
        "rawMetrics": raw_metrics,
        "gatedMetrics": gated_metrics,
        "recentMetrics": recent_metrics,
        "bySetup": _summarize_by(passed, "setupName"),
        "byPair": _summarize_by(passed, "pair"),
        **status,
    }
    return result, passed


def _mine_expanded_candidates(events: pd.DataFrame, limit: int = 30) -> list[dict[str, Any]]:
    if events.empty:
        return []
    prepared = add_probability_buckets(events)
    mined: list[dict[str, Any]] = []
    for size in [1, 2, 3]:
        for columns in combinations(MINING_BUCKET_COLUMNS, size):
            for key, group in prepared.groupby(list(columns), dropna=False):
                if len(group) < 50:
                    continue
                metrics = evaluate_trades(group)
                if (metrics.get("profitFactor") or 0) < 1.05:
                    continue
                period_metrics = _period_metrics(group)
                recent = period_metrics.get("year2026", evaluate_trades(pd.DataFrame()))
                full_status = _gate_status(metrics, recent)
                holdout_metrics = _holdout_metrics(group)
                holdout_status = _gate_status(holdout_metrics, holdout_metrics)
                combined_status = {
                    "hardGatePassed": full_status["hardGatePassed"] and holdout_status["hardGatePassed"],
                    "hardGateFailReasons": [
                        *[f"full_{reason}" for reason in full_status["hardGateFailReasons"]],
                        *[f"holdout_{reason}" for reason in holdout_status["hardGateFailReasons"]],
                    ],
                    "relaxedShadowWatchlistPassed": (
                        full_status["relaxedShadowWatchlistPassed"]
                        and holdout_status["relaxedShadowWatchlistPassed"]
                    ),
                    "relaxedShadowWatchlistFailReasons": [
                        *[f"full_{reason}" for reason in full_status["relaxedShadowWatchlistFailReasons"]],
                        *[f"holdout_{reason}" for reason in holdout_status["relaxedShadowWatchlistFailReasons"]],
                    ],
                    "observationGatePassed": (
                        full_status["observationGatePassed"] and holdout_status["observationGatePassed"]
                    ),
                    "observationGateFailReasons": [
                        *[f"full_{reason}" for reason in full_status["observationGateFailReasons"]],
                        *[f"holdout_{reason}" for reason in holdout_status["observationGateFailReasons"]],
                    ],
                }
                if not (
                    combined_status["hardGatePassed"]
                    or combined_status["relaxedShadowWatchlistPassed"]
                    or combined_status["observationGatePassed"]
                    or full_status["relaxedShadowWatchlistPassed"]
                ):
                    continue
                mined.append(
                    {
                        "columns": list(columns),
                        "values": [str(item) for item in (key if isinstance(key, tuple) else (key,))],
                        "metrics": metrics,
                        "holdoutMetrics": holdout_metrics,
                        "periodMetrics": period_metrics,
                        "fullSampleGateStatus": full_status,
                        "holdoutGateStatus": holdout_status,
                        **combined_status,
                    }
                )
    return sorted(
        mined,
        key=lambda row: (
            1 if row["hardGatePassed"] else 0,
            1 if row["relaxedShadowWatchlistPassed"] else 0,
            1 if row["observationGatePassed"] else 0,
            row["metrics"].get("profitFactor") or 0,
            row["metrics"].get("winRatePct") or 0,
            row["metrics"].get("rewardRiskRatio") or 0,
            row["metrics"].get("tradeCount") or 0,
        ),
        reverse=True,
    )[:limit]


def _rank_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        results,
        key=lambda row: (
            1 if row["hardGatePassed"] else 0,
            1 if row["relaxedShadowWatchlistPassed"] else 0,
            1 if row["observationGatePassed"] else 0,
            row["gatedMetrics"].get("profitFactor") or 0,
            row["gatedMetrics"].get("winRatePct") or 0,
            row["gatedMetrics"].get("rewardRiskRatio") or 0,
            row["gatedMetrics"].get("totalReturnPct") or -999,
        ),
        reverse=True,
    )


def _coverage_notes(panel: pd.DataFrame) -> dict[str, Any]:
    rows = []
    for pair, group in panel.groupby("pair"):
        rows.append(
            {
                "pair": pair,
                "rows": int(len(group)),
                "start": group["date"].min().isoformat(),
                "end": group["date"].max().isoformat(),
                "markBasisCoveragePct": round(float(group["mark_basis_pct"].notna().mean() * 100), 4),
                "fundingCoveragePct": round(float(group["funding_rate"].notna().mean() * 100), 4),
            }
        )
    return {
        "pairCoverage": sorted(rows, key=lambda row: row["pair"]),
        "shortHistoryPairs": [row["pair"] for row in rows if row["rows"] < 1500],
    }


def run_expanded_relaxed_research(
    pairs: list[str],
    timeframe: str,
    folds: int,
    max_configs: int | None,
) -> dict[str, Any]:
    panel_result = build_derivatives_feature_panel(pairs=pairs, timeframe=timeframe)
    panel = panel_result.rows.dropna(subset=["close", "rsi14", "volume_ratio", "atr_pct"]).copy()
    if panel.empty:
        return {
            "reportId": REPORT_ID,
            "version": VERSION,
            "status": "blocked_no_panel_rows",
            "isMock": False,
            "generatedAt": utc_now(),
            "pairs": pairs,
            "timeframe": timeframe,
        }

    configs = [(barrier, gate) for barrier in _barrier_configs(timeframe) for gate in _gate_configs()]
    if max_configs:
        configs = configs[:max_configs]

    results: list[dict[str, Any]] = []
    mined_candidates: list[dict[str, Any]] = []
    events_cache: dict[tuple[float, int], pd.DataFrame] = {}
    best_relaxed_events = pd.DataFrame()
    best_relaxed_metrics: dict[str, Any] | None = None

    for index, (barrier_config, gate_config) in enumerate(configs, start=1):
        cache_key = (barrier_config.stop_loss_pct, barrier_config.horizon_bars)
        if cache_key not in events_cache:
            events = build_labeled_events(panel, barrier_config)
            events_cache[cache_key] = events
            for candidate in _mine_expanded_candidates(events):
                candidate["barrierConfig"] = asdict(barrier_config)
                mined_candidates.append(candidate)
        events = events_cache[cache_key]
        result, gated_events = _classify_config_result(events, barrier_config, gate_config, folds, index)
        results.append(result)
        if result["relaxedShadowWatchlistPassed"]:
            current_metrics = result["gatedMetrics"]
            if best_relaxed_metrics is None or (current_metrics.get("profitFactor") or 0) > (
                best_relaxed_metrics.get("profitFactor") or 0
            ):
                best_relaxed_metrics = current_metrics
                best_relaxed_events = gated_events.copy()

    ranked = _rank_results(results)
    hard_candidates = [row for row in ranked if row["hardGatePassed"]]
    relaxed_candidates = [row for row in ranked if row["relaxedShadowWatchlistPassed"]]
    observation_candidates = [row for row in ranked if row["observationGatePassed"]]
    mined_candidates = _rank_results(
        [
            {
                **row,
                "gatedMetrics": row["metrics"],
                "recentMetrics": row["periodMetrics"].get("year2026", {}),
                "candidateEventCount": row["metrics"].get("tradeCount"),
                "gatedTradeCount": row["metrics"].get("tradeCount"),
            }
            for row in mined_candidates
        ]
    )
    mined_hard = [row for row in mined_candidates if row["hardGatePassed"]]
    mined_relaxed = [row for row in mined_candidates if row["relaxedShadowWatchlistPassed"]]
    mined_full_sample_relaxed = [
        row
        for row in mined_candidates
        if row.get("fullSampleGateStatus", {}).get("relaxedShadowWatchlistPassed")
    ]
    mined_observation = [row for row in mined_candidates if row["observationGatePassed"]]

    signal_sample = _latest_signal_sample(best_relaxed_events)
    relaxed_approved = bool(relaxed_candidates or mined_relaxed)
    hard_approved = bool(hard_candidates)
    deterministic_forward_candidate_found = bool(mined_relaxed or mined_hard or mined_full_sample_relaxed)
    coverage = _coverage_notes(panel)

    return {
        "reportId": REPORT_ID,
        "version": VERSION,
        "status": "completed",
        "isMock": False,
        "generatedAt": utc_now(),
        "pairs": pairs,
        "timeframe": timeframe,
        "objective": {
            "mode": "expanded_universe_relaxed_research",
            "hardGate": HARD_RESEARCH_GATE.to_dict(),
            "relaxedShadowWatchlistGate": RELAXED_SHADOW_WATCHLIST_GATE.to_dict(),
            "observationGate": OBSERVATION_GATE.to_dict(),
            "note": "Relaxed gates create research watchlists only. They are not paper, Dry-run, or live-trading approval.",
        },
        "dataSummary": {
            "panelRows": int(len(panel)),
            "loadedPairs": panel_result.loaded_pairs,
            "missingPairs": panel_result.missing_pairs,
            "missingOptionalSources": panel_result.missing_optional_sources,
            "openInterestStatus": "unavailable_not_fabricated",
            "fundingRateCoverageNote": "Funding files are used when local public data exists; missing values are not fabricated.",
            **coverage,
        },
        "searchSummary": {
            "configCount": len(configs),
            "hardPassingConfigCount": len(hard_candidates),
            "relaxedPassingConfigCount": len(relaxed_candidates),
            "observationPassingConfigCount": len(observation_candidates),
            "deterministicHoldoutHardPassingCount": len(mined_hard),
            "deterministicHoldoutRelaxedPassingCount": len(mined_relaxed),
            "deterministicFullSampleRelaxedCount": len(mined_full_sample_relaxed),
            "deterministicObservationPassingCount": len(mined_observation),
            "folds": folds,
        },
        "bestCandidate": ranked[0] if ranked else None,
        "hardPassingCandidates": hard_candidates[:10],
        "relaxedShadowWatchlistCandidates": relaxed_candidates[:20],
        "observationCandidates": observation_candidates[:20],
        "topCandidates": ranked[:30],
        "bestDeterministicMinedCandidate": mined_candidates[0] if mined_candidates else None,
        "deterministicMinedCandidates": mined_candidates[:30],
        "shadowSignalSamplePath": str(DEFAULT_OUTPUT_SIGNALS) if signal_sample else None,
        "decision": {
            "probabilityHardGateApproved": hard_approved,
            "probabilityRelaxedShadowWatchlistApproved": bool(relaxed_candidates),
            "deterministicForwardConfirmationCandidateFound": deterministic_forward_candidate_found,
            "deterministicHoldoutRelaxedCandidateFound": bool(mined_relaxed),
            "paperApproved": hard_approved,
            "dryRunApproved": False,
            "liveTradingApproved": False,
            "reason": (
                "probability_hard_gate_candidate_found"
                if hard_approved
                else "probability_relaxed_shadow_watchlist_candidate_found"
                if relaxed_candidates
                else "deterministic_forward_confirmation_candidate_found"
                if deterministic_forward_candidate_found
                else "no_candidate_passed_relaxed_shadow_watchlist_gate"
            ),
        },
        "recommendations": _recommendations(
            hard_approved,
            bool(relaxed_candidates),
            deterministic_forward_candidate_found,
            ranked,
            mined_candidates,
        ),
        "safetyBoundary": {
            "usesPublicLocalDataOnly": True,
            "usesApiKey": False,
            "tradeApiUsed": False,
            "withdrawApiUsed": False,
            "readsRealAccount": False,
            "readsRealPositions": False,
            "createsOrders": False,
            "autoTrading": False,
            "paperApprovedRequiresHardGate": True,
            "dryRunApproved": False,
            "liveTradingApproved": False,
        },
        "_shadowSignalSample": signal_sample,
    }


def _recommendations(
    hard_approved: bool,
    relaxed_approved: bool,
    deterministic_forward_candidate_found: bool,
    ranked: list[dict[str, Any]],
    mined_candidates: list[dict[str, Any]],
) -> list[str]:
    if hard_approved:
        return [
            "A hard-gate candidate exists. Start shadow logging first; do not enter exchange Dry-run yet.",
            "Paper consideration still requires manual review, longer holdout checks, and slippage stress.",
            "Keep Trade API, Withdraw API, account reads, and order creation disabled.",
        ]
    if relaxed_approved:
        best = ranked[0] if ranked else {}
        metrics = best.get("gatedMetrics", {})
        return [
            "A relaxed shadow-watchlist candidate exists, but hard gate did not pass.",
            "Use it only for offline shadow logging and additional holdout checks.",
            f"Best relaxed metrics: trades={metrics.get('tradeCount')}, winRate={metrics.get('winRatePct')}, rewardRisk={metrics.get('rewardRiskRatio')}, profitFactor={metrics.get('profitFactor')}, maxDrawdown={metrics.get('maxDrawdownPct')}.",
            "Do not start paper, Dry-run, or live trading from relaxed-only approval.",
        ]
    if deterministic_forward_candidate_found:
        mined = mined_candidates[0] if mined_candidates else {}
        mined_metrics = mined.get("metrics", {})
        holdout_metrics = mined.get("holdoutMetrics", {})
        return [
            "A deterministic mined candidate exists, but probability-gated configs did not pass.",
            "Treat this as a forward-confirmation candidate only; it may be data-mined.",
            f"Best mined full-sample metrics: trades={mined_metrics.get('tradeCount')}, winRate={mined_metrics.get('winRatePct')}, rewardRisk={mined_metrics.get('rewardRiskRatio')}, profitFactor={mined_metrics.get('profitFactor')}, maxDrawdown={mined_metrics.get('maxDrawdownPct')}.",
            f"Best mined holdout metrics: trades={holdout_metrics.get('tradeCount')}, winRate={holdout_metrics.get('winRatePct')}, rewardRisk={holdout_metrics.get('rewardRiskRatio')}, profitFactor={holdout_metrics.get('profitFactor')}, maxDrawdown={holdout_metrics.get('maxDrawdownPct')}.",
            "Do not start paper, Dry-run, or live trading until a probability-gated walk-forward candidate confirms it.",
        ]
    best = ranked[0] if ranked else {}
    metrics = best.get("gatedMetrics", {})
    mined = mined_candidates[0] if mined_candidates else None
    mined_note = ""
    if mined:
        mined_metrics = mined.get("metrics", {})
        mined_note = (
            f" Best mined observation: trades={mined_metrics.get('tradeCount')}, "
            f"winRate={mined_metrics.get('winRatePct')}, "
            f"rewardRisk={mined_metrics.get('rewardRiskRatio')}, "
            f"profitFactor={mined_metrics.get('profitFactor')}, "
            f"maxDrawdown={mined_metrics.get('maxDrawdownPct')}."
        )
    return [
        "No expanded-universe candidate cleared the relaxed shadow-watchlist gate.",
        "Keep researching features before any shadow/paper workflow.",
        f"Best observed gated metrics: trades={metrics.get('tradeCount')}, winRate={metrics.get('winRatePct')}, rewardRisk={metrics.get('rewardRiskRatio')}, profitFactor={metrics.get('profitFactor')}, maxDrawdown={metrics.get('maxDrawdownPct')}.{mined_note}",
    ]


def write_summary(report: dict[str, Any], path: Path) -> None:
    decision = report["decision"]
    best = report.get("bestCandidate") or {}
    metrics = best.get("gatedMetrics", {})
    mined = report.get("bestDeterministicMinedCandidate") or {}
    mined_metrics = mined.get("metrics", {})
    lines = [
        "# V13.5.1 Expanded Relaxed Derivatives Research Report",
        "",
        "This report is research-only. Relaxed candidates are shadow-watchlist candidates, not trading approval.",
        "",
        "## Decision",
        "",
        f"- Probability hard gate approved: `{decision['probabilityHardGateApproved']}`",
        f"- Probability relaxed shadow-watchlist approved: `{decision['probabilityRelaxedShadowWatchlistApproved']}`",
        f"- Deterministic forward-confirmation candidate found: `{decision['deterministicForwardConfirmationCandidateFound']}`",
        f"- Deterministic holdout relaxed candidate found: `{decision['deterministicHoldoutRelaxedCandidateFound']}`",
        f"- Paper approved: `{decision['paperApproved']}`",
        f"- Dry-run approved: `{decision['dryRunApproved']}`",
        f"- Live trading approved: `{decision['liveTradingApproved']}`",
        f"- Reason: `{decision['reason']}`",
        "",
        "## Best Probability-Gated Candidate",
        "",
        f"- Trade count: `{metrics.get('tradeCount')}`",
        f"- Win rate: `{metrics.get('winRatePct')}`",
        f"- Reward/risk: `{metrics.get('rewardRiskRatio')}`",
        f"- Profit factor: `{metrics.get('profitFactor')}`",
        f"- Total return: `{metrics.get('totalReturnPct')}`",
        f"- Max drawdown: `{metrics.get('maxDrawdownPct')}`",
        f"- Hard gate passed: `{best.get('hardGatePassed')}`",
        f"- Relaxed gate passed: `{best.get('relaxedShadowWatchlistPassed')}`",
        f"- Observation gate passed: `{best.get('observationGatePassed')}`",
        "",
        "## Best Deterministic Mined Candidate",
        "",
        f"- Columns: `{', '.join(mined.get('columns', [])) if mined else 'none'}`",
        f"- Values: `{', '.join(mined.get('values', [])) if mined else 'none'}`",
        f"- Trade count: `{mined_metrics.get('tradeCount')}`",
        f"- Win rate: `{mined_metrics.get('winRatePct')}`",
        f"- Reward/risk: `{mined_metrics.get('rewardRiskRatio')}`",
        f"- Profit factor: `{mined_metrics.get('profitFactor')}`",
        f"- Max drawdown: `{mined_metrics.get('maxDrawdownPct')}`",
        f"- Hard gate passed: `{mined.get('hardGatePassed') if mined else False}`",
        f"- Relaxed gate passed: `{mined.get('relaxedShadowWatchlistPassed') if mined else False}`",
        f"- Holdout metrics: `{mined.get('holdoutMetrics') if mined else None}`",
        "",
        "## Search",
        "",
        f"- Config count: `{report['searchSummary']['configCount']}`",
        f"- Hard passing configs: `{report['searchSummary']['hardPassingConfigCount']}`",
        f"- Relaxed passing configs: `{report['searchSummary']['relaxedPassingConfigCount']}`",
        f"- Observation passing configs: `{report['searchSummary']['observationPassingConfigCount']}`",
        f"- Deterministic holdout relaxed passing count: `{report['searchSummary']['deterministicHoldoutRelaxedPassingCount']}`",
        f"- Deterministic full-sample relaxed count: `{report['searchSummary']['deterministicFullSampleRelaxedCount']}`",
        "",
        "## Data",
        "",
        f"- Panel rows: `{report['dataSummary']['panelRows']}`",
        f"- Loaded pairs: `{len(report['dataSummary']['loadedPairs'])}`",
        f"- Missing pairs: `{', '.join(report['dataSummary']['missingPairs']) or 'none'}`",
        f"- Open interest status: `{report['dataSummary']['openInterestStatus']}`",
        "",
        "## Recommendations",
        "",
        *[f"- {item}" for item in report.get("recommendations", [])],
        "",
    ]
    write_text(path, "\n".join(lines))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pairs", default=None)
    parser.add_argument("--timeframe", default="1h", choices=["1h", "4h"])
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--max-configs", type=int, default=None)
    parser.add_argument("--output-report", default=str(DEFAULT_OUTPUT_REPORT))
    parser.add_argument("--output-summary", default=str(DEFAULT_OUTPUT_SUMMARY))
    parser.add_argument("--output-signals", default=str(DEFAULT_OUTPUT_SIGNALS))
    args = parser.parse_args()

    pairs = parse_pairs(args.pairs) if args.pairs else discover_local_pairs(args.timeframe)
    report = run_expanded_relaxed_research(
        pairs=pairs,
        timeframe=args.timeframe,
        folds=args.folds,
        max_configs=args.max_configs,
    )
    signal_sample = report.pop("_shadowSignalSample", [])
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
    print(f"decision={report.get('decision')}")
    best = report.get("bestCandidate") or {}
    print(f"bestGatedMetrics={best.get('gatedMetrics')}")


if __name__ == "__main__":
    main()
