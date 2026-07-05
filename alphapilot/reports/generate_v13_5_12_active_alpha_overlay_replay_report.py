"""Generate V13.5.12 active alpha overlay replay report.

This report rebuilds the V13.5.7 active overlay event log and replays it through
the local paper sandbox. It is historical research replay only, not forward
validation, exchange Dry-run, or live trading.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from alphapilot.derivatives.feature_panel import DEFAULT_DATA_DIR, build_derivatives_feature_panel
from alphapilot.factors.alpha101_style_overlay import add_alpha101_style_factors
from alphapilot.ml_gate.high_reward_event_setups import add_high_reward_event_setups
from alphapilot.ml_gate.high_reward_triple_barrier import build_high_reward_labeled_events
from alphapilot.ml_gate.probability_gate import evaluate_trades
from alphapilot.ml_gate.triple_barrier import BarrierConfig
from alphapilot.paper_sandbox.local_paper_ledger import LocalPaperSandboxConfig, simulate_local_paper_ledger
from alphapilot.reports.generate_v13_5_1_expanded_relaxed_research_report import discover_local_pairs
from alphapilot.reports.generate_v13_5_7_external_alpha_overlay_report import _apply_overlay_filter
from alphapilot.reports.generate_v13_5_derivatives_ml_strategy_report import _json_ready, write_json, write_text


VERSION = "V13.5.12"
REPORT_ID = "v13_5_12_active_alpha_overlay_replay_report"
DEFAULT_CONTROL_TOWER_REPORT = Path("reports/v13_5_9_strategy_control_tower_report.json")
DEFAULT_OUTPUT_REPORT = Path("reports/v13_5_12_active_alpha_overlay_replay_report.json")
DEFAULT_OUTPUT_SUMMARY = Path("reports/v13_5_12_active_alpha_overlay_replay_summary.md")
DEFAULT_OUTPUT_SIGNAL_LOG = Path("reports/v13_5_12_active_alpha_overlay_signal_log.json")
DEFAULT_OUTPUT_LEDGER = Path("reports/v13_5_12_active_alpha_overlay_paper_ledger.json")


def _parse_pool_id(pool_id: str) -> dict[str, Any]:
    parts = pool_id.split(":")
    if len(parts) != 4:
        raise ValueError(f"Unsupported active pool id format: {pool_id}")
    timeframe, overlay_id, stop_part, horizon_part = parts
    if not stop_part.startswith("sl") or not horizon_part.startswith("h"):
        raise ValueError(f"Unsupported active pool id format: {pool_id}")
    return {
        "timeframe": timeframe,
        "overlayId": overlay_id,
        "stopLossPct": float(stop_part[2:]),
        "horizonBars": int(horizon_part[1:]),
        "rewardRMultiple": 2.0,
    }


def _load_active_pool_id(control_tower_report: Path) -> str:
    data = json.loads(control_tower_report.read_text(encoding="utf-8"))
    decision = data.get("decision") or {}
    primary_strategy_id = decision.get("primaryActiveStrategyId")
    for state in data.get("strategyStates") or []:
        if state.get("strategy_id") == primary_strategy_id:
            pool_id = state.get("candidate_pool_id")
            if pool_id:
                return str(pool_id)
    raise ValueError("No active candidate pool id found in control tower report.")


def _to_signal_rows(events: pd.DataFrame, pool_id: str) -> list[dict[str, Any]]:
    columns = [
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
    rows: list[dict[str, Any]] = []
    prepared = events.sort_values(["entryDate", "pair", "setupName"]).reset_index(drop=True)
    for _, row in prepared.iterrows():
        payload: dict[str, Any] = {}
        for column in columns:
            value = row.get(column)
            if isinstance(value, pd.Timestamp):
                payload[column] = value.isoformat()
            elif hasattr(value, "item"):
                try:
                    payload[column] = value.item()
                except Exception:
                    payload[column] = str(value)
            else:
                payload[column] = value
        payload["candidateId"] = pool_id
        payload["source"] = "v13_5_12_active_alpha_overlay_replay_signal_log"
        payload["historicalReplayOnly"] = True
        rows.append(payload)
    return rows


def build_active_alpha_overlay_replay(
    *,
    control_tower_report: Path = DEFAULT_CONTROL_TOWER_REPORT,
    data_dir: Path = DEFAULT_DATA_DIR,
) -> dict[str, Any]:
    pool_id = _load_active_pool_id(control_tower_report)
    pool = _parse_pool_id(pool_id)
    timeframe = pool["timeframe"]
    pairs = discover_local_pairs(timeframe, data_dir=data_dir)
    panel_result = build_derivatives_feature_panel(pairs=pairs, timeframe=timeframe, data_dir=data_dir)
    panel = add_high_reward_event_setups(add_alpha101_style_factors(panel_result.rows))
    barrier_config = BarrierConfig(
        stop_loss_pct=pool["stopLossPct"],
        reward_r_multiple=pool["rewardRMultiple"],
        horizon_bars=pool["horizonBars"],
        fee_rate_roundtrip=0.001,
        slippage_rate_roundtrip=0.001,
    )
    all_events = build_high_reward_labeled_events(panel, barrier_config)
    selected = all_events[_apply_overlay_filter(all_events, pool["overlayId"])].copy()
    metrics = evaluate_trades(selected)
    signal_rows = _to_signal_rows(selected, pool_id)
    ledger = simulate_local_paper_ledger(
        signal_rows,
        approved_candidate_ids=[pool_id],
        config=LocalPaperSandboxConfig(
            stop_loss_pct=pool["stopLossPct"],
            source="local_paper_sandbox_v13_5_12_active_alpha_overlay_replay",
        ),
    )
    ledger_metrics = ledger.get("metrics") or {}
    return {
        "version": VERSION,
        "reportId": REPORT_ID,
        "generatedAt": datetime.now(UTC).isoformat(),
        "status": "completed",
        "objective": (
            "Rebuild the V13.5.7 active alpha overlay event log and replay it through "
            "the local paper sandbox as historical research evidence only."
        ),
        "activePool": {
            "poolId": pool_id,
            **pool,
        },
        "dataSource": {
            "localPublicDataDir": str(data_dir),
            "loadedPairs": panel_result.loaded_pairs,
            "missingPairs": panel_result.missing_pairs,
            "missingOptionalSources": panel_result.missing_optional_sources,
            "publicDataOnly": True,
        },
        "eventSummary": {
            "allHighRewardEventCount": int(len(all_events)),
            "activeOverlayEventCount": int(len(selected)),
            "metrics": metrics,
        },
        "paperReplaySummary": {
            "mode": "historical_replay_not_forward_validation",
            "ledgerMetrics": ledger_metrics,
            "skippedSignalCount": len(ledger.get("skippedSignals") or []),
            "filledSignalCount": ledger_metrics.get("filledSignalCount"),
        },
        "signalRows": signal_rows,
        "ledger": ledger,
        "decision": {
            "activeAlphaOverlayReplayCompleted": True,
            "historicalReplayOnly": True,
            "activeStrategySamplesPrepared": len(signal_rows),
            "readyForExchangeDryRunReview": False,
            "exchangeDryRunApproved": False,
            "liveTradingApproved": False,
            "reason": "active_strategy_historical_replay_ready_but_forward_local_paper_still_required",
        },
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


def build_summary(report: dict[str, Any]) -> str:
    active = report["activePool"]
    event_summary = report["eventSummary"]
    replay = report["paperReplaySummary"]
    decision = report["decision"]
    ledger_metrics = replay["ledgerMetrics"]
    lines = [
        "# V13.5.12 Active Alpha Overlay Replay Report",
        "",
        "This report rebuilds the active V13.5.7 alpha overlay event log and replays it through local paper accounting.",
        "It is historical replay only, not forward validation, exchange Dry-run, or live trading.",
        "",
        "## Active Pool",
        "",
        f"- Pool id: `{active['poolId']}`",
        f"- Overlay id: `{active['overlayId']}`",
        f"- Timeframe: `{active['timeframe']}`",
        f"- Stop loss: `{active['stopLossPct']}`",
        f"- Target R: `{active['rewardRMultiple']}`",
        f"- Horizon bars: `{active['horizonBars']}`",
        "",
        "## Event Summary",
        "",
        f"- All high-reward events: `{event_summary['allHighRewardEventCount']}`",
        f"- Active overlay events: `{event_summary['activeOverlayEventCount']}`",
        f"- Event win rate: `{event_summary['metrics'].get('winRatePct')}`",
        f"- Event profit factor: `{event_summary['metrics'].get('profitFactor')}`",
        f"- Event reward/risk: `{event_summary['metrics'].get('rewardRiskRatio')}`",
        "",
        "## Local Paper Replay",
        "",
        f"- Mode: `{replay['mode']}`",
        f"- Filled signals: `{ledger_metrics.get('filledSignalCount')}`",
        f"- Closed trades: `{ledger_metrics.get('tradeCount')}`",
        f"- Win rate: `{ledger_metrics.get('winRatePct')}`",
        f"- Profit factor: `{ledger_metrics.get('profitFactor')}`",
        f"- Reward/risk: `{ledger_metrics.get('rewardRiskRatio')}`",
        f"- Total return: `{ledger_metrics.get('totalReturnPct')}`",
        f"- Max drawdown: `{ledger_metrics.get('maxDrawdownPct')}`",
        f"- Skipped signals: `{replay['skippedSignalCount']}`",
        "",
        "## Decision",
        "",
        f"- Replay completed: `{decision['activeAlphaOverlayReplayCompleted']}`",
        f"- Historical replay only: `{decision['historicalReplayOnly']}`",
        f"- Active strategy samples prepared: `{decision['activeStrategySamplesPrepared']}`",
        f"- Ready for exchange Dry-run review: `{decision['readyForExchangeDryRunReview']}`",
        f"- Exchange Dry-run approved: `{decision['exchangeDryRunApproved']}`",
        f"- Live trading approved: `{decision['liveTradingApproved']}`",
        f"- Reason: `{decision['reason']}`",
        "",
        "## Safety Boundary",
        "",
        "- Public local data only.",
        "- No Trade API.",
        "- No Withdraw API.",
        "- No API key storage.",
        "- No real account reads.",
        "- No real position reads.",
        "- No real orders.",
        "- No automatic trading.",
    ]
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate V13.5.12 active alpha overlay replay report.")
    parser.add_argument("--control-tower-report", default=str(DEFAULT_CONTROL_TOWER_REPORT))
    parser.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR))
    parser.add_argument("--output-report", default=str(DEFAULT_OUTPUT_REPORT))
    parser.add_argument("--output-summary", default=str(DEFAULT_OUTPUT_SUMMARY))
    parser.add_argument("--output-signal-log", default=str(DEFAULT_OUTPUT_SIGNAL_LOG))
    parser.add_argument("--output-ledger", default=str(DEFAULT_OUTPUT_LEDGER))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_active_alpha_overlay_replay(
        control_tower_report=Path(args.control_tower_report),
        data_dir=Path(args.data_dir),
    )
    write_json(Path(args.output_report), _json_ready({key: value for key, value in report.items() if key not in {"signalRows", "ledger"}}))
    write_text(Path(args.output_summary), build_summary(report))
    write_json(Path(args.output_signal_log), _json_ready(report["signalRows"]))
    write_json(Path(args.output_ledger), _json_ready(report["ledger"]))


if __name__ == "__main__":
    main()
