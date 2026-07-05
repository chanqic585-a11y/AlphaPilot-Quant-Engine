"""Generate V13.5.20 exit-aware loss cooldown report.

The report evaluates portfolio-level loss cooldown rules that only start after
the historical trade exit time is known. This avoids future leakage while
keeping the active entry rules and 2R target unchanged.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from alphapilot.paper_sandbox.risk_normalized_replay import (
    ExitAwareLossPolicy,
    evaluate_exit_aware_loss_policies,
    prepare_signal_frame,
)
from alphapilot.reports.generate_v13_5_derivatives_ml_strategy_report import _json_ready, write_json, write_text


VERSION = "V13.5.20"
REPORT_ID = "v13_5_20_exit_aware_loss_cooldown_report"
DEFAULT_INPUT_SIGNALS = Path("reports/v13_5_18_non_okx_expansion_signal_log.json")
DEFAULT_OUTPUT_REPORT = Path("reports/v13_5_20_exit_aware_loss_cooldown_report.json")
DEFAULT_OUTPUT_SUMMARY = Path("reports/v13_5_20_exit_aware_loss_cooldown_summary.md")
DEFAULT_OUTPUT_SELECTED = Path("reports/v13_5_20_best_exit_aware_policy_selected_signals.json")


DEFAULT_POLICIES = [
    ExitAwareLossPolicy(
        "pair_loss_exit_3d",
        "After a selected trade closes at a loss, pause that pair for three days.",
        pair_loss_cooldown_days=3,
    ),
    ExitAwareLossPolicy(
        "pair_loss_exit_5d",
        "After a selected trade closes at a loss, pause that pair for five days.",
        pair_loss_cooldown_days=5,
    ),
    ExitAwareLossPolicy(
        "pair_loss_exit_7d",
        "After a selected trade closes at a loss, pause that pair for seven days.",
        pair_loss_cooldown_days=7,
    ),
    ExitAwareLossPolicy(
        "pair_loss_exit_10d",
        "After a selected trade closes at a loss, pause that pair for ten days.",
        pair_loss_cooldown_days=10,
    ),
    ExitAwareLossPolicy(
        "pair_loss_exit_14d",
        "After a selected trade closes at a loss, pause that pair for fourteen days.",
        pair_loss_cooldown_days=14,
    ),
    ExitAwareLossPolicy(
        "pair_loss_exit_21d",
        "After a selected trade closes at a loss, pause that pair for twenty-one days.",
        pair_loss_cooldown_days=21,
    ),
    ExitAwareLossPolicy(
        "global_loss_exit_pause_8h",
        "After any selected trade closes at a loss, pause all new selections for eight hours.",
        global_loss_pause_hours=8,
    ),
    ExitAwareLossPolicy(
        "global_loss_exit_pause_24h",
        "After any selected trade closes at a loss, pause all new selections for twenty-four hours.",
        global_loss_pause_hours=24,
    ),
    ExitAwareLossPolicy(
        "global_loss_exit_pause_48h",
        "After any selected trade closes at a loss, pause all new selections for forty-eight hours.",
        global_loss_pause_hours=48,
    ),
]


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _gate(metrics: dict[str, Any]) -> dict[str, Any]:
    checks = {
        "minTradeCount300": (metrics.get("tradeCount") or 0) >= 300,
        "minUniqueExchanges3": (metrics.get("uniqueExchanges") or 0) >= 3,
        "minUniquePairs10": (metrics.get("uniquePairs") or 0) >= 10,
        "minProfitFactor1_5": (metrics.get("profitFactor") or 0) >= 1.5,
        "minRewardRisk1_8": (metrics.get("rewardRiskRatio") or 0) >= 1.8,
        "maxDrawdown20R": (metrics.get("maxDrawdownR") or 9999) <= 20,
        "maxConsecutiveLosses12": (metrics.get("maxConsecutiveLosses") or 9999) <= 12,
    }
    return {
        "checks": checks,
        "passed": all(checks.values()),
        "meaning": "Research threshold for local paper refresh review only, not exchange Dry-run approval.",
    }


def _score(metrics: dict[str, Any]) -> float:
    trade_count = min(metrics.get("tradeCount") or 0, 500) / 500
    profit_factor = min(metrics.get("profitFactor") or 0, 2.5) / 2.5
    reward_risk = min(metrics.get("rewardRiskRatio") or 0, 2.5) / 2.5
    drawdown_penalty = min(metrics.get("maxDrawdownR") or 100, 60) / 60
    consecutive_penalty = min(metrics.get("maxConsecutiveLosses") or 20, 20) / 20
    exchange_count = min(metrics.get("uniqueExchanges") or 0, 3) / 3
    return round(
        trade_count * 0.15
        + profit_factor * 0.25
        + reward_risk * 0.25
        + exchange_count * 0.15
        - drawdown_penalty * 0.15
        - consecutive_penalty * 0.05,
        6,
    )


def _policy_rows(policy_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in policy_results:
        metrics = item["metrics"]
        gate = _gate(metrics)
        rows.append(
            {
                "policyId": item["policyId"],
                "description": item["description"],
                "metrics": metrics,
                "byExchange": item["byExchange"],
                "gate": gate,
                "score": _score(metrics),
                "noFutureLeakageRule": "Loss cooldown starts after exitDate, never at entryDate.",
            }
        )
    return sorted(rows, key=lambda row: (row["gate"]["passed"], row["score"]), reverse=True)


def _to_selected_rows(frame: pd.DataFrame, policy_id: str | None) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    rows: list[dict[str, Any]] = []
    for _, row in frame.sort_values(["entryDate", "exchange", "pair"]).iterrows():
        payload = row.to_dict()
        payload["selectedPolicyId"] = policy_id
        payload["source"] = "v13_5_20_exit_aware_loss_cooldown_selected_signal"
        payload["portfolioReplayOnly"] = True
        payload["orderCreation"] = False
        rows.append(payload)
    return _json_ready(rows)


def _summary_markdown(report: dict[str, Any]) -> str:
    best = report["bestPolicy"]
    metrics = best["metrics"]
    decision = report["decision"]
    lines = [
        "# AlphaPilot V13.5.20 Exit-Aware Loss Cooldown",
        "",
        "This report evaluates loss cooldown policies that only activate after a historical selected trade closes.",
        "",
        "## Best Policy",
        "",
        f"- policyId: {best['policyId']}",
        f"- description: {best['description']}",
        f"- tradeCount: {metrics.get('tradeCount')}",
        f"- winRatePct: {metrics.get('winRatePct')}",
        f"- profitFactor: {metrics.get('profitFactor')}",
        f"- rewardRiskRatio: {metrics.get('rewardRiskRatio')}",
        f"- totalR: {metrics.get('totalR')}",
        f"- maxDrawdownR: {metrics.get('maxDrawdownR')}",
        f"- maxConsecutiveLosses: {metrics.get('maxConsecutiveLosses')}",
        f"- gatePassed: {best['gate']['passed']}",
        "",
        "## Policy Table",
        "",
    ]
    for row in report["policyResults"]:
        metric = row["metrics"]
        lines.append(
            f"- {row['policyId']}: trades={metric.get('tradeCount')}, winRate={metric.get('winRatePct')}, "
            f"pf={metric.get('profitFactor')}, rr={metric.get('rewardRiskRatio')}, "
            f"maxDDR={metric.get('maxDrawdownR')}, maxCL={metric.get('maxConsecutiveLosses')}, "
            f"passed={row['gate']['passed']}"
        )
    lines.extend(
        [
            "",
            "## Decision",
            "",
            f"- readyForLocalPaperRefreshReview: {decision['readyForLocalPaperRefreshReview']}",
            f"- readyForExchangeDryRunReview: {decision['readyForExchangeDryRunReview']}",
            f"- nextAction: {decision['nextAction']}",
            "",
            "## No-Lookahead Rule",
            "",
            "- Loss cooldown is triggered by `exitDate` only after the selected historical trade is closed.",
            "- Entry rules and the 2R target are unchanged.",
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
            "- No exchange Dry-run approval.",
            "- No live-trading approval.",
        ]
    )
    return "\n".join(lines) + "\n"


def generate_report(args: argparse.Namespace) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    raw_signals = json.loads(args.input_signals.read_text(encoding="utf-8"))
    signal_frame = prepare_signal_frame(raw_signals)
    policy_results = evaluate_exit_aware_loss_policies(signal_frame, DEFAULT_POLICIES)
    policy_rows = _policy_rows(policy_results)
    best = policy_rows[0] if policy_rows else {
        "policyId": None,
        "description": None,
        "metrics": {},
        "byExchange": [],
        "gate": {"passed": False, "checks": {}},
        "score": None,
    }
    best_result = next((item for item in policy_results if item["policyId"] == best["policyId"]), None)
    selected_signals = _to_selected_rows(best_result["selectedSignals"], best["policyId"]) if best_result else []
    ready_for_local_paper = bool(best["gate"]["passed"])
    report = {
        "version": VERSION,
        "reportId": REPORT_ID,
        "generatedAt": utc_now(),
        "inputSignals": str(args.input_signals),
        "inputSignalCount": int(len(signal_frame)),
        "riskUnit": "1R per selected historical signal",
        "targetRMultipleUnchanged": 2.0,
        "entryRulesUnchanged": True,
        "noFutureLeakageRule": "Loss cooldown starts only after exitDate is known.",
        "policyResults": policy_rows,
        "bestPolicy": best,
        "decision": {
            "readyForLocalPaperRefreshReview": ready_for_local_paper,
            "readyForExchangeDryRunReview": False,
            "exchangeDryRunApproved": False,
            "liveTradingApproved": False,
            "reason": (
                "Exit-aware portfolio replay passed the local paper refresh gate."
                if ready_for_local_paper
                else "No exit-aware policy passed all local paper refresh gate checks."
            ),
            "nextAction": (
                "prepare_local_paper_refresh_candidate"
                if ready_for_local_paper
                else "continue_portfolio_throttle_research_or_wait_for_forward_readiness"
            ),
        },
        "safety": {
            "tradeApi": False,
            "withdrawApi": False,
            "apiKeyStorage": False,
            "realAccountRead": False,
            "realPositionRead": False,
            "orderCreation": False,
            "automaticTrading": False,
            "exchangeDryRun": False,
            "liveTrading": False,
        },
    }
    return _json_ready(report), selected_signals


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate V13.5.20 exit-aware loss cooldown report.")
    parser.add_argument("--input-signals", type=Path, default=DEFAULT_INPUT_SIGNALS)
    parser.add_argument("--output-report", type=Path, default=DEFAULT_OUTPUT_REPORT)
    parser.add_argument("--output-summary", type=Path, default=DEFAULT_OUTPUT_SUMMARY)
    parser.add_argument("--output-selected", type=Path, default=DEFAULT_OUTPUT_SELECTED)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report, selected_signals = generate_report(args)
    write_json(args.output_report, report)
    write_text(args.output_summary, _summary_markdown(report))
    write_json(args.output_selected, selected_signals)
    print(f"Wrote {args.output_report}")
    print(f"Wrote {args.output_summary}")
    print(f"Wrote {args.output_selected}")
    print(
        "bestPolicy="
        f"{report['bestPolicy']['policyId']} "
        f"gatePassed={report['bestPolicy']['gate']['passed']} "
        f"readyForLocalPaperRefreshReview={report['decision']['readyForLocalPaperRefreshReview']}"
    )


if __name__ == "__main__":
    main()
