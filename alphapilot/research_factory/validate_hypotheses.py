"""CLI for V13.4.26 factor hypothesis validation.

This command builds research validation statistics only. It does not implement
strategy code, run Freqtrade backtests, enter Dry-run, call exchange APIs, read
accounts, create orders, or auto trade.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from alphapilot.research_factory.hypothesis_validation_dataset import build_validation
from alphapilot.research_factory.hypothesis_validation_schema import HypothesisValidationConfig

DEFAULT_HYPOTHESES = Path("reports/v13_4_25_research_hypotheses.json")
DEFAULT_OUTPUT_REPORT = Path("reports/v13_4_26_hypothesis_validation_report.json")
DEFAULT_OUTPUT_SUMMARY = Path("reports/v13_4_26_hypothesis_validation_summary.md")
DEFAULT_OUTPUT_SAMPLE = Path("reports/v13_4_26_hypothesis_validation_dataset_sample.json")
DEFAULT_OUTPUT_RECOMMENDATIONS = Path("reports/v13_4_26_hypothesis_recommendations.json")


def _parse_int_list(raw: str) -> list[int]:
    values = [int(part.strip()) for part in raw.split(",") if part.strip()]
    if not values:
        raise argparse.ArgumentTypeError("At least one horizon is required.")
    return values


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")


def _summary(report: dict[str, Any]) -> str:
    metrics = report.get("validationMetrics", [])
    metric_lines = "\n".join(
        f"- {item['hypothesisId']} | {item['hypothesisName']} | {item['supportLevel']} | pass={item['conditionPassCount']} | PF={item['profitFactor']} | excessBTC={item['averageExcessReturnVsBTC']}"
        for item in metrics
    )
    return f"""# AlphaPilot V13.4.26 Hypothesis Validation Summary

Status: {report.get("status")}

V13.4.26 validates high-priority V13.4.25 research hypotheses against a rebuilt
FactorDataPanel and forward labels. It is research-only.

No strategy code was written. No Freqtrade backtest was run. No Dry-run or live
trading approval was granted.

## Core Counts

- hypothesisCount: {report.get("hypothesisCount")}
- validatedHypothesisCount: {report.get("validatedHypothesisCount")}
- rejectedHypothesisCount: {report.get("rejectedHypothesisCount")}
- sampleCount: {report.get("sampleCount")}

## Supported / Unsupported

- topSupportedHypotheses: {", ".join(report.get("topSupportedHypotheses", [])) or "none"}
- unsupportedHypotheses: {", ".join(report.get("unsupportedHypotheses", [])) or "none"}
- insufficientSampleHypotheses: {", ".join(report.get("insufficientSampleHypotheses", [])) or "none"}
- hypothesesWithPositiveExcessVsBTC: {", ".join(report.get("hypothesesWithPositiveExcessVsBTC", [])) or "none"}

## Validation Metrics

{metric_lines or "- none"}

## Stability Warnings

{chr(10).join(f"- {item}" for item in report.get("stabilityWarnings", [])) or "- none"}

## Recommendations

{chr(10).join(f"- {item.get('type')}: {item.get('reason')}" for item in report.get("recommendations", [])) or "- none"}

## Next Step

{report.get("nextStep")}

## No-Lookahead Notes

{chr(10).join(f"- {item}" for item in report.get("noLookaheadAssurance", []))}

## Safety Boundary

- dryRunApproved: {report.get("dryRunApproved")}
- liveTradingApproved: {report.get("liveTradingApproved")}
- no strategy implementation
- no backtest execution
- no Dry-run
- no Trade API
- no Withdraw API
- no API key
- no account or position reads
- no order creation
- no auto trading
"""


def run_validation(args: argparse.Namespace) -> dict[str, Any]:
    config = HypothesisValidationConfig(
        hypothesesPath=str(args.hypotheses),
        factorPanelPath=str(args.factor_panel) if args.factor_panel else None,
        timerange=args.timerange,
        timeframe=args.timeframe,
        horizons=args.horizons,
        tpPct=args.tp_pct,
        slPct=args.sl_pct,
        dataPath=args.data_path,
        useDynamicUniverse=bool(args.use_dynamic_universe),
        universeSnapshotsPath=args.universe_snapshots,
    )
    result = build_validation(
        config=config,
        output_report=Path(args.output_report),
        output_summary=Path(args.output_summary),
        output_sample=Path(args.output_sample),
        output_recommendations=Path(args.output_recommendations),
    )
    report_payload = result.report.to_dict()
    _write_json(Path(args.output_report), report_payload)
    _write_text(Path(args.output_summary), _summary(report_payload))
    _write_json(Path(args.output_sample), result.datasetSample)
    _write_json(Path(args.output_recommendations), result.recommendations)
    return report_payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate V13.4.25 research hypotheses against local factor data.")
    parser.add_argument("--hypotheses", type=Path, default=DEFAULT_HYPOTHESES)
    parser.add_argument("--factor-panel", type=Path, default=None)
    parser.add_argument("--timerange", default="20260101-")
    parser.add_argument("--timeframe", default="1h")
    parser.add_argument("--horizons", type=_parse_int_list, default=[4, 8, 12, 24])
    parser.add_argument("--tp-pct", type=float, default=0.05)
    parser.add_argument("--sl-pct", type=float, default=0.025)
    parser.add_argument("--data-path", default="user_data/data/okx/futures")
    parser.add_argument("--use-dynamic-universe", action="store_true")
    parser.add_argument("--universe-snapshots", default="reports/v13_4_13_dynamic_universe_snapshots.json")
    parser.add_argument("--output-report", type=Path, default=DEFAULT_OUTPUT_REPORT)
    parser.add_argument("--output-summary", type=Path, default=DEFAULT_OUTPUT_SUMMARY)
    parser.add_argument("--output-sample", type=Path, default=DEFAULT_OUTPUT_SAMPLE)
    parser.add_argument("--output-recommendations", type=Path, default=DEFAULT_OUTPUT_RECOMMENDATIONS)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    report = run_validation(args)
    print(f"Hypothesis validation status: {report.get('status')}")
    print(f"Sample count: {report.get('sampleCount')}")
    print(f"Validated hypotheses: {report.get('validatedHypothesisCount')}")
    print(f"Top supported: {', '.join(report.get('topSupportedHypotheses', [])) or 'none'}")
    print(f"Report: {args.output_report}")
    print(f"Summary: {args.output_summary}")
    if str(report.get("status")).startswith("blocked"):
        raise SystemExit("Hypothesis validation blocked. Do not tag V13.4.26 until validation succeeds.")


if __name__ == "__main__":
    main()
