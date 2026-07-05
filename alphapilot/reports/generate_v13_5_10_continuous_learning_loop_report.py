"""Generate V13.5.10 continuous learning loop report.

This command prepares local paper outcome samples for future offline research.
It does not retrain models, call exchange APIs, create orders, or auto trade.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from alphapilot.learning_loop.strategy_learning_loop import LearningLoopPaths, build_continuous_learning_loop
from alphapilot.reports.generate_v13_5_derivatives_ml_strategy_report import _json_ready, write_json, write_text


DEFAULT_OUTPUT_REPORT = Path("reports/v13_5_10_continuous_learning_loop_report.json")
DEFAULT_OUTPUT_SUMMARY = Path("reports/v13_5_10_continuous_learning_loop_summary.md")
DEFAULT_OUTPUT_DATASET = Path("reports/v13_5_10_strategy_evolution_dataset.json")
DEFAULT_OUTPUT_STATE = Path("reports/v13_5_10_learning_state.json")


def _fmt(value: Any) -> str:
    if value is None:
        return "None"
    return str(value)


def build_summary(report: dict[str, Any]) -> str:
    state = report["learningState"]
    gate = report["retrainingGate"]
    sample_summary = report["strategyEvolutionDataset"]["sampleSummary"]
    lines = [
        "# V13.5.10 Continuous Learning Loop Report",
        "",
        "This report converts local paper outcomes into strategy evolution samples.",
        "It does not retrain a model, use API keys, call exchange APIs, create orders, or auto trade.",
        "",
        "## Learning State",
        "",
        f"- Learning loop computed: `{state['learningLoopComputed']}`",
        f"- Active strategy: `{state['activeStrategyId']}`",
        f"- Active candidate pool: `{state['activeCandidatePoolId']}`",
        f"- Observer strategies: `{', '.join(state['observerStrategyIds'])}`",
        f"- Strategy evolution dataset updated: `{state['strategyEvolutionDatasetUpdated']}`",
        f"- New local paper samples: `{state['newTrainingSamplesFromPaper']}`",
        f"- Usable local paper samples: `{state['usableTrainingSamplesFromPaper']}`",
        f"- Active strategy samples: `{state['activeStrategySamplesFromPaper']}`",
        f"- Active strategy usable samples: `{state['activeStrategyUsableSamplesFromPaper']}`",
        f"- Ready for retraining: `{state['readyForRetraining']}`",
        f"- Continue local paper monitoring: `{state['continueLocalPaperMonitoring']}`",
        f"- Exchange Dry-run review ready: `{state['exchangeDryRunReviewReady']}`",
        f"- Exchange Dry-run approved: `{state['exchangeDryRunApproved']}`",
        f"- Live trading approved: `{state['liveTradingApproved']}`",
        f"- Reason: `{state['reason']}`",
        "",
        "## Sample Summary",
        "",
        f"- Total samples: `{sample_summary['totalSamples']}`",
        f"- Usable for retraining: `{sample_summary['usableForRetrainingCount']}`",
        f"- Active strategy samples: `{sample_summary['activeStrategySampleCount']}`",
        f"- Active strategy usable samples: `{sample_summary['activeStrategyUsableCount']}`",
        f"- Outcome labels: `{sample_summary['outcomeLabelBreakdown']}`",
        f"- Pair breakdown: `{sample_summary['pairBreakdown']}`",
        f"- Strategy breakdown: `{sample_summary['strategyBreakdown']}`",
        "",
        "## Retraining Gate",
        "",
        f"- Ready: `{gate['readyForRetraining']}`",
        f"- Minimum usable samples: `{gate['minRetrainingSampleCount']}`",
        f"- Usable samples: `{gate['usableSampleCount']}`",
        f"- Active strategy usable samples: `{gate['activeStrategyUsableSampleCount']}`",
        f"- Latest exit time: `{_fmt(gate['latestExitTime'])}`",
        f"- Monitoring health: `{_fmt(gate['monitoringHealth'])}`",
        f"- Fail reasons: `{', '.join(gate['failReasons']) or 'none'}`",
        f"- Warning reasons: `{', '.join(gate['warningReasons']) or 'none'}`",
        f"- Allowed next action: `{gate['allowedNextAction']}`",
        "",
        "## Strategy Roles",
        "",
    ]
    for role in report["strategyRoles"]:
        lines.extend(
            [
                f"- `{role['strategyId']}`",
                f"  - role: `{role['role']}`",
                f"  - candidatePoolId: `{_fmt(role.get('candidatePoolId'))}`",
                f"  - canCreateOrders: `{role['canCreateOrders']}`",
                f"  - canTriggerDryRun: `{role['canTriggerDryRun']}`",
            ]
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
            "- Local paper outcomes only.",
            "- No real trade outcomes are claimed.",
            "- No model retraining is performed by this report.",
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
    parser = argparse.ArgumentParser(description="Generate V13.5.10 continuous learning loop report.")
    parser.add_argument("--control-tower-report", default="reports/v13_5_9_strategy_control_tower_report.json")
    parser.add_argument("--local-paper-ledger", default="reports/v13_5_3_local_paper_sandbox_ledger.json")
    parser.add_argument("--monitoring-report", default="reports/v13_5_4_local_paper_monitoring_report.json")
    parser.add_argument("--adaptive-ml-report", default="reports/v13_5_8_adaptive_ml_factor_report.json")
    parser.add_argument("--strategy-evolution-schema", default="reports/v13_5_8_strategy_evolution_sample_schema.json")
    parser.add_argument("--output-report", default=str(DEFAULT_OUTPUT_REPORT))
    parser.add_argument("--output-summary", default=str(DEFAULT_OUTPUT_SUMMARY))
    parser.add_argument("--output-dataset", default=str(DEFAULT_OUTPUT_DATASET))
    parser.add_argument("--output-state", default=str(DEFAULT_OUTPUT_STATE))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    paths = LearningLoopPaths(
        control_tower_report=Path(args.control_tower_report),
        local_paper_ledger=Path(args.local_paper_ledger),
        monitoring_report=Path(args.monitoring_report),
        adaptive_ml_report=Path(args.adaptive_ml_report),
        strategy_evolution_schema=Path(args.strategy_evolution_schema),
    )
    report = build_continuous_learning_loop(paths)
    write_json(Path(args.output_report), _json_ready(report))
    write_text(Path(args.output_summary), build_summary(report))
    write_json(Path(args.output_dataset), _json_ready(report["strategyEvolutionDataset"]))
    write_json(Path(args.output_state), _json_ready(report["learningState"]))


if __name__ == "__main__":
    main()
