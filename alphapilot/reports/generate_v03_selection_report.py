"""Generate V13.4.7 V03 candidate selection report.

This module reads local V13.4.6 research artifacts and writes specification
reports only. It does not implement a Freqtrade strategy, run backtests, enter
Dry-run, call exchange APIs, read accounts, create orders, or auto trade.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from alphapilot.strategy_specs.trend_pullback_1h_v01 import get_trend_pullback_1h_v01_spec

DEFAULT_SOURCE_REVIEW = Path("reports/v13_4_6_strategy_direction_review.json")
DEFAULT_SOURCE_SUMMARY = Path("reports/v13_4_6_strategy_direction_summary.md")
DEFAULT_SOURCE_STATUS = Path("reports/v13_4_6_strategy_status_archive.json")
DEFAULT_OUTPUT_JSON = Path("reports/v13_4_7_v03_selection_report.json")
DEFAULT_OUTPUT_SPEC = Path("reports/v13_4_7_v03_strategy_spec.md")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path, warnings: list[str]) -> dict[str, Any]:
    if not path.exists():
        warnings.append(f"Missing input report: {path}")
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        warnings.append(f"Unable to parse input report {path}: {exc}")
        return {}


def _read_text(path: Path, warnings: list[str]) -> str:
    if not path.exists():
        warnings.append(f"Missing input summary: {path}")
        return "unavailable"
    return path.read_text(encoding="utf-8")


def _find_candidate(review: dict[str, Any], candidate_id: str) -> dict[str, Any]:
    candidates = review.get("v03CandidateDirections")
    if not isinstance(candidates, list):
        return {}
    for candidate in candidates:
        if isinstance(candidate, dict) and candidate.get("candidateId") == candidate_id:
            return candidate
    return {}


def build_selection_report(
    source_review_path: Path = DEFAULT_SOURCE_REVIEW,
    source_summary_path: Path = DEFAULT_SOURCE_SUMMARY,
    source_status_path: Path = DEFAULT_SOURCE_STATUS,
) -> dict[str, Any]:
    warnings: list[str] = []
    review = _read_json(source_review_path, warnings)
    summary_text = _read_text(source_summary_path, warnings)
    status_archive = _read_json(source_status_path, warnings)
    spec = get_trend_pullback_1h_v01_spec()
    v03a = _find_candidate(review, "alpha_volume_rebound_v03a_trend_pullback_continuation")
    v03b = _find_candidate(review, "alpha_volume_rebound_v03b_breakout_retest_confirmation")
    v03c = _find_candidate(review, "alpha_volume_rebound_v03c_high_score_signal_only")
    v03d = _find_candidate(review, "alpha_volume_rebound_v03d_1h_main_timeframe")

    if review.get("strategyFamilyStatus") != "rejected_for_dry_run":
        warnings.append("Source V13.4.6 review is not marked rejected_for_dry_run.")
    if review.get("dryRunApproved") is not False:
        warnings.append("Source V13.4.6 review is not marked dryRunApproved=false.")
    if status_archive.get("familyStatus") != "rejected_for_dry_run":
        warnings.append("Source strategy status archive is not marked rejected_for_dry_run.")
    if "V03A" not in summary_text or "V03D" not in summary_text:
        warnings.append("Source summary does not mention both V03A and V03D.")

    return {
        "reportId": "v13_4_7_v03_selection",
        "sourceReview": str(source_review_path),
        "sourceSummary": str(source_summary_path),
        "sourceStatusArchive": str(source_status_path),
        "selectedDirection": "V03A+D",
        "selectedStrategyId": spec["strategyId"],
        "selectedStrategyName": spec["name"],
        "selectionReasons": [
            "V0.1/V0.2 15m signals were too dense and cost-sensitive in expanded validation.",
            "Raising the primary timeframe to 1h directly addresses noise, fee drag, and slippage sensitivity.",
            "Trend pullback continuation addresses weak-rebound failures by requiring clearer 4h/1h structure.",
            "The selected direction avoids continuing small threshold edits inside the failed 15m rebound framework.",
            "V03A provides the structural logic, while V03D provides the lower-noise timeframe choice.",
        ],
        "sourceCandidateEvidence": {
            "v03a": v03a or "unavailable",
            "v03d": v03d or "unavailable",
        },
        "rejectedAlternatives": [
            {
                "direction": "V03B Breakout Retest Confirmation",
                "status": "second_priority",
                "reason": (
                    "The structure is clear and useful, but it requires more robust support/resistance, "
                    "breakout, and retest detection before first implementation."
                ),
                "futureUse": "Keep as a follow-up candidate if Trend Pullback 1H does not pass quality gates.",
                "sourceCandidate": v03b or "unavailable",
            },
            {
                "direction": "V03C High Score Signal Only",
                "status": "future_enhancement_layer",
                "reason": (
                    "A score model is attractive for low-frequency quality control, but first implementation "
                    "should establish a simpler structural baseline before adding weights."
                ),
                "futureUse": "Use later as a scoring layer on top of V03A/V03B style structures.",
                "sourceCandidate": v03c or "unavailable",
            },
            {
                "direction": "V03D 1h Main Timeframe",
                "status": "merged_into_selected_direction",
                "reason": "V03D is a timeframe/noise reduction decision, not a complete standalone strategy.",
                "futureUse": "Merged into V03A as the primary timeframe for Trend Pullback 1H.",
                "sourceCandidate": v03d or "unavailable",
            },
        ],
        "strategySpec": spec,
        "qualityGate": spec["qualityGate"],
        "v13_4_8_plan": spec["implementationPlan"],
        "dryRunApproved": False,
        "liveTradingApproved": False,
        "implementedStrategyCode": False,
        "backtestExecuted": False,
        "warnings": warnings,
        "generatedAt": _utc_now(),
        "source": "alphapilot_v13_4_7_v03_selection",
    }


def _write_spec_markdown(report: dict[str, Any], path: Path) -> None:
    spec = report["strategySpec"]
    entry_filters = spec["entryRules"]["filters"]
    exit_profiles = spec["exitRules"]["profiles"]
    lines = [
        "# V13.4.7 V03 Strategy Specification",
        "",
        "## Selected Direction",
        "",
        f"- Selected direction: {report['selectedDirection']}",
        f"- Strategy ID: {report['selectedStrategyId']}",
        f"- Strategy name: {report['selectedStrategyName']}",
        f"- Status: {spec['status']}",
        f"- Dry-run approved: {report['dryRunApproved']}",
        "",
        "This is a specification only. It is not a Freqtrade strategy implementation.",
        "",
        "## Selection Reasons",
        "",
    ]
    lines.extend(f"- {item}" for item in report["selectionReasons"])
    lines.extend(
        [
            "",
            "## Market Scope",
            "",
            f"- Exchange: {spec['market']['exchange']}",
            f"- Market type: {spec['market']['marketType']}",
            f"- Universe: {spec['market']['universe']}",
            f"- Direction: {spec['market']['direction']}",
            f"- Primary timeframe: {spec['market']['primaryTimeframe']}",
            f"- Higher timeframe: {spec['market']['higherTimeframe']}",
            f"- BTC filter timeframes: {', '.join(spec['market']['btcFilterTimeframes'])}",
            "",
            "V03 first implementation still uses the fixed Top30 supported pair universe. It does not use a dynamic leaderboard.",
            "",
            "## Entry Rules",
            "",
        ]
    )
    for rule in entry_filters:
        lines.extend(
            [
                f"### {rule['name']}",
                "",
                f"- ID: {rule['id']}",
                f"- Timeframe: {rule['timeframe']}",
                f"- Purpose: {rule['purpose']}",
                "- Candidate rules:",
            ]
        )
        lines.extend(f"  - {item}" for item in rule["candidateRules"])
        if rule.get("implementationStatus"):
            lines.append(f"- Implementation status: {rule['implementationStatus']}")
        if rule.get("futureVariants"):
            lines.append("- Future variants:")
            lines.extend(f"  - {item}" for item in rule["futureVariants"])
        lines.append("")

    lines.extend(["## Exit Profiles", ""])
    for profile in exit_profiles:
        lines.extend(
            [
                f"### {profile['id']}",
                "",
                f"- Status: {profile['status']}",
                f"- Stoploss: {profile['stoploss']}",
                f"- Take profit: {profile['takeProfit']}",
                f"- Time stop: {profile['timeStop']}",
                f"- Momentum exit: {profile['momentumExit']}",
                f"- Reason: {profile['reason']}",
                "",
            ]
        )

    lines.extend(
        [
            "## Position Sizing",
            "",
            f"- Risk per trade: {spec['riskRules']['riskPerTradePct']}%",
            f"- Leverage: {spec['riskRules']['leverage']}",
            f"- Margin mode: {spec['riskRules']['marginMode']}",
            "- Formula:",
        ]
    )
    lines.extend(f"  - {item}" for item in spec["riskRules"]["positionSizingFormula"])
    lines.extend(["", "## Quality Gate", ""])
    lines.extend(f"- {item}" for item in report["qualityGate"]["minimumRequirements"])
    lines.extend(["", "## Rejected Alternatives", ""])
    for item in report["rejectedAlternatives"]:
        lines.extend(
            [
                f"### {item['direction']}",
                "",
                f"- Status: {item['status']}",
                f"- Reason: {item['reason']}",
                f"- Future use: {item['futureUse']}",
                "",
            ]
        )
    lines.extend(["## V13.4.8 Plan", ""])
    lines.extend(f"- {item}" for item in report["v13_4_8_plan"]["steps"])
    lines.extend(
        [
            "",
            "## Safety",
            "",
            "V13.4.7 does not implement strategy code, run backtests, enter Dry-run, use API keys, call Trade API or Withdraw API, read accounts, create orders, or auto trade.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def export_v03_selection_report(output_json: Path, output_spec: Path) -> tuple[Path, Path]:
    report = build_selection_report()
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_spec_markdown(report, output_spec)
    return output_json, output_spec


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate V13.4.7 V03 selection report.")
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-spec", type=Path, default=DEFAULT_OUTPUT_SPEC)
    args = parser.parse_args()

    output_json, output_spec = export_v03_selection_report(args.output_json, args.output_spec)
    print(f"Exported V03 selection report: {output_json}")
    print(f"Exported V03 strategy spec: {output_spec}")


if __name__ == "__main__":
    main()
