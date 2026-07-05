"""Generate V13.5.16 core multi-exchange replay report.

This report replays the fixed active V13.5.7 research pool on local public
BTC/ETH/SOL data across OKX, Binance, and Bybit. It is a historical research
diagnostic only and does not approve Dry-run or live trading.
"""

from __future__ import annotations

import argparse
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from alphapilot.derivatives.exchange_feature_panel import build_exchange_feature_panel
from alphapilot.factors.alpha101_style_overlay import add_alpha101_style_factors
from alphapilot.ml_gate.high_reward_event_setups import add_high_reward_event_setups
from alphapilot.ml_gate.high_reward_triple_barrier import build_high_reward_labeled_events
from alphapilot.ml_gate.probability_gate import evaluate_trades
from alphapilot.ml_gate.triple_barrier import BarrierConfig
from alphapilot.reports.generate_v13_5_7_external_alpha_overlay_report import _apply_overlay_filter
from alphapilot.reports.generate_v13_5_12_active_alpha_overlay_replay_report import _parse_pool_id
from alphapilot.reports.generate_v13_5_derivatives_ml_strategy_report import _json_ready, write_json, write_text


VERSION = "V13.5.16"
REPORT_ID = "v13_5_16_core_multi_exchange_replay_report"
DEFAULT_OUTPUT_REPORT = Path("reports/v13_5_16_core_multi_exchange_replay_report.json")
DEFAULT_OUTPUT_SUMMARY = Path("reports/v13_5_16_core_multi_exchange_replay_summary.md")
DEFAULT_OUTPUT_SIGNAL_LOG = Path("reports/v13_5_16_core_multi_exchange_signal_log.json")
DEFAULT_ACTIVE_POOL_ID = "4h:alpha_short_exhaustion_pressure_watch:sl0.06:h24"
DEFAULT_EXCHANGES = ["okx", "binance", "bybit"]
DEFAULT_CORE_PAIRS = ["BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT"]


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


def _metrics_by_column(events: pd.DataFrame, column: str) -> list[dict[str, Any]]:
    if events.empty or column not in events.columns:
        return []
    rows = []
    for value, group in events.groupby(column, dropna=False):
        rows.append(_metric_row(str(value), group))
    return sorted(rows, key=lambda row: (row.get("tradeCount") or 0, row.get("profitFactor") or 0), reverse=True)


def _panel_summary(exchange: str, data_dir: Path, panel: pd.DataFrame, loaded_pairs: list[str], missing_pairs: list[str], missing_optional: dict[str, list[str]]) -> dict[str, Any]:
    dates = pd.to_datetime(panel["date"], utc=True, errors="coerce") if not panel.empty and "date" in panel else pd.Series([], dtype="datetime64[ns, UTC]")
    return {
        "exchange": exchange,
        "dataDir": str(data_dir),
        "rowCount": int(len(panel)),
        "loadedPairs": loaded_pairs,
        "missingPairs": missing_pairs,
        "missingOptionalSources": missing_optional,
        "firstDate": dates.min().isoformat() if not dates.empty else None,
        "lastDate": dates.max().isoformat() if not dates.empty else None,
    }


def _signal_rows(events: pd.DataFrame, pool_id: str) -> list[dict[str, Any]]:
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
    for _, row in events.sort_values(["entryDate", "exchange", "pair"]).iterrows():
        payload = {column: row.get(column) for column in columns}
        payload["candidateId"] = pool_id
        payload["source"] = "v13_5_16_core_multi_exchange_replay_signal_log"
        payload["historicalReplayOnly"] = True
        output.append(payload)
    return _json_ready(output)


def _build_exchange_replay(
    exchange: str,
    pairs: list[str],
    pool: dict[str, Any],
    data_root: Path,
) -> tuple[dict[str, Any], pd.DataFrame]:
    panel_result = build_exchange_feature_panel(exchange, pairs=pairs, timeframe=pool["timeframe"], data_root=data_root)
    panel = panel_result.rows
    panel_summary = _panel_summary(
        exchange,
        panel_result.data_dir,
        panel,
        panel_result.loaded_pairs,
        panel_result.missing_pairs,
        panel_result.missing_optional_sources,
    )
    if panel.empty:
        return {
            "exchange": exchange,
            "panel": panel_summary,
            "allHighRewardEvents": _metric_row("all_high_reward_events", pd.DataFrame()),
            "activePoolEvents": _metric_row("active_pool_events", pd.DataFrame()),
            "eventsByPair": [],
            "status": "no_panel_rows",
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
        "panel": panel_summary,
        "allHighRewardEvents": _metric_row("all_high_reward_events", all_events),
        "activePoolEvents": _metric_row("active_pool_events", selected),
        "eventsByPair": _metrics_by_column(selected, "pair"),
        "status": "completed",
    }, selected


def _decision(combined: pd.DataFrame, exchange_reports: list[dict[str, Any]], exchanges: list[str], pairs: list[str]) -> dict[str, Any]:
    completed_exchanges = [report["exchange"] for report in exchange_reports if report["status"] == "completed"]
    trade_count = int(len(combined))
    unique_exchanges = int(combined["exchange"].nunique()) if not combined.empty and "exchange" in combined else 0
    unique_pairs = int(combined["pair"].nunique()) if not combined.empty and "pair" in combined else 0
    adequate_cross_exchange_sample = trade_count >= 60 and unique_exchanges >= 3 and unique_pairs >= len(pairs)
    return {
        "exchangeAwareCoreReplayCompleted": set(completed_exchanges) == set(exchanges),
        "activePoolTradeCount": trade_count,
        "activePoolUniqueExchanges": unique_exchanges,
        "activePoolUniquePairs": unique_pairs,
        "activePoolCrossExchangeSampleAdequate": adequate_cross_exchange_sample,
        "readyForExchangeDryRunReview": False,
        "exchangeDryRunApproved": False,
        "liveTradingApproved": False,
        "reason": "Core multi-exchange replay is historical diagnostics only. Dry-run review still requires forward samples, broader exchange-aware validation, and manual review.",
        "nextAction": "expand_exchange_aware_replay_to_larger_resumable_universe_or_forward_ready_refresh",
    }


def _summary_markdown(report: dict[str, Any]) -> str:
    decision = report["decision"]
    combined = report["combinedActivePoolMetrics"]
    lines = [
        "# AlphaPilot V13.5.16 Core Multi-Exchange Replay",
        "",
        "This report replays the fixed active research pool on local public BTC/ETH/SOL data across OKX, Binance, and Bybit.",
        "",
        "## Active Pool",
        "",
        f"- poolId: {report['activePoolId']}",
        f"- timeframe: {report['poolConfig']['timeframe']}",
        f"- stopLossPct: {report['poolConfig']['stopLossPct']}",
        f"- rewardRMultiple: {report['poolConfig']['rewardRMultiple']}",
        f"- horizonBars: {report['poolConfig']['horizonBars']}",
        "",
        "## Combined Active Pool Metrics",
        "",
        f"- tradeCount: {combined.get('tradeCount')}",
        f"- winRatePct: {combined.get('winRatePct')}",
        f"- profitFactor: {combined.get('profitFactor')}",
        f"- rewardRiskRatio: {combined.get('rewardRiskRatio')}",
        "",
        "## By Exchange",
        "",
    ]
    for exchange in report["exchangeReports"]:
        active = exchange["activePoolEvents"]
        panel = exchange["panel"]
        lines.append(
            f"- {exchange['exchange']}: status={exchange['status']}, panelRows={panel['rowCount']}, "
            f"loadedPairs={len(panel['loadedPairs'])}, activeTrades={active.get('tradeCount')}, "
            f"winRate={active.get('winRatePct')}, pf={active.get('profitFactor')}"
        )
    lines.extend(
        [
            "",
            "## Decision",
            "",
            f"- exchangeAwareCoreReplayCompleted: {decision['exchangeAwareCoreReplayCompleted']}",
            f"- activePoolCrossExchangeSampleAdequate: {decision['activePoolCrossExchangeSampleAdequate']}",
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
    pairs = _parse_csv(args.pairs, DEFAULT_CORE_PAIRS)
    pool_id = args.active_pool_id
    pool = _parse_pool_id(pool_id)
    exchange_reports: list[dict[str, Any]] = []
    selected_frames: list[pd.DataFrame] = []
    for exchange in exchanges:
        exchange_report, selected = _build_exchange_replay(exchange, pairs, pool, args.data_root)
        exchange_reports.append(exchange_report)
        if not selected.empty:
            selected_frames.append(selected)
    combined = pd.concat(selected_frames, ignore_index=True) if selected_frames else pd.DataFrame()
    combined_metrics = _metric_row("combined_active_pool_events", combined)
    report = {
        "version": VERSION,
        "reportId": REPORT_ID,
        "generatedAt": utc_now(),
        "activePoolId": pool_id,
        "poolConfig": pool,
        "scope": {
            "exchanges": exchanges,
            "pairs": pairs,
            "dataRoot": str(args.data_root),
            "localPublicDataOnly": True,
        },
        "exchangeReports": exchange_reports,
        "combinedActivePoolMetrics": combined_metrics,
        "combinedByExchange": _metrics_by_column(combined, "exchange"),
        "combinedByPair": _metrics_by_column(combined, "pair"),
        "decision": _decision(combined, exchange_reports, exchanges, pairs),
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
    return _json_ready(report), _signal_rows(combined, pool_id)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate V13.5.16 core multi-exchange replay report.")
    parser.add_argument("--data-root", type=Path, default=Path("user_data/data"))
    parser.add_argument("--exchanges", default=",".join(DEFAULT_EXCHANGES))
    parser.add_argument("--pairs", default=",".join(DEFAULT_CORE_PAIRS))
    parser.add_argument("--active-pool-id", default=DEFAULT_ACTIVE_POOL_ID)
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
        f"exchangeAwareCoreReplayCompleted={report['decision']['exchangeAwareCoreReplayCompleted']}"
    )


if __name__ == "__main__":
    main()
