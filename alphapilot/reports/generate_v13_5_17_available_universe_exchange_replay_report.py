"""Generate V13.5.17 available-universe exchange-aware replay report.

This expands the fixed active-pool replay to every locally available public
4h futures file per exchange. It does not download data, tune parameters, run
Dry-run, create orders, or connect to private exchange endpoints.
"""

from __future__ import annotations

import argparse
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from alphapilot.derivatives.exchange_feature_panel import build_exchange_feature_panel, discover_exchange_pairs
from alphapilot.factors.alpha101_style_overlay import add_alpha101_style_factors
from alphapilot.ml_gate.high_reward_event_setups import add_high_reward_event_setups
from alphapilot.ml_gate.high_reward_triple_barrier import build_high_reward_labeled_events
from alphapilot.ml_gate.probability_gate import evaluate_trades
from alphapilot.ml_gate.triple_barrier import BarrierConfig
from alphapilot.reports.generate_v13_5_7_external_alpha_overlay_report import _apply_overlay_filter
from alphapilot.reports.generate_v13_5_12_active_alpha_overlay_replay_report import _parse_pool_id
from alphapilot.reports.generate_v13_5_derivatives_ml_strategy_report import _json_ready, write_json, write_text


VERSION = "V13.5.17"
REPORT_ID = "v13_5_17_available_universe_exchange_replay_report"
DEFAULT_OUTPUT_REPORT = Path("reports/v13_5_17_available_universe_exchange_replay_report.json")
DEFAULT_OUTPUT_SUMMARY = Path("reports/v13_5_17_available_universe_exchange_replay_summary.md")
DEFAULT_OUTPUT_SIGNAL_LOG = Path("reports/v13_5_17_available_universe_exchange_signal_log.json")
DEFAULT_ACTIVE_POOL_ID = "4h:alpha_short_exhaustion_pressure_watch:sl0.06:h24"
DEFAULT_EXCHANGES = ["okx", "binance", "bybit"]


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


def _metric_row(label: str, events: pd.DataFrame) -> dict[str, Any]:
    return {"label": label, **evaluate_trades(events)}


def _metrics_by_column(events: pd.DataFrame, column: str, limit: int = 50) -> list[dict[str, Any]]:
    if events.empty or column not in events.columns:
        return []
    rows = [_metric_row(str(value), group) for value, group in events.groupby(column, dropna=False)]
    return sorted(rows, key=lambda row: (row.get("tradeCount") or 0, row.get("profitFactor") or 0), reverse=True)[:limit]


def _signal_rows(events: pd.DataFrame, pool_id: str, limit: int = 500) -> list[dict[str, Any]]:
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
    ]
    output: list[dict[str, Any]] = []
    for _, row in events.sort_values(["entryDate", "exchange", "pair"]).tail(limit).iterrows():
        payload = {column: row.get(column) for column in columns}
        payload["candidateId"] = pool_id
        payload["source"] = "v13_5_17_available_universe_exchange_replay_signal_log"
        payload["historicalReplayOnly"] = True
        output.append(payload)
    return _json_ready(output)


def _date_range(frame: pd.DataFrame) -> dict[str, Any]:
    if frame.empty or "date" not in frame:
        return {"firstDate": None, "lastDate": None}
    dates = pd.to_datetime(frame["date"], utc=True, errors="coerce").dropna()
    if dates.empty:
        return {"firstDate": None, "lastDate": None}
    return {"firstDate": dates.min().isoformat(), "lastDate": dates.max().isoformat()}


def _run_exchange(exchange: str, pool: dict[str, Any], data_root: Path, max_pairs: int | None) -> tuple[dict[str, Any], pd.DataFrame]:
    discovered_pairs = discover_exchange_pairs(exchange, timeframe=pool["timeframe"], data_root=data_root)
    selected_pairs = discovered_pairs[:max_pairs] if max_pairs else discovered_pairs
    panel_result = build_exchange_feature_panel(exchange, pairs=selected_pairs, timeframe=pool["timeframe"], data_root=data_root)
    panel = panel_result.rows
    panel_range = _date_range(panel)
    if panel.empty:
        return {
            "exchange": exchange,
            "status": "no_panel_rows",
            "discoveredPairCount": len(discovered_pairs),
            "selectedPairCount": len(selected_pairs),
            "loadedPairs": [],
            "missingPairs": selected_pairs,
            "panelRows": 0,
            "dateRange": panel_range,
            "activePoolEvents": _metric_row("active_pool_events", pd.DataFrame()),
            "allHighRewardEvents": _metric_row("all_high_reward_events", pd.DataFrame()),
            "eventsByPair": [],
        }, pd.DataFrame()

    enriched = add_high_reward_event_setups(add_alpha101_style_factors(panel))
    barrier = BarrierConfig(
        stop_loss_pct=pool["stopLossPct"],
        reward_r_multiple=pool["rewardRMultiple"],
        horizon_bars=pool["horizonBars"],
        fee_rate_roundtrip=0.001,
        slippage_rate_roundtrip=0.001,
    )
    all_events = build_high_reward_labeled_events(enriched, barrier)
    if not all_events.empty:
        all_events["exchange"] = exchange
    selected = all_events[_apply_overlay_filter(all_events, pool["overlayId"])].copy() if not all_events.empty else all_events
    if not selected.empty:
        selected["exchange"] = exchange

    return {
        "exchange": exchange,
        "status": "completed",
        "discoveredPairCount": len(discovered_pairs),
        "selectedPairCount": len(selected_pairs),
        "loadedPairs": panel_result.loaded_pairs,
        "missingPairs": panel_result.missing_pairs,
        "missingOptionalSources": panel_result.missing_optional_sources,
        "panelRows": int(len(panel)),
        "dateRange": panel_range,
        "allHighRewardEvents": _metric_row("all_high_reward_events", all_events),
        "activePoolEvents": _metric_row("active_pool_events", selected),
        "eventsByPair": _metrics_by_column(selected, "pair", limit=25),
    }, selected


def _decision(combined: pd.DataFrame, exchange_reports: list[dict[str, Any]]) -> dict[str, Any]:
    trade_count = int(len(combined))
    unique_exchanges = int(combined["exchange"].nunique()) if not combined.empty and "exchange" in combined else 0
    unique_pairs = int(combined["pair"].nunique()) if not combined.empty and "pair" in combined else 0
    okx_count = next((report["activePoolEvents"].get("tradeCount") or 0 for report in exchange_reports if report["exchange"] == "okx"), 0)
    non_okx_count = trade_count - int(okx_count)
    sample_adequate = trade_count >= 60 and unique_pairs >= 10
    exchange_balance_adequate = non_okx_count >= 20 and unique_exchanges >= 3
    return {
        "availableUniverseReplayCompleted": all(report["status"] == "completed" for report in exchange_reports),
        "activePoolTradeCount": trade_count,
        "activePoolUniquePairs": unique_pairs,
        "activePoolUniqueExchanges": unique_exchanges,
        "sampleAdequate": sample_adequate,
        "exchangeBalanceAdequate": exchange_balance_adequate,
        "readyForExchangeDryRunReview": False,
        "exchangeDryRunApproved": False,
        "liveTradingApproved": False,
        "reason": "The fixed pool can be replayed on available local data, but exchange balance and forward validation remain insufficient for Dry-run review.",
        "nextAction": "download_resumable_non_okx_universe_or_wait_for_forward_readiness",
    }


def _summary_markdown(report: dict[str, Any]) -> str:
    combined = report["combinedActivePoolMetrics"]
    decision = report["decision"]
    lines = [
        "# AlphaPilot V13.5.17 Available-Universe Exchange Replay",
        "",
        "This report expands the fixed active-pool replay to all locally available public 4h futures files per exchange.",
        "",
        "## Combined Active Pool Metrics",
        "",
        f"- tradeCount: {combined.get('tradeCount')}",
        f"- winRatePct: {combined.get('winRatePct')}",
        f"- profitFactor: {combined.get('profitFactor')}",
        f"- rewardRiskRatio: {combined.get('rewardRiskRatio')}",
        f"- maxDrawdownPct: {combined.get('maxDrawdownPct')}",
        "",
        "## By Exchange",
        "",
    ]
    for report_row in report["exchangeReports"]:
        active = report_row["activePoolEvents"]
        lines.append(
            f"- {report_row['exchange']}: pairs={report_row['loadedPairs'].__len__()} / {report_row['discoveredPairCount']}, "
            f"panelRows={report_row['panelRows']}, activeTrades={active.get('tradeCount')}, "
            f"winRate={active.get('winRatePct')}, pf={active.get('profitFactor')}"
        )
    lines.extend(
        [
            "",
            "## Decision",
            "",
            f"- availableUniverseReplayCompleted: {decision['availableUniverseReplayCompleted']}",
            f"- sampleAdequate: {decision['sampleAdequate']}",
            f"- exchangeBalanceAdequate: {decision['exchangeBalanceAdequate']}",
            f"- readyForExchangeDryRunReview: {decision['readyForExchangeDryRunReview']}",
            f"- nextAction: {decision['nextAction']}",
            "",
            "## Safety Boundary",
            "",
            "- No Trade API.",
            "- No Withdraw API.",
            "- No API key storage.",
            "- No real account reads.",
            "- No real position reads.",
            "- No order creation.",
            "- No automatic trading.",
        ]
    )
    return "\n".join(lines) + "\n"


def generate_report(args: argparse.Namespace) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    exchanges = _parse_csv(args.exchanges, DEFAULT_EXCHANGES)
    pool = _parse_pool_id(args.active_pool_id)
    exchange_reports = []
    selected_frames = []
    max_pairs = args.max_pairs if args.max_pairs and args.max_pairs > 0 else None
    for exchange in exchanges:
        exchange_report, selected = _run_exchange(exchange, pool, args.data_root, max_pairs)
        exchange_reports.append(exchange_report)
        if not selected.empty:
            selected_frames.append(selected)
    combined = pd.concat(selected_frames, ignore_index=True) if selected_frames else pd.DataFrame()
    report = {
        "version": VERSION,
        "reportId": REPORT_ID,
        "generatedAt": utc_now(),
        "activePoolId": args.active_pool_id,
        "poolConfig": pool,
        "scope": {
            "exchanges": exchanges,
            "timeframe": pool["timeframe"],
            "dataRoot": str(args.data_root),
            "maxPairsPerExchange": max_pairs,
            "localPublicDataOnly": True,
        },
        "exchangeReports": exchange_reports,
        "combinedActivePoolMetrics": _metric_row("combined_active_pool_events", combined),
        "combinedByExchange": _metrics_by_column(combined, "exchange"),
        "combinedByPair": _metrics_by_column(combined, "pair"),
        "decision": _decision(combined, exchange_reports),
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
    return _json_ready(report), _signal_rows(combined, args.active_pool_id)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate V13.5.17 available-universe exchange replay report.")
    parser.add_argument("--data-root", type=Path, default=Path("user_data/data"))
    parser.add_argument("--exchanges", default=",".join(DEFAULT_EXCHANGES))
    parser.add_argument("--active-pool-id", default=DEFAULT_ACTIVE_POOL_ID)
    parser.add_argument("--max-pairs", type=int, default=0)
    parser.add_argument("--output-report", type=Path, default=DEFAULT_OUTPUT_REPORT)
    parser.add_argument("--output-summary", type=Path, default=DEFAULT_OUTPUT_SUMMARY)
    parser.add_argument("--output-signal-log", type=Path, default=DEFAULT_OUTPUT_SIGNAL_LOG)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report, signal_rows = generate_report(args)
    write_json(args.output_report, report)
    write_text(args.output_summary, _summary_markdown(report))
    write_json(args.output_signal_log, signal_rows)
    print(f"Wrote {args.output_report}")
    print(f"Wrote {args.output_summary}")
    print(f"Wrote {args.output_signal_log}")
    print(
        "combinedTrades="
        f"{report['combinedActivePoolMetrics'].get('tradeCount')} "
        f"sampleAdequate={report['decision']['sampleAdequate']} "
        f"exchangeBalanceAdequate={report['decision']['exchangeBalanceAdequate']}"
    )


if __name__ == "__main__":
    main()
