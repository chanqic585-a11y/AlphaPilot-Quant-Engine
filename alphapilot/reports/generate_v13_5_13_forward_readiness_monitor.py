"""Generate V13.5.13 active strategy forward readiness monitor.

The monitor checks whether enough post-selection public candles exist to create
closed forward local paper samples for the active V13.5.7 strategy. It does not
create orders, call exchange APIs, or auto trade.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from alphapilot.derivatives.feature_panel import DEFAULT_DATA_DIR, build_derivatives_feature_panel
from alphapilot.reports.generate_v13_5_1_expanded_relaxed_research_report import discover_local_pairs
from alphapilot.reports.generate_v13_5_12_active_alpha_overlay_replay_report import _parse_pool_id
from alphapilot.reports.generate_v13_5_derivatives_ml_strategy_report import _json_ready, write_json, write_text


VERSION = "V13.5.13"
REPORT_ID = "v13_5_13_forward_readiness_monitor"
DEFAULT_CONTROL_TOWER_REPORT = Path("reports/v13_5_9_strategy_control_tower_report.json")
DEFAULT_ALPHA_OVERLAY_REPORT = Path("reports/v13_5_7_external_alpha_overlay_report.json")
DEFAULT_OUTPUT_REPORT = Path("reports/v13_5_13_forward_readiness_monitor_report.json")
DEFAULT_OUTPUT_SUMMARY = Path("reports/v13_5_13_forward_readiness_monitor_summary.md")


TIMEFRAME_HOURS = {
    "15m": 0.25,
    "1h": 1,
    "4h": 4,
    "1d": 24,
}


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_active_pool_id(control_tower_report: Path) -> str:
    data = _load_json(control_tower_report)
    primary_strategy_id = (data.get("decision") or {}).get("primaryActiveStrategyId")
    for state in data.get("strategyStates") or []:
        if state.get("strategy_id") == primary_strategy_id and state.get("candidate_pool_id"):
            return str(state["candidate_pool_id"])
    raise ValueError("No active candidate pool id found in control tower report.")


def _parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def _latest_by_pair(panel: pd.DataFrame) -> dict[str, str | None]:
    if panel.empty:
        return {}
    output: dict[str, str | None] = {}
    for pair, group in panel.groupby("pair"):
        latest = pd.to_datetime(group["date"], utc=True, errors="coerce").max()
        output[str(pair)] = latest.isoformat() if pd.notna(latest) else None
    return output


def _bars_after_selection(panel: pd.DataFrame, selection_time: datetime) -> dict[str, int]:
    if panel.empty:
        return {}
    output: dict[str, int] = {}
    dates = pd.to_datetime(panel["date"], utc=True, errors="coerce")
    working = panel.copy()
    working["_date"] = dates
    for pair, group in working.groupby("pair"):
        output[str(pair)] = int((group["_date"] > selection_time).sum())
    return output


def build_forward_readiness_monitor(
    *,
    control_tower_report: Path = DEFAULT_CONTROL_TOWER_REPORT,
    alpha_overlay_report: Path = DEFAULT_ALPHA_OVERLAY_REPORT,
    data_dir: Path = DEFAULT_DATA_DIR,
) -> dict[str, Any]:
    active_pool_id = _load_active_pool_id(control_tower_report)
    active_pool = _parse_pool_id(active_pool_id)
    timeframe = active_pool["timeframe"]
    alpha_report = _load_json(alpha_overlay_report)
    selection_time = _parse_utc(alpha_report["generatedAt"])
    timeframe_hours = TIMEFRAME_HOURS.get(timeframe)
    if timeframe_hours is None:
        raise ValueError(f"Unsupported timeframe for readiness monitor: {timeframe}")
    required_horizon = timedelta(hours=timeframe_hours * active_pool["horizonBars"])
    earliest_closed_sample_time = selection_time + required_horizon

    pairs = discover_local_pairs(timeframe, data_dir=data_dir)
    panel_result = build_derivatives_feature_panel(pairs=pairs, timeframe=timeframe, data_dir=data_dir)
    latest_by_pair = _latest_by_pair(panel_result.rows)
    bars_after = _bars_after_selection(panel_result.rows, selection_time)
    latest_times = [
        _parse_utc(value)
        for value in latest_by_pair.values()
        if value
    ]
    latest_local_candle = max(latest_times) if latest_times else None
    forward_closed_samples_possible = bool(
        latest_local_candle and latest_local_candle >= earliest_closed_sample_time
    )
    pair_ready = {
        pair: count >= active_pool["horizonBars"]
        for pair, count in bars_after.items()
    }
    ready_pair_count = sum(1 for value in pair_ready.values() if value)
    status = "ready_for_forward_local_paper_refresh" if forward_closed_samples_possible else "waiting_for_forward_horizon"
    if not latest_local_candle:
        status = "no_local_candles_available"
    return {
        "version": VERSION,
        "reportId": REPORT_ID,
        "generatedAt": datetime.now(UTC).isoformat(),
        "status": status,
        "objective": (
            "Check whether the active strategy has enough post-selection public candles "
            "to produce closed forward local paper samples."
        ),
        "activePool": {
            "poolId": active_pool_id,
            **active_pool,
        },
        "selection": {
            "selectionSourceReport": str(alpha_overlay_report),
            "selectionTime": selection_time.isoformat(),
            "timeframeHours": timeframe_hours,
            "requiredHorizonBars": active_pool["horizonBars"],
            "requiredHorizonHours": required_horizon.total_seconds() / 3600,
            "earliestClosedSampleTime": earliest_closed_sample_time.isoformat(),
        },
        "localData": {
            "dataDir": str(data_dir),
            "loadedPairCount": len(panel_result.loaded_pairs),
            "missingPairs": panel_result.missing_pairs,
            "latestLocalCandle": latest_local_candle.isoformat() if latest_local_candle else None,
            "latestByPair": latest_by_pair,
            "barsAfterSelectionByPair": bars_after,
            "readyPairCount": ready_pair_count,
            "pairReadyForClosedForwardSample": pair_ready,
        },
        "decision": {
            "forwardClosedSamplesPossible": forward_closed_samples_possible,
            "readyForForwardLocalPaperRefresh": forward_closed_samples_possible,
            "exchangeDryRunApproved": False,
            "liveTradingApproved": False,
            "reason": (
                "post_selection_horizon_available"
                if forward_closed_samples_possible
                else "not_enough_post_selection_4h_candles_for_closed_forward_samples"
            ),
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
    selection = report["selection"]
    local = report["localData"]
    decision = report["decision"]
    lines = [
        "# V13.5.13 Forward Readiness Monitor",
        "",
        "This monitor checks whether enough post-selection public candles exist for closed forward local paper samples.",
        "It does not create orders, use API keys, or auto trade.",
        "",
        "## Active Pool",
        "",
        f"- Pool id: `{active['poolId']}`",
        f"- Timeframe: `{active['timeframe']}`",
        f"- Horizon bars: `{active['horizonBars']}`",
        f"- Stop loss: `{active['stopLossPct']}`",
        f"- Target R: `{active['rewardRMultiple']}`",
        "",
        "## Forward Horizon",
        "",
        f"- Selection time: `{selection['selectionTime']}`",
        f"- Required horizon hours: `{selection['requiredHorizonHours']}`",
        f"- Earliest closed sample time: `{selection['earliestClosedSampleTime']}`",
        f"- Latest local candle: `{local['latestLocalCandle']}`",
        f"- Loaded pairs: `{local['loadedPairCount']}`",
        f"- Ready pair count: `{local['readyPairCount']}`",
        "",
        "## Decision",
        "",
        f"- Forward closed samples possible: `{decision['forwardClosedSamplesPossible']}`",
        f"- Ready for forward local paper refresh: `{decision['readyForForwardLocalPaperRefresh']}`",
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
    parser = argparse.ArgumentParser(description="Generate V13.5.13 forward readiness monitor.")
    parser.add_argument("--control-tower-report", default=str(DEFAULT_CONTROL_TOWER_REPORT))
    parser.add_argument("--alpha-overlay-report", default=str(DEFAULT_ALPHA_OVERLAY_REPORT))
    parser.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR))
    parser.add_argument("--output-report", default=str(DEFAULT_OUTPUT_REPORT))
    parser.add_argument("--output-summary", default=str(DEFAULT_OUTPUT_SUMMARY))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_forward_readiness_monitor(
        control_tower_report=Path(args.control_tower_report),
        alpha_overlay_report=Path(args.alpha_overlay_report),
        data_dir=Path(args.data_dir),
    )
    write_json(Path(args.output_report), _json_ready(report))
    write_text(Path(args.output_summary), build_summary(report))


if __name__ == "__main__":
    main()
