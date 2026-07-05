"""Generate V13.5.2 forward-confirmation and local paper-sandbox report.

V13.5.2 takes the deterministic candidates found by V13.5.1, replays them as
fixed research rules, and checks whether their final holdout segment is strong
enough for a local paper sandbox.

This module is deliberately local-only. It reads public historical files and
local reports, writes JSON/Markdown reports, and never uses API keys, exchange
private endpoints, account data, positions, orders, Freqtrade dry-run, or live
trading.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from alphapilot.derivatives.feature_panel import build_derivatives_feature_panel
from alphapilot.ml_gate.probability_gate import add_probability_buckets, evaluate_trades
from alphapilot.ml_gate.triple_barrier import BarrierConfig, build_labeled_events
from alphapilot.reports.generate_v13_5_1_expanded_relaxed_research_report import discover_local_pairs
from alphapilot.reports.generate_v13_5_derivatives_ml_strategy_report import (
    _json_ready,
    _summarize_by,
    write_json,
    write_text,
)


REPORT_ID = "v13_5_2_forward_confirmation_paper_sandbox_report"
VERSION = "V13.5.2"
DEFAULT_INPUT_1H = Path("reports/v13_5_1_expanded_relaxed_1h_report.json")
DEFAULT_INPUT_4H = Path("reports/v13_5_1_expanded_relaxed_4h_report.json")
DEFAULT_OUTPUT_REPORT = Path("reports/v13_5_2_forward_confirmation_report.json")
DEFAULT_OUTPUT_SUMMARY = Path("reports/v13_5_2_forward_confirmation_summary.md")
DEFAULT_OUTPUT_SIGNALS = Path("reports/v13_5_2_forward_confirmation_signal_log.json")


@dataclass(frozen=True)
class PaperSandboxGate:
    name: str = "local_paper_sandbox_confirmation_gate"
    min_confirmation_trade_count: int = 50
    min_confirmation_win_rate_pct: float = 55
    min_confirmation_reward_risk_ratio: float = 1.8
    min_confirmation_profit_factor: float = 1.35
    max_confirmation_drawdown_pct: float = 20
    require_positive_confirmation_return: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


LOCAL_PAPER_SANDBOX_GATE = PaperSandboxGate()


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _barrier_from_report(candidate: dict[str, Any]) -> BarrierConfig:
    config = candidate.get("barrierConfig") or {}
    return BarrierConfig(
        stop_loss_pct=float(config.get("stop_loss_pct", 0.045)),
        reward_r_multiple=float(config.get("reward_r_multiple", 2.0)),
        horizon_bars=int(config.get("horizon_bars", 36)),
        fee_rate_roundtrip=float(config.get("fee_rate_roundtrip", 0.001)),
        slippage_rate_roundtrip=float(config.get("slippage_rate_roundtrip", 0.001)),
    )


def _candidate_from_report(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    report = _read_json(path)
    candidate = report.get("bestDeterministicMinedCandidate")
    if not candidate:
        return None
    return {
        "sourceReport": str(path),
        "sourceVersion": report.get("version"),
        "timeframe": report.get("timeframe"),
        "pairs": report.get("pairs") or [],
        "columns": candidate.get("columns") or [],
        "values": candidate.get("values") or [],
        "sourceFullSampleMetrics": candidate.get("metrics") or {},
        "sourceHoldoutMetrics": candidate.get("holdoutMetrics") or {},
        "sourceBarrierConfig": candidate.get("barrierConfig") or {},
        "barrierConfig": _barrier_from_report(candidate),
        "sourceWarnings": [
            "Candidate was mined from historical data and may be overfit.",
            "Forward confirmation is required before any local paper sandbox.",
        ],
    }


def _split_events(events: pd.DataFrame, confirmation_fraction: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    if events.empty:
        return events.copy(), events.copy()
    ordered = events.sort_values("signalDate").reset_index(drop=True)
    split_index = max(1, int(len(ordered) * (1 - confirmation_fraction)))
    return ordered.iloc[:split_index].copy(), ordered.iloc[split_index:].copy()


def _evaluate_paper_sandbox_gate(metrics: dict[str, Any], gate: PaperSandboxGate) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    trade_count = metrics.get("tradeCount") or 0
    win_rate = metrics.get("winRatePct") or 0
    reward_risk = metrics.get("rewardRiskRatio") or 0
    profit_factor = metrics.get("profitFactor") or 0
    max_drawdown = metrics.get("maxDrawdownPct")
    total_return = metrics.get("totalReturnPct") or 0

    if trade_count < gate.min_confirmation_trade_count:
        reasons.append(f"confirmation_trade_count_below_{gate.min_confirmation_trade_count}")
    if win_rate < gate.min_confirmation_win_rate_pct:
        reasons.append(f"confirmation_win_rate_below_{gate.min_confirmation_win_rate_pct:g}")
    if reward_risk < gate.min_confirmation_reward_risk_ratio:
        reasons.append(f"confirmation_reward_risk_below_{gate.min_confirmation_reward_risk_ratio:g}")
    if profit_factor < gate.min_confirmation_profit_factor:
        reasons.append(f"confirmation_profit_factor_below_{gate.min_confirmation_profit_factor:g}")
    if max_drawdown is None or max_drawdown > gate.max_confirmation_drawdown_pct:
        reasons.append(f"confirmation_drawdown_above_{gate.max_confirmation_drawdown_pct:g}")
    if gate.require_positive_confirmation_return and total_return <= 0:
        reasons.append("confirmation_return_not_positive")
    return len(reasons) == 0, reasons


def _filter_candidate_events(events: pd.DataFrame, columns: list[str], values: list[str]) -> pd.DataFrame:
    prepared = add_probability_buckets(events)
    if not columns or len(columns) != len(values):
        return prepared.iloc[0:0].copy()
    mask = pd.Series(True, index=prepared.index)
    for column, value in zip(columns, values, strict=True):
        if column not in prepared.columns:
            return prepared.iloc[0:0].copy()
        mask &= prepared[column].astype(str).eq(str(value))
    return prepared[mask].copy().sort_values(["signalDate", "pair", "setupName"]).reset_index(drop=True)


def _signal_log_rows(candidate_id: str, events: pd.DataFrame, limit: int = 500) -> list[dict[str, Any]]:
    if events.empty:
        return []
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
        "funding_rate",
        "funding_z_60",
        "mark_basis_pct",
    ]
    available = [column for column in columns if column in events.columns]
    ordered = events.sort_values("signalDate", ascending=False).head(limit)
    rows = []
    for row in ordered[available].to_dict(orient="records"):
        row["candidateId"] = candidate_id
        row["source"] = "v13_5_2_forward_confirmation_signal_log"
        rows.append(_json_ready(row))
    return rows


def _monthly_breakdown(events: pd.DataFrame) -> list[dict[str, Any]]:
    if events.empty:
        return []
    prepared = events.copy()
    prepared["month"] = prepared["signalDate"].dt.strftime("%Y-%m")
    rows = []
    for month, group in prepared.groupby("month"):
        rows.append({"month": str(month), **evaluate_trades(group)})
    return rows


def _build_candidate_confirmation(
    candidate_id: str,
    candidate: dict[str, Any],
    confirmation_fraction: float,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    timeframe = candidate["timeframe"]
    pairs = candidate["pairs"] or discover_local_pairs(timeframe)
    panel_result = build_derivatives_feature_panel(pairs=pairs, timeframe=timeframe)
    panel = panel_result.rows.dropna(subset=["close", "rsi14", "volume_ratio", "atr_pct"]).copy()
    if panel.empty:
        return (
            {
                "candidateId": candidate_id,
                "timeframe": timeframe,
                "status": "blocked_no_panel_rows",
                "localPaperSandboxApproved": False,
                "localPaperSandboxFailReasons": ["no_panel_rows"],
            },
            [],
        )

    events = build_labeled_events(panel, candidate["barrierConfig"])
    fixed_rule_events = _filter_candidate_events(events, candidate["columns"], candidate["values"])
    discovery_events, confirmation_events = _split_events(fixed_rule_events, confirmation_fraction)
    full_metrics = evaluate_trades(fixed_rule_events)
    discovery_metrics = evaluate_trades(discovery_events)
    confirmation_metrics = evaluate_trades(confirmation_events)
    approved, fail_reasons = _evaluate_paper_sandbox_gate(confirmation_metrics, LOCAL_PAPER_SANDBOX_GATE)
    signal_log = _signal_log_rows(candidate_id, confirmation_events)

    return (
        {
            "candidateId": candidate_id,
            "timeframe": timeframe,
            "status": "completed",
            "sourceReport": candidate["sourceReport"],
            "columns": candidate["columns"],
            "values": candidate["values"],
            "barrierConfig": asdict(candidate["barrierConfig"]),
            "sourceFullSampleMetrics": candidate["sourceFullSampleMetrics"],
            "sourceHoldoutMetrics": candidate["sourceHoldoutMetrics"],
            "replayedFullSampleMetrics": full_metrics,
            "discoveryMetrics": discovery_metrics,
            "confirmationMetrics": confirmation_metrics,
            "byPairConfirmation": _summarize_by(confirmation_events, "pair"),
            "bySetupConfirmation": _summarize_by(confirmation_events, "setupName"),
            "monthlyConfirmation": _monthly_breakdown(confirmation_events),
            "confirmationTradeCount": int(len(confirmation_events)),
            "localPaperSandboxApproved": approved,
            "localPaperSandboxFailReasons": fail_reasons,
            "dataSummary": {
                "panelRows": int(len(panel)),
                "eventRows": int(len(events)),
                "fixedRuleEventRows": int(len(fixed_rule_events)),
                "loadedPairs": panel_result.loaded_pairs,
                "missingPairs": panel_result.missing_pairs,
                "missingOptionalSources": panel_result.missing_optional_sources,
                "openInterestStatus": "unavailable_not_fabricated",
            },
            "riskNotes": [
                "Local paper sandbox means local simulated observation only.",
                "This is not Freqtrade exchange dry-run approval.",
                "This is not live trading approval.",
                "The candidate originated from deterministic historical mining and must be monitored for overfit decay.",
                "No API key, account data, positions, orders, or exchange private endpoint is used.",
            ],
        },
        signal_log,
    )


def run_forward_confirmation(
    input_1h: Path = DEFAULT_INPUT_1H,
    input_4h: Path = DEFAULT_INPUT_4H,
    confirmation_fraction: float = 0.30,
) -> dict[str, Any]:
    candidates = []
    for candidate_id, path in [("v13_5_1_1h_short_reversal_bull_relative_return", input_1h), ("v13_5_1_4h_bear_regime_bollinger_reversal", input_4h)]:
        candidate = _candidate_from_report(path)
        if candidate is not None:
            candidates.append((candidate_id, candidate))

    confirmations = []
    signal_log: list[dict[str, Any]] = []
    for candidate_id, candidate in candidates:
        confirmation, rows = _build_candidate_confirmation(candidate_id, candidate, confirmation_fraction)
        confirmations.append(confirmation)
        signal_log.extend(rows)

    local_paper_candidates = [row for row in confirmations if row.get("localPaperSandboxApproved")]
    best = sorted(
        confirmations,
        key=lambda row: (
            1 if row.get("localPaperSandboxApproved") else 0,
            (row.get("confirmationMetrics") or {}).get("profitFactor") or 0,
            (row.get("confirmationMetrics") or {}).get("winRatePct") or 0,
            (row.get("confirmationMetrics") or {}).get("rewardRiskRatio") or 0,
            (row.get("confirmationMetrics") or {}).get("tradeCount") or 0,
        ),
        reverse=True,
    )
    best_candidate = best[0] if best else None

    return {
        "reportId": REPORT_ID,
        "version": VERSION,
        "status": "completed" if confirmations else "blocked_no_candidates",
        "isMock": False,
        "generatedAt": utc_now(),
        "objective": {
            "mode": "forward_confirmation_and_local_paper_sandbox_gate",
            "confirmationFraction": confirmation_fraction,
            "localPaperSandboxGate": LOCAL_PAPER_SANDBOX_GATE.to_dict(),
            "paperDefinition": "Local paper sandbox is local simulated observation only; it is not exchange dry-run.",
        },
        "candidateConfirmations": confirmations,
        "bestCandidate": best_candidate,
        "decision": {
            "localPaperSandboxApproved": bool(local_paper_candidates),
            "localPaperSandboxCandidateIds": [row["candidateId"] for row in local_paper_candidates],
            "exchangeDryRunApproved": False,
            "liveTradingApproved": False,
            "reason": (
                "local_paper_sandbox_candidate_confirmed"
                if local_paper_candidates
                else "no_candidate_passed_local_paper_sandbox_confirmation_gate"
            ),
        },
        "nextStep": (
            "Start local paper sandbox logging for the approved candidate only. Keep exchange Dry-run disabled."
            if local_paper_candidates
            else "Collect more forward data or refine features before local paper sandbox."
        ),
        "signalLogPath": str(DEFAULT_OUTPUT_SIGNALS) if signal_log else None,
        "safetyBoundary": {
            "usesPublicLocalDataOnly": True,
            "usesApiKey": False,
            "tradeApiUsed": False,
            "withdrawApiUsed": False,
            "readsRealAccount": False,
            "readsRealPositions": False,
            "createsOrders": False,
            "autoTrading": False,
            "freqtradeDryRunApproved": False,
            "exchangeDryRunApproved": False,
            "liveTradingApproved": False,
        },
        "_signalLog": signal_log,
    }


def write_summary(report: dict[str, Any], path: Path) -> None:
    decision = report["decision"]
    best = report.get("bestCandidate") or {}
    metrics = best.get("confirmationMetrics") or {}
    lines = [
        "# V13.5.2 Forward Confirmation and Local Paper Sandbox Report",
        "",
        "This report is research-only. Local paper sandbox means local simulated observation only.",
        "It does not approve exchange Dry-run, API keys, account reads, orders, or live trading.",
        "",
        "## Decision",
        "",
        f"- Local paper sandbox approved: `{decision['localPaperSandboxApproved']}`",
        f"- Local paper candidate IDs: `{', '.join(decision['localPaperSandboxCandidateIds']) or 'none'}`",
        f"- Exchange Dry-run approved: `{decision['exchangeDryRunApproved']}`",
        f"- Live trading approved: `{decision['liveTradingApproved']}`",
        f"- Reason: `{decision['reason']}`",
        "",
        "## Best Candidate",
        "",
        f"- Candidate ID: `{best.get('candidateId')}`",
        f"- Timeframe: `{best.get('timeframe')}`",
        f"- Columns: `{', '.join(best.get('columns', [])) if best else 'none'}`",
        f"- Values: `{', '.join(best.get('values', [])) if best else 'none'}`",
        f"- Confirmation trades: `{metrics.get('tradeCount')}`",
        f"- Confirmation win rate: `{metrics.get('winRatePct')}`",
        f"- Confirmation reward/risk: `{metrics.get('rewardRiskRatio')}`",
        f"- Confirmation profit factor: `{metrics.get('profitFactor')}`",
        f"- Confirmation total return: `{metrics.get('totalReturnPct')}`",
        f"- Confirmation max drawdown: `{metrics.get('maxDrawdownPct')}`",
        f"- Local paper sandbox fail reasons: `{', '.join(best.get('localPaperSandboxFailReasons', [])) if best else 'none'}`",
        "",
        "## Candidate Confirmations",
        "",
    ]
    for item in report.get("candidateConfirmations", []):
        item_metrics = item.get("confirmationMetrics") or {}
        lines.extend(
            [
                f"### {item.get('candidateId')}",
                "",
                f"- Approved: `{item.get('localPaperSandboxApproved')}`",
                f"- Trades: `{item_metrics.get('tradeCount')}`",
                f"- Win rate: `{item_metrics.get('winRatePct')}`",
                f"- Reward/risk: `{item_metrics.get('rewardRiskRatio')}`",
                f"- Profit factor: `{item_metrics.get('profitFactor')}`",
                f"- Max drawdown: `{item_metrics.get('maxDrawdownPct')}`",
                f"- Fail reasons: `{', '.join(item.get('localPaperSandboxFailReasons', [])) or 'none'}`",
                "",
            ]
        )
    lines.extend(
        [
            "## Next Step",
            "",
            f"- {report.get('nextStep')}",
            "",
            "## Safety Boundary",
            "",
            "- No Trade API.",
            "- No Withdraw API.",
            "- No API key storage.",
            "- No real account reads.",
            "- No real position reads.",
            "- No real orders.",
            "- No automatic trading.",
            "- Exchange Dry-run remains disabled.",
            "",
        ]
    )
    write_text(path, "\n".join(lines))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-1h", default=str(DEFAULT_INPUT_1H))
    parser.add_argument("--input-4h", default=str(DEFAULT_INPUT_4H))
    parser.add_argument("--confirmation-fraction", type=float, default=0.30)
    parser.add_argument("--output-report", default=str(DEFAULT_OUTPUT_REPORT))
    parser.add_argument("--output-summary", default=str(DEFAULT_OUTPUT_SUMMARY))
    parser.add_argument("--output-signals", default=str(DEFAULT_OUTPUT_SIGNALS))
    args = parser.parse_args()

    report = run_forward_confirmation(
        input_1h=Path(args.input_1h),
        input_4h=Path(args.input_4h),
        confirmation_fraction=args.confirmation_fraction,
    )
    signal_log = report.pop("_signalLog", [])
    output_report = Path(args.output_report)
    output_summary = Path(args.output_summary)
    output_signals = Path(args.output_signals)
    if signal_log:
        write_json(output_signals, signal_log)
        report["signalLogPath"] = str(output_signals)
    write_json(output_report, _json_ready(report))
    write_summary(report, output_summary)
    print(f"Wrote {output_report}")
    print(f"Wrote {output_summary}")
    if signal_log:
        print(f"Wrote {output_signals}")
    print(f"decision={report['decision']}")


if __name__ == "__main__":
    main()
