"""Generate V13.5.9 Strategy Control Tower report.

The report coordinates existing AlphaPilot research into local-paper-only
strategy states. It does not use API keys, call exchange endpoints, create
orders, or auto trade.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from alphapilot.control_tower.strategy_control_tower import ControlTowerPaths, build_strategy_control_tower
from alphapilot.reports.generate_v13_5_derivatives_ml_strategy_report import _json_ready, write_json, write_text


DEFAULT_OUTPUT_REPORT = Path("reports/v13_5_9_strategy_control_tower_report.json")
DEFAULT_OUTPUT_SUMMARY = Path("reports/v13_5_9_strategy_control_tower_summary.md")
DEFAULT_OUTPUT_ROUTER_INTENTS = Path("reports/v13_5_9_local_paper_router_intents.json")
DEFAULT_OUTPUT_REFERENCE_INDEX = Path("reports/v13_5_9_external_reference_index.json")


def _fmt(value: Any) -> str:
    if value is None:
        return "None"
    return str(value)


def _get(mapping: dict[str, Any], snake_key: str, camel_key: str | None = None) -> Any:
    if snake_key in mapping:
        return mapping.get(snake_key)
    if camel_key and camel_key in mapping:
        return mapping.get(camel_key)
    return None


def build_summary(report: dict[str, Any]) -> str:
    decision = report["decision"]
    lines = [
        "# V13.5.9 Strategy Control Tower Report",
        "",
        "This report coordinates existing research candidates into a local-paper-only control tower.",
        "It does not create exchange orders, use API keys, enter exchange Dry-run, or auto trade.",
        "",
        "## Decision",
        "",
        f"- Control tower computed: `{decision['controlTowerComputed']}`",
        f"- Active local paper strategies: `{decision['activeLocalPaperStrategies']}`",
        f"- Primary active strategy: `{decision['primaryActiveStrategyId']}`",
        f"- Continue local paper monitoring: `{decision['continueLocalPaperMonitoring']}`",
        f"- Paper trial approved: `{decision['paperTrialApproved']}`",
        f"- Exchange Dry-run review ready: `{decision['exchangeDryRunReviewReady']}`",
        f"- Exchange Dry-run approved: `{decision['exchangeDryRunApproved']}`",
        f"- Live trading approved: `{decision['liveTradingApproved']}`",
        f"- Reason: `{decision['reason']}`",
        "",
        "## Strategy States",
        "",
    ]
    for state in report["strategyStates"]:
        metrics = state.get("metrics") or {}
        strategy_id = _get(state, "strategy_id", "strategyId")
        candidate_pool_id = _get(state, "candidate_pool_id", "candidatePoolId")
        route_action = _get(state, "route_action", "routeAction")
        lines.extend(
            [
                f"- `{strategy_id}`",
                f"  - stage: `{state['stage']}`",
                f"  - routeAction: `{route_action}`",
                f"  - pool: `{candidate_pool_id}`",
                f"  - winRate: `{_fmt(metrics.get('winRatePct'))}`",
                f"  - rewardRisk: `{_fmt(metrics.get('rewardRiskRatio'))}`",
                f"  - profitFactor: `{_fmt(metrics.get('profitFactor'))}`",
                f"  - maxDrawdown: `{_fmt(metrics.get('maxDrawdownPct'))}`",
                f"  - warnings: `{', '.join(state.get('warnings') or []) or 'none'}`",
                f"  - blockers: `{', '.join(state.get('blockers') or []) or 'none'}`",
            ]
        )
    lines.extend(
        [
            "",
            "## Local Paper Router Intents",
            "",
        ]
    )
    for intent in report["localPaperRouterIntents"]:
        lines.extend(
            [
                f"- `{intent['intentId']}`: strategy=`{intent['strategyId']}`, action=`{intent['routeAction']}`, isOrder=`{intent['isOrder']}`",
            ]
        )
    ledger = report["ledgerSummary"]
    lines.extend(
        [
            "",
            "## Ledger Summary",
            "",
            f"- Trades: `{_fmt(ledger.get('tradeCount'))}`",
            f"- Win rate: `{_fmt(ledger.get('winRatePct'))}`",
            f"- Reward/risk: `{_fmt(ledger.get('rewardRiskRatio'))}`",
            f"- Profit factor: `{_fmt(ledger.get('profitFactor'))}`",
            f"- Total return: `{_fmt(ledger.get('totalReturnPct'))}`",
            f"- Max drawdown: `{_fmt(ledger.get('maxDrawdownPct'))}`",
            "",
            "## External References",
            "",
        ]
    )
    for ref in report["externalReferences"]:
        lines.append(
            f"- `{ref['name']}`: url=`{ref['url']}`, license=`{ref['license']}`, localReference=`{ref['localReference']}`"
        )
    lines.extend(
        [
            "",
            "## Recommendations",
            "",
        ]
    )
    for item in report["recommendations"]:
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## Safety Boundary",
            "",
            "- Local paper only.",
            "- No Trade API.",
            "- No Withdraw API.",
            "- No API key storage.",
            "- No real account reads.",
            "- No real position reads.",
            "- No real orders.",
            "- No emergency close implementation.",
            "- No testnet execution implementation.",
            "- No automatic trading.",
        ]
    )
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate V13.5.9 strategy control tower report.")
    parser.add_argument("--v13-5-7-report", default="reports/v13_5_7_external_alpha_overlay_report.json")
    parser.add_argument("--v13-5-8-report", default="reports/v13_5_8_adaptive_ml_factor_report.json")
    parser.add_argument("--v13-5-3-ledger", default="reports/v13_5_3_local_paper_sandbox_ledger.json")
    parser.add_argument("--v13-5-4-monitoring", default="reports/v13_5_4_local_paper_monitoring_report.json")
    parser.add_argument("--output-report", default=str(DEFAULT_OUTPUT_REPORT))
    parser.add_argument("--output-summary", default=str(DEFAULT_OUTPUT_SUMMARY))
    parser.add_argument("--output-router-intents", default=str(DEFAULT_OUTPUT_ROUTER_INTENTS))
    parser.add_argument("--output-reference-index", default=str(DEFAULT_OUTPUT_REFERENCE_INDEX))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    paths = ControlTowerPaths(
        v13_5_7_report=Path(args.v13_5_7_report),
        v13_5_8_report=Path(args.v13_5_8_report),
        v13_5_3_ledger=Path(args.v13_5_3_ledger),
        v13_5_4_monitoring=Path(args.v13_5_4_monitoring),
    )
    report = build_strategy_control_tower(paths)
    write_json(Path(args.output_report), _json_ready(report))
    write_text(Path(args.output_summary), build_summary(report))
    write_json(Path(args.output_router_intents), _json_ready(report["localPaperRouterIntents"]))
    write_json(Path(args.output_reference_index), _json_ready(report["externalReferences"]))


if __name__ == "__main__":
    main()
