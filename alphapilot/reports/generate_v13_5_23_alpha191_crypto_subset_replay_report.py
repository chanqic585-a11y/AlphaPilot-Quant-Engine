"""Generate V13.5.23 Alpha191 crypto-safe subset replay report.

This report implements a small, fixed Alpha191-inspired factor subset and
evaluates it against AlphaPilot's existing local historical replay gates. The
implementation is concept-inspired only; no Alpha191 full formulas are copied.

The report is research-only. It does not call Trade API, Withdraw API, store API
keys, read real accounts or positions, create orders, approve exchange Dry-run,
or enable automatic trading.
"""

from __future__ import annotations

import argparse
import math
from argparse import Namespace
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from alphapilot.derivatives.exchange_feature_panel import build_exchange_feature_panel, discover_exchange_pairs
from alphapilot.factors.alpha101_style_overlay import add_alpha101_style_factors
from alphapilot.factors.alpha191_crypto_safe_subset import (
    ALPHA191_CRYPTO_SAFE_FACTOR_COLUMNS,
    add_alpha191_crypto_safe_factors,
)
from alphapilot.ml_gate.high_reward_event_setups import add_high_reward_event_setups
from alphapilot.ml_gate.high_reward_triple_barrier import build_high_reward_labeled_events
from alphapilot.ml_gate.probability_gate import evaluate_trades
from alphapilot.ml_gate.triple_barrier import BarrierConfig
from alphapilot.paper_sandbox.local_paper_ledger import LocalPaperSandboxConfig, simulate_local_paper_ledger
from alphapilot.paper_sandbox.risk_normalized_replay import (
    ExitAwareLossPolicy,
    evaluate_exit_aware_loss_policies,
    prepare_signal_frame,
)
from alphapilot.reports.generate_v13_5_12_active_alpha_overlay_replay_report import _parse_pool_id
from alphapilot.reports.generate_v13_5_17_available_universe_exchange_replay_report import DEFAULT_ACTIVE_POOL_ID
from alphapilot.reports.generate_v13_5_20_exit_aware_loss_cooldown_report import DEFAULT_POLICIES
from alphapilot.reports.generate_v13_5_20_exit_aware_loss_cooldown_report import _gate as exit_policy_gate
from alphapilot.reports.generate_v13_5_21_local_paper_refresh_candidate_report import _gate as local_paper_gate
from alphapilot.reports.generate_v13_5_derivatives_ml_strategy_report import _json_ready, write_json, write_text


VERSION = "V13.5.23"
REPORT_ID = "v13_5_23_alpha191_crypto_subset_replay_report"
DEFAULT_OUTPUT_REPORT = Path("reports/v13_5_23_alpha191_crypto_subset_replay_report.json")
DEFAULT_OUTPUT_SUMMARY = Path("reports/v13_5_23_alpha191_crypto_subset_replay_summary.md")
DEFAULT_OUTPUT_SIGNAL_LOG = Path("reports/v13_5_23_alpha191_crypto_subset_signal_log.json")
DEFAULT_OUTPUT_SELECTED = Path("reports/v13_5_23_alpha191_crypto_subset_selected_signals.json")
DEFAULT_EXCHANGES = ["okx", "binance", "bybit"]
TARGET_R_MULTIPLE = 2.0


@dataclass(frozen=True)
class Alpha191OverlaySpec:
    overlay_id: str
    description: str


ALPHA191_OVERLAY_SPECS = [
    Alpha191OverlaySpec(
        "a191_short_exhaustion_quality_v01",
        "Short exhaustion context requiring Alpha191-inspired volume-price exhaustion and liquidity-range quality.",
    ),
    Alpha191OverlaySpec(
        "a191_short_range_rejection_v01",
        "Short failed-breakout context requiring Alpha191-inspired range rejection pressure.",
    ),
    Alpha191OverlaySpec(
        "a191_short_residual_exhaustion_v01",
        "Short context requiring strong BTC-residual relative strength and exhaustion pressure.",
    ),
    Alpha191OverlaySpec(
        "a191_long_capitulation_reclaim_v01",
        "Long capitulation context requiring Alpha191-inspired rebound pressure and lower-range reclaim.",
    ),
    Alpha191OverlaySpec(
        "a191_long_volume_reclaim_v01",
        "Long failed-breakdown context requiring volume reclaim pressure and liquidity-range quality.",
    ),
    Alpha191OverlaySpec(
        "a191_balanced_liquidity_quality_v01",
        "Existing active-pool direction with Alpha191-inspired liquidity and range-quality controls.",
    ),
]


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


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


def _parse_csv(value: str | None, default: list[str]) -> list[str]:
    if not value:
        return default.copy()
    return [item.strip() for item in value.split(",") if item.strip()]


def _barrier_configs() -> list[BarrierConfig]:
    return [
        BarrierConfig(stop_loss_pct=0.04, reward_r_multiple=TARGET_R_MULTIPLE, horizon_bars=12),
        BarrierConfig(stop_loss_pct=0.05, reward_r_multiple=TARGET_R_MULTIPLE, horizon_bars=18),
        BarrierConfig(stop_loss_pct=0.06, reward_r_multiple=TARGET_R_MULTIPLE, horizon_bars=24),
        BarrierConfig(stop_loss_pct=0.08, reward_r_multiple=TARGET_R_MULTIPLE, horizon_bars=30),
    ]


def _metric_row(label: str, events: pd.DataFrame) -> dict[str, Any]:
    row = {"label": label, **evaluate_trades(events)}
    if not events.empty:
        row["uniquePairs"] = int(events["pair"].nunique()) if "pair" in events else 0
        row["uniqueExchanges"] = int(events["exchange"].nunique()) if "exchange" in events else 0
        entry_months = pd.to_datetime(events["entryDate"], utc=True, errors="coerce").dropna().dt.strftime("%Y-%m")
        row["uniqueMonths"] = int(entry_months.nunique())
    else:
        row["uniquePairs"] = 0
        row["uniqueExchanges"] = 0
        row["uniqueMonths"] = 0
    return row


def _metrics_by_column(events: pd.DataFrame, column: str, limit: int = 30) -> list[dict[str, Any]]:
    if events.empty or column not in events.columns:
        return []
    rows = [_metric_row(str(value), group) for value, group in events.groupby(column, dropna=False)]
    return sorted(rows, key=lambda row: (row.get("tradeCount") or 0, row.get("profitFactor") or 0), reverse=True)[:limit]


def _recent_profit_factor(events: pd.DataFrame, fraction: float = 0.2) -> dict[str, Any]:
    if events.empty:
        return {"sampleCount": 0, "profitFactor": None}
    ordered = events.sort_values("entryDate").reset_index(drop=True)
    count = max(1, int(len(ordered) * fraction))
    sample = ordered.tail(count)
    metrics = evaluate_trades(sample)
    return {"sampleCount": int(len(sample)), "profitFactor": metrics.get("profitFactor")}


def _raw_gate(events: pd.DataFrame) -> dict[str, Any]:
    metrics = _metric_row("candidate", events)
    recent = _recent_profit_factor(events)
    checks = {
        "minTradeCount80": (metrics.get("tradeCount") or 0) >= 80,
        "minUniqueExchanges3": (metrics.get("uniqueExchanges") or 0) >= 3,
        "minUniquePairs10": (metrics.get("uniquePairs") or 0) >= 10,
        "minUniqueMonths8": (metrics.get("uniqueMonths") or 0) >= 8,
        "minProfitFactor1_5": (metrics.get("profitFactor") or 0) >= 1.5,
        "minRewardRisk1_8": (metrics.get("rewardRiskRatio") or 0) >= 1.8,
        "maxDrawdown45Pct": (metrics.get("maxDrawdownPct") or 999) <= 45,
        "minRecentProfitFactor0_9": (recent.get("profitFactor") or 0) >= 0.9,
    }
    return {
        "checks": checks,
        "passed": all(checks.values()),
        "recent": recent,
        "meaning": "Raw Alpha191-inspired overlay gate only, not exchange Dry-run approval.",
    }


def _score(metrics: dict[str, Any], gate: dict[str, Any]) -> float:
    trade_count = min(metrics.get("tradeCount") or 0, 500) / 500
    exchange_count = min(metrics.get("uniqueExchanges") or 0, 3) / 3
    pair_count = min(metrics.get("uniquePairs") or 0, 30) / 30
    profit_factor = min(metrics.get("profitFactor") or 0, 3.0) / 3.0
    reward_risk = min(metrics.get("rewardRiskRatio") or 0, 2.4) / 2.4
    drawdown_penalty = min(metrics.get("maxDrawdownPct") or 100, 80) / 80
    recent_pf = min((gate.get("recent") or {}).get("profitFactor") or 0, 2.5) / 2.5
    return round(
        trade_count * 0.12
        + exchange_count * 0.12
        + pair_count * 0.10
        + profit_factor * 0.24
        + reward_risk * 0.22
        + recent_pf * 0.12
        - drawdown_penalty * 0.08,
        6,
    )


def _apply_alpha191_filter(events: pd.DataFrame, overlay_id: str) -> pd.Series:
    if events.empty:
        return pd.Series([], dtype=bool)
    def column(name: str, default: Any) -> pd.Series:
        if name in events.columns:
            return events[name].fillna(default)
        return pd.Series(default, index=events.index)

    direction = column("direction", "")
    setup = column("setupName", "")
    liquidity_quality = column("a191_liquidity_range_quality", 0)
    short_pressure = column("a191_short_exhaustion_pressure", 0)
    reversal_pressure = column("a191_reversal_pressure", 0)
    range_rejection = column("a191_range_rejection_pressure", 0)
    volume_reclaim = column("a191_volume_reclaim_pressure", 0)
    residual_rank = column("a191_cs_residual_strength_rank", 0.5)
    volume_rank = column("a191_ts_volume_ratio_rank_48", 0.5)
    corr_24 = column("a191_return_volume_corr_24", 0)

    if overlay_id == "a191_short_exhaustion_quality_v01":
        return (
            (direction == "short")
            & (short_pressure >= 0.12)
            & (liquidity_quality >= 0.30)
            & (events["volume_ratio"].fillna(0) >= 2.4)
            & (corr_24 >= -0.35)
        )
    if overlay_id == "a191_short_range_rejection_v01":
        return (
            (setup == "hr_short_failed_breakout_rejection")
            & (range_rejection >= 0.12)
            & (liquidity_quality >= 0.25)
            & (events["rsi14"].fillna(0) >= 56)
        )
    if overlay_id == "a191_short_residual_exhaustion_v01":
        return (
            (direction == "short")
            & (residual_rank >= 0.72)
            & (short_pressure >= 0.09)
            & (volume_rank >= 0.60)
            & (events["btc_regime"].fillna("") != "bull")
        )
    if overlay_id == "a191_long_capitulation_reclaim_v01":
        return (
            (direction == "long")
            & (reversal_pressure >= 0.10)
            & (events["bollinger_z"].fillna(0) <= -1.2)
            & (events["close_location"].fillna(0.5) >= 0.50)
            & (events["btc_return_3"].fillna(0) > -0.055)
        )
    if overlay_id == "a191_long_volume_reclaim_v01":
        return (
            (direction == "long")
            & (volume_reclaim >= 0.08)
            & (liquidity_quality >= 0.25)
            & (events["volume_ratio"].fillna(0) >= 1.35)
            & (events["close_location"].fillna(0.5) >= 0.55)
        )
    if overlay_id == "a191_balanced_liquidity_quality_v01":
        return (
            (liquidity_quality >= 0.38)
            & (events["volume_ratio"].fillna(0) >= 1.4)
            & (events["a191_cs_range_rank"].fillna(0.5) <= 0.90)
            & (direction.isin(["long", "short"]))
        )
    return pd.Series([False] * len(events), index=events.index)


def build_alpha191_observer_signals(
    feature_panel: pd.DataFrame,
    *,
    overlay_id: str,
) -> pd.DataFrame:
    """Return deterministic current-candle signals without labels or path data."""

    if feature_panel.empty:
        return pd.DataFrame()
    enriched = add_high_reward_event_setups(
        add_alpha191_crypto_safe_factors(
            add_alpha101_style_factors(feature_panel.copy())
        )
    )
    signal_frames: list[pd.DataFrame] = []
    for setup_name in (
        "hr_long_failed_breakdown_reclaim",
        "hr_short_failed_breakout_rejection",
        "hr_long_capitulation_reversal",
        "hr_short_blowoff_reversal",
        "hr_long_trend_pullback_acceleration",
        "hr_short_trend_pullback_acceleration",
    ):
        if setup_name not in enriched.columns:
            continue
        selected = enriched[enriched[setup_name].fillna(False)].copy()
        if selected.empty:
            continue
        selected["setupName"] = setup_name
        selected["direction"] = (
            "long" if setup_name.startswith("hr_long_") else "short"
        )
        signal_frames.append(selected)
    if not signal_frames:
        return pd.DataFrame()
    candidates = pd.concat(signal_frames, ignore_index=True)
    selected = candidates[_apply_alpha191_filter(candidates, overlay_id)].copy()
    if selected.empty:
        return pd.DataFrame()
    selected["signalDate"] = pd.to_datetime(selected["date"], utc=True)
    selected["signalTimestampMs"] = (
        selected["signalDate"].astype("int64") // 1_000_000
    )
    selected["overlayId"] = overlay_id
    columns = [
        "pair",
        "timeframe",
        "signalDate",
        "signalTimestampMs",
        "direction",
        "setupName",
        "overlayId",
    ]
    return selected[columns].sort_values(
        ["signalTimestampMs", "pair", "setupName"]
    ).reset_index(drop=True)


def _build_events_for_exchange(
    exchange: str,
    data_root: Path,
    pool: dict[str, Any],
    max_pairs: int | None,
) -> tuple[dict[str, Any], pd.DataFrame]:
    discovered_pairs = discover_exchange_pairs(exchange, timeframe=pool["timeframe"], data_root=data_root)
    selected_pairs = discovered_pairs[:max_pairs] if max_pairs else discovered_pairs
    panel_result = build_exchange_feature_panel(exchange, pairs=selected_pairs, timeframe=pool["timeframe"], data_root=data_root)
    panel = panel_result.rows
    if panel.empty:
        return {
            "exchange": exchange,
            "status": "no_panel_rows",
            "discoveredPairCount": len(discovered_pairs),
            "selectedPairCount": len(selected_pairs),
            "loadedPairs": [],
            "missingPairs": selected_pairs,
            "panelRows": 0,
            "eventRows": 0,
        }, pd.DataFrame()

    enriched = add_high_reward_event_setups(add_alpha191_crypto_safe_factors(add_alpha101_style_factors(panel)))
    event_frames: list[pd.DataFrame] = []
    for barrier in _barrier_configs():
        events = build_high_reward_labeled_events(enriched, barrier)
        if events.empty:
            continue
        events["exchange"] = exchange
        events["candidateStopLossPct"] = barrier.stop_loss_pct
        events["candidateHorizonBars"] = barrier.horizon_bars
        event_frames.append(events)

    all_events = pd.concat(event_frames, ignore_index=True) if event_frames else pd.DataFrame()
    return {
        "exchange": exchange,
        "status": "completed",
        "discoveredPairCount": len(discovered_pairs),
        "selectedPairCount": len(selected_pairs),
        "loadedPairs": panel_result.loaded_pairs,
        "missingPairs": panel_result.missing_pairs,
        "missingOptionalSources": panel_result.missing_optional_sources,
        "panelRows": int(len(panel)),
        "eventRows": int(len(all_events)),
    }, all_events


def _candidate_id(row: dict[str, Any]) -> str:
    return (
        f"{row['timeframe']}:{row['overlayId']}:"
        f"sl{row['stopLossPct']}:h{row['horizonBars']}"
    )


def _candidate_rows(events: pd.DataFrame, pool: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if events.empty:
        return rows
    for spec in ALPHA191_OVERLAY_SPECS:
        for barrier in _barrier_configs():
            mask = (
                (events["candidateStopLossPct"] == barrier.stop_loss_pct)
                & (events["candidateHorizonBars"] == barrier.horizon_bars)
                & _apply_alpha191_filter(events, spec.overlay_id)
            )
            selected = events[mask].copy()
            if selected.empty:
                metrics = _metric_row(spec.overlay_id, selected)
            else:
                metrics = _metric_row(spec.overlay_id, selected)
            gate = _raw_gate(selected)
            row = {
                "overlayId": spec.overlay_id,
                "description": spec.description,
                "timeframe": pool["timeframe"],
                "stopLossPct": barrier.stop_loss_pct,
                "horizonBars": barrier.horizon_bars,
                "targetRMultiple": barrier.reward_r_multiple,
                "metrics": metrics,
                "gate": gate,
                "score": _score(metrics, gate),
            }
            row["candidateId"] = _candidate_id(row)
            rows.append(row)
    return sorted(rows, key=lambda item: (item["gate"]["passed"], item["score"]), reverse=True)


def _signal_rows(events: pd.DataFrame, candidate_id: str, overlay_id: str, limit: int = 2000) -> list[dict[str, Any]]:
    if events.empty:
        return []
    columns = [
        "exchange",
        "pair",
        "timeframe",
        "setupName",
        "direction",
        "signalDate",
        "entryDate",
        "exitDate",
        "entryPrice",
        "exitPrice",
        "exitReason",
        "holdingBars",
        "netReturnPct",
        "rMultiple",
        "btc_regime",
        "return_3",
        "relative_return_6",
        "bollinger_z",
        "volume_ratio",
        "funding_rate",
        "funding_z_60",
        "mark_basis_pct",
        "alpha_exhaustion_pressure",
        "alpha_liquidity_quality",
        "cs_return_12_rank",
        "cs_volume_ratio_rank",
        *ALPHA191_CRYPTO_SAFE_FACTOR_COLUMNS,
    ]
    output: list[dict[str, Any]] = []
    for _, row in events.sort_values(["entryDate", "exchange", "pair"]).tail(limit).iterrows():
        payload = {column: row.get(column) for column in columns}
        payload["candidateId"] = candidate_id
        payload["overlayId"] = overlay_id
        payload["source"] = "v13_5_23_alpha191_crypto_subset_signal_log"
        payload["historicalReplayOnly"] = True
        payload["orderCreation"] = False
        output.append(payload)
    return _json_ready(output)


def _selected_events_for_candidate(events: pd.DataFrame, candidate: dict[str, Any]) -> pd.DataFrame:
    if events.empty or not candidate:
        return pd.DataFrame()
    return events[
        (events["candidateStopLossPct"] == candidate["stopLossPct"])
        & (events["candidateHorizonBars"] == candidate["horizonBars"])
        & _apply_alpha191_filter(events, candidate["overlayId"])
    ].copy()


def _exit_aware_evaluation(signals: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    frame = prepare_signal_frame(signals)
    if frame.empty:
        return [], {"gate": {"passed": False}, "metrics": {}, "policyId": None}, []
    policies: list[ExitAwareLossPolicy] = DEFAULT_POLICIES
    results = evaluate_exit_aware_loss_policies(frame, policies)
    rows = []
    selected_signals: list[dict[str, Any]] = []
    for item in results:
        metrics = item["metrics"]
        gate = exit_policy_gate(metrics)
        row = {
            "policyId": item["policyId"],
            "description": item["description"],
            "metrics": metrics,
            "byExchange": item["byExchange"],
            "gate": gate,
            "selectedSignalCount": int(len(item["selectedSignals"])),
        }
        rows.append(row)
    rows = sorted(
        rows,
        key=lambda row: (
            row["gate"]["passed"],
            row["metrics"].get("profitFactor") or 0,
            row["metrics"].get("rewardRiskRatio") or 0,
            -(row["metrics"].get("maxDrawdownR") or 999),
        ),
        reverse=True,
    )
    best = rows[0] if rows else {"gate": {"passed": False}, "metrics": {}, "policyId": None}
    best_result = next((item for item in results if item["policyId"] == best["policyId"]), None)
    if best_result is not None and not best_result["selectedSignals"].empty:
        selected_signals = _json_ready(best_result["selectedSignals"].to_dict(orient="records"))
    return rows, best, selected_signals


def _simulate_local_paper(signals: list[dict[str, Any]], candidate: dict[str, Any]) -> dict[str, Any]:
    if not signals:
        return {
            "ledgerMetrics": {},
            "gate": {"passed": False, "reason": "no_selected_signals"},
            "skippedSignalCount": 0,
        }
    config = LocalPaperSandboxConfig(
        initial_equity=10_000.0,
        risk_per_signal_pct=1.0,
        max_concurrent_positions=8,
        max_notional_per_signal_pct=35.0,
        stop_loss_pct=float(candidate["stopLossPct"]),
        source="v13_5_23_alpha191_crypto_subset_local_paper",
    )
    ledger = simulate_local_paper_ledger(signals, [candidate["candidateId"]], config)
    gate = local_paper_gate(ledger["metrics"])
    return {
        "config": config.to_dict(),
        "ledgerMetrics": ledger["metrics"],
        "gate": gate,
        "skippedSignalCount": len(ledger.get("skippedSignals", [])),
    }


def _summary_markdown(report: dict[str, Any]) -> str:
    best = report["bestRawCandidate"]
    decision = report["decision"]
    lines = [
        "# AlphaPilot V13.5.23 Alpha191 Crypto-Safe Subset Replay",
        "",
        "This report implements a small Alpha191-inspired factor subset and evaluates it with existing local research gates.",
        "It is concept-inspired only and does not copy Alpha191 formulas.",
        "",
        "## Best Raw Candidate",
        "",
        f"- candidateId: {best.get('candidateId')}",
        f"- overlayId: {best.get('overlayId')}",
        f"- trades: {best.get('metrics', {}).get('tradeCount')}",
        f"- winRatePct: {best.get('metrics', {}).get('winRatePct')}",
        f"- profitFactor: {best.get('metrics', {}).get('profitFactor')}",
        f"- rewardRiskRatio: {best.get('metrics', {}).get('rewardRiskRatio')}",
        f"- maxDrawdownPct: {best.get('metrics', {}).get('maxDrawdownPct')}",
        f"- rawGatePassed: {best.get('gate', {}).get('passed')}",
        "",
        "## Exit-Aware Best Policy",
        "",
        f"- policyId: {report['bestExitAwarePolicy'].get('policyId')}",
        f"- trades: {report['bestExitAwarePolicy'].get('metrics', {}).get('tradeCount')}",
        f"- profitFactor: {report['bestExitAwarePolicy'].get('metrics', {}).get('profitFactor')}",
        f"- rewardRiskRatio: {report['bestExitAwarePolicy'].get('metrics', {}).get('rewardRiskRatio')}",
        f"- maxDrawdownR: {report['bestExitAwarePolicy'].get('metrics', {}).get('maxDrawdownR')}",
        f"- gatePassed: {report['bestExitAwarePolicy'].get('gate', {}).get('passed')}",
        "",
        "## Local Paper Gate",
        "",
        f"- filledSignalCount: {report['localPaperSimulation'].get('ledgerMetrics', {}).get('filledSignalCount')}",
        f"- winRatePct: {report['localPaperSimulation'].get('ledgerMetrics', {}).get('winRatePct')}",
        f"- profitFactor: {report['localPaperSimulation'].get('ledgerMetrics', {}).get('profitFactor')}",
        f"- rewardRiskRatio: {report['localPaperSimulation'].get('ledgerMetrics', {}).get('rewardRiskRatio')}",
        f"- maxDrawdownPct: {report['localPaperSimulation'].get('ledgerMetrics', {}).get('maxDrawdownPct')}",
        f"- gatePassed: {report['localPaperSimulation'].get('gate', {}).get('passed')}",
        "",
        "## Top Candidates",
        "",
    ]
    for row in report["candidateRows"][:12]:
        metric = row["metrics"]
        lines.append(
            f"- {row['candidateId']}: trades={metric.get('tradeCount')}, "
            f"winRate={metric.get('winRatePct')}, pf={metric.get('profitFactor')}, "
            f"rr={metric.get('rewardRiskRatio')}, dd={metric.get('maxDrawdownPct')}, "
            f"rawGate={row['gate']['passed']}"
        )
    lines.extend(
        [
            "",
            "## Decision",
            "",
            f"- alpha191SubsetImplemented: {decision['alpha191SubsetImplemented']}",
            f"- rawReplayGatePassed: {decision['rawReplayGatePassed']}",
            f"- exitAwareGatePassed: {decision['exitAwareGatePassed']}",
            f"- localPaperGatePassed: {decision['localPaperGatePassed']}",
            f"- readyForForwardRefreshComparison: {decision['readyForForwardRefreshComparison']}",
            f"- exchangeDryRunApproved: {decision['exchangeDryRunApproved']}",
            f"- liveTradingApproved: {decision['liveTradingApproved']}",
            f"- nextAction: {decision['nextAction']}",
            "",
            "## Safety Boundary",
            "",
            "- Research replay only.",
            "- No Alpha191 full formula copying.",
            "- No Trade API.",
            "- No Withdraw API.",
            "- No API key storage.",
            "- No real account reads.",
            "- No real position reads.",
            "- No order creation.",
            "- No automatic trading.",
            "- No exchange Dry-run approval.",
            "- No live-trading approval.",
        ]
    )
    return "\n".join(lines) + "\n"


def generate_report(args: argparse.Namespace) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    exchanges = _parse_csv(args.exchanges, DEFAULT_EXCHANGES)
    pool = _parse_pool_id(args.active_pool_id)
    max_pairs = args.max_pairs if args.max_pairs and args.max_pairs > 0 else None

    exchange_reports = []
    event_frames = []
    for exchange in exchanges:
        exchange_report, events = _build_events_for_exchange(exchange, args.data_root, pool, max_pairs)
        exchange_reports.append(exchange_report)
        if not events.empty:
            event_frames.append(events)
    combined_events = pd.concat(event_frames, ignore_index=True) if event_frames else pd.DataFrame()
    candidate_rows = _candidate_rows(combined_events, pool)
    best = candidate_rows[0] if candidate_rows else {}
    best_events = _selected_events_for_candidate(combined_events, best)
    signal_log = _signal_rows(best_events, best.get("candidateId", "none"), best.get("overlayId", "none"))
    exit_rows, best_exit_policy, selected_signals = _exit_aware_evaluation(signal_log)
    local_paper = _simulate_local_paper(selected_signals, best) if best else {"gate": {"passed": False}}
    local_gate_passed = bool(local_paper.get("gate", {}).get("passed"))

    decision = {
        "alpha191SubsetImplemented": True,
        "formulaCopied": False,
        "rawReplayGatePassed": bool(best.get("gate", {}).get("passed")),
        "exitAwareGatePassed": bool(best_exit_policy.get("gate", {}).get("passed")),
        "localPaperGatePassed": local_gate_passed,
        "readyForForwardRefreshComparison": local_gate_passed,
        "readyForExchangeDryRunReview": False,
        "exchangeDryRunApproved": False,
        "liveTradingApproved": False,
        "nextAction": (
            "compare_alpha191_subset_against_new_forward_closed_samples_when_available"
            if local_gate_passed
            else "keep_alpha191_subset_as_research_only_and_do_not_replace_v13_5_21"
        ),
    }
    report = {
        "version": VERSION,
        "reportId": REPORT_ID,
        "generatedAt": utc_now(),
        "status": "completed",
        "sourceCatalog": "reports/v13_5_22_alpha191_factor_candidate_catalog.json",
        "scope": {
            "dataRoot": str(args.data_root),
            "exchanges": exchanges,
            "timeframe": pool["timeframe"],
            "maxPairsPerExchange": max_pairs,
            "localPublicDataOnly": True,
        },
        "factorSubset": {
            "columns": ALPHA191_CRYPTO_SAFE_FACTOR_COLUMNS,
            "conceptSource": "V13.5.22 Alpha191 category and operator metadata only",
            "formulaCopied": False,
            "fullFormulaStored": False,
            "longSourceTextStored": False,
        },
        "exchangeReports": exchange_reports,
        "candidateRows": _json_ready(candidate_rows),
        "bestRawCandidate": _json_ready(best),
        "bestRawCandidateByExchange": _metrics_by_column(best_events, "exchange"),
        "bestRawCandidateByPair": _metrics_by_column(best_events, "pair", limit=40),
        "exitAwarePolicyRows": _json_ready(exit_rows),
        "bestExitAwarePolicy": _json_ready(best_exit_policy),
        "localPaperSimulation": _json_ready(local_paper),
        "decision": decision,
        "safety": {
            "tradeApi": False,
            "withdrawApi": False,
            "apiKeyStorage": False,
            "realAccountRead": False,
            "realPositionRead": False,
            "orderCreation": False,
            "automaticTrading": False,
        },
    }
    return _json_ready(report), signal_log, _json_ready(selected_signals)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate V13.5.23 Alpha191 crypto-safe subset replay report.")
    parser.add_argument("--data-root", type=Path, default=Path("user_data/data"))
    parser.add_argument("--exchanges", default=",".join(DEFAULT_EXCHANGES))
    parser.add_argument("--active-pool-id", default=DEFAULT_ACTIVE_POOL_ID)
    parser.add_argument("--max-pairs", type=int, default=0)
    parser.add_argument("--output-report", type=Path, default=DEFAULT_OUTPUT_REPORT)
    parser.add_argument("--output-summary", type=Path, default=DEFAULT_OUTPUT_SUMMARY)
    parser.add_argument("--output-signal-log", type=Path, default=DEFAULT_OUTPUT_SIGNAL_LOG)
    parser.add_argument("--output-selected", type=Path, default=DEFAULT_OUTPUT_SELECTED)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report, signal_log, selected_signals = generate_report(args)
    write_json(args.output_report, report)
    write_text(args.output_summary, _summary_markdown(report))
    write_json(args.output_signal_log, signal_log)
    write_json(args.output_selected, selected_signals)
    print(f"Wrote {args.output_report}")
    print(f"Wrote {args.output_summary}")
    print(f"Wrote {args.output_signal_log}")
    print(f"Wrote {args.output_selected}")
    print(
        "best="
        f"{report['bestRawCandidate'].get('candidateId')} "
        f"rawGate={report['decision']['rawReplayGatePassed']} "
        f"exitGate={report['decision']['exitAwareGatePassed']} "
        f"localPaperGate={report['decision']['localPaperGatePassed']}"
    )


if __name__ == "__main__":
    main()
