"""Generate V13.5.19 risk-normalized portfolio replay report.

The report evaluates fixed portfolio throttles on the V13.5.18 signal log in
R-multiple space. It does not change entry rules, does not change the 2R target,
does not create orders, and does not approve exchange Dry-run.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from alphapilot.paper_sandbox.risk_normalized_replay import evaluate_risk_policies, prepare_signal_frame, replay_policy
from alphapilot.reports.generate_v13_5_derivatives_ml_strategy_report import _json_ready, write_json, write_text


VERSION = "V13.5.19"
REPORT_ID = "v13_5_19_risk_normalized_portfolio_replay_report"
DEFAULT_INPUT_SIGNALS = Path("reports/v13_5_18_non_okx_expansion_signal_log.json")
DEFAULT_OUTPUT_REPORT = Path("reports/v13_5_19_risk_normalized_portfolio_replay_report.json")
DEFAULT_OUTPUT_SUMMARY = Path("reports/v13_5_19_risk_normalized_portfolio_replay_summary.md")
DEFAULT_OUTPUT_SELECTED = Path("reports/v13_5_19_best_policy_selected_signals.json")


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _policy_gate(metrics: dict[str, Any]) -> dict[str, Any]:
    checks = {
        "minTradeCount100": (metrics.get("tradeCount") or 0) >= 100,
        "minUniqueExchanges3": (metrics.get("uniqueExchanges") or 0) >= 3,
        "minUniquePairs10": (metrics.get("uniquePairs") or 0) >= 10,
        "minProfitFactor1_2": (metrics.get("profitFactor") or 0) >= 1.2,
        "minRewardRisk1_8": (metrics.get("rewardRiskRatio") or 0) >= 1.8,
        "maxDrawdown30R": (metrics.get("maxDrawdownR") or 9999) <= 30,
        "maxConsecutiveLosses8": (metrics.get("maxConsecutiveLosses") or 9999) <= 8,
    }
    return {
        "checks": checks,
        "passed": all(checks.values()),
        "meaning": "Research threshold for local paper refresh review only, not exchange Dry-run approval.",
    }


def _policy_score(metrics: dict[str, Any]) -> float:
    trade_count = min(metrics.get("tradeCount") or 0, 200) / 200
    profit_factor = min(metrics.get("profitFactor") or 0, 2.5) / 2.5
    reward_risk = min(metrics.get("rewardRiskRatio") or 0, 2.5) / 2.5
    drawdown_penalty = min(metrics.get("maxDrawdownR") or 100, 60) / 60
    exchange_count = min(metrics.get("uniqueExchanges") or 0, 3) / 3
    return round(trade_count * 0.2 + profit_factor * 0.25 + reward_risk * 0.2 + exchange_count * 0.15 - drawdown_penalty * 0.2, 6)


def _serializable_policy_rows(policy_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in policy_results:
        metrics = item["metrics"]
        gate = _policy_gate(metrics)
        rows.append(
            {
                "policyId": item["policyId"],
                "description": item["description"],
                "metrics": metrics,
                "byExchange": item["byExchange"],
                "gate": gate,
                "score": _policy_score(metrics),
            }
        )
    return sorted(rows, key=lambda row: (row["gate"]["passed"], row["score"]), reverse=True)


def _to_signal_rows(frame: pd.DataFrame) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    rows: list[dict[str, Any]] = []
    for _, row in frame.sort_values(["entryDate", "exchange", "pair"]).iterrows():
        payload = row.to_dict()
        payload["source"] = "v13_5_19_risk_normalized_best_policy_selected_signal"
        payload["portfolioReplayOnly"] = True
        rows.append(payload)
    return _json_ready(rows)


def _summary_markdown(report: dict[str, Any]) -> str:
    best = report["bestPolicy"]
    metrics = best["metrics"]
    gate = best["gate"]
    lines = [
        "# AlphaPilot V13.5.19 Risk-Normalized Portfolio Replay",
        "",
        "This report applies fixed portfolio-level throttles to the V13.5.18 historical signal log in R-multiple space.",
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
        f"- gatePassed: {gate['passed']}",
        "",
        "## Policy Table",
        "",
    ]
    for row in report["policyResults"]:
        metric = row["metrics"]
        lines.append(
            f"- {row['policyId']}: trades={metric.get('tradeCount')}, pf={metric.get('profitFactor')}, "
            f"rr={metric.get('rewardRiskRatio')}, maxDDR={metric.get('maxDrawdownR')}, passed={row['gate']['passed']}"
        )
    lines.extend(
        [
            "",
            "## Decision",
            "",
            f"- readyForLocalPaperRefreshReview: {report['decision']['readyForLocalPaperRefreshReview']}",
            f"- readyForExchangeDryRunReview: {report['decision']['readyForExchangeDryRunReview']}",
            f"- nextAction: {report['decision']['nextAction']}",
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
    signals = json.loads(args.input_signals.read_text(encoding="utf-8"))
    signal_frame = prepare_signal_frame(signals)
    policy_results = evaluate_risk_policies(signal_frame)
    policy_rows = _serializable_policy_rows(policy_results)
    best = policy_rows[0] if policy_rows else {
        "policyId": None,
        "description": None,
        "metrics": {},
        "byExchange": [],
        "gate": {"passed": False, "checks": {}},
        "score": None,
    }
    best_policy_result = next((item for item in policy_results if item["policyId"] == best["policyId"]), None)
    selected_signals = _to_signal_rows(best_policy_result["selectedSignals"]) if best_policy_result else []
    ready_for_local_paper = bool(best["gate"]["passed"])
    report = {
        "version": VERSION,
        "reportId": REPORT_ID,
        "generatedAt": utc_now(),
        "inputSignals": str(args.input_signals),
        "inputSignalCount": int(len(signal_frame)),
        "riskUnit": "1R per selected historical signal",
        "targetRMultipleUnchanged": 2.0,
        "policyResults": policy_rows,
        "bestPolicy": best,
        "decision": {
            "readyForLocalPaperRefreshReview": ready_for_local_paper,
            "readyForExchangeDryRunReview": False,
            "exchangeDryRunApproved": False,
            "liveTradingApproved": False,
            "reason": "Portfolio replay is local historical research only. Exchange Dry-run still requires forward validation, manual review, and explicit approval.",
            "nextAction": "prepare_local_paper_refresh_candidate" if ready_for_local_paper else "tighten_risk_controls_or_wait_for_forward_readiness",
        },
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
    return _json_ready(report), selected_signals


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate V13.5.19 risk-normalized portfolio replay report.")
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
