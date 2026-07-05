"""CLI for V13.4.22 factor evaluation and forward label analysis."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from alphapilot.factors.build_factor_data_panel import DEFAULT_MANUAL_FACTOR_REPORT
from alphapilot.factors.compute_manual_factors import compute_manual_factors
from alphapilot.factors.factor_data_panel import build_factor_data_panel
from alphapilot.factors.factor_evaluation_reporter import write_factor_evaluation_outputs
from alphapilot.factors.factor_evaluator import FactorEvaluationConfig, evaluate_factors
from alphapilot.factors.factor_schema import FactorDataPanelConfig
from alphapilot.factors.forward_label_builder import ForwardLabelConfig, build_forward_labels

REPORT_VERSION = "V13.4.22"
DEFAULT_OUTPUT_REPORT = Path("reports/v13_4_22_factor_evaluation_report.json")
DEFAULT_OUTPUT_SUMMARY = Path("reports/v13_4_22_factor_evaluation_summary.md")
DEFAULT_OUTPUT_CANDIDATES = Path("reports/v13_4_22_factor_candidates.json")


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _parse_int_list(raw: str) -> list[int]:
    values = [int(part.strip()) for part in raw.split(",") if part.strip()]
    if not values:
        raise argparse.ArgumentTypeError("At least one horizon is required.")
    return values


def _parse_pairs(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


def _load_factor_panel(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"factor panel not found: {path.as_posix()}")
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return pd.DataFrame(payload)
    if isinstance(payload, dict):
        if isinstance(payload.get("rows"), list):
            return pd.DataFrame(payload["rows"])
        if isinstance(payload.get("panel"), list):
            return pd.DataFrame(payload["panel"])
    raise ValueError("Unsupported factor panel JSON layout. Expected a list, rows, or panel array.")


def _blocked_report(reason: str, warnings: list[str], args: argparse.Namespace) -> dict[str, Any]:
    return {
        "reportId": "v13_4_22_factor_evaluation_report",
        "version": REPORT_VERSION,
        "status": "blocked_insufficient_factor_panel",
        "blockedReason": reason,
        "factorPanelInputPath": str(args.factor_panel) if args.factor_panel else None,
        "sampleCount": 0,
        "validLabelCount": 0,
        "factorCount": 0,
        "evaluatedFactorCount": 0,
        "horizons": args.horizons,
        "warnings": warnings,
        "dryRunApproved": False,
        "liveTradingApproved": False,
        "nextStepRecommendation": "Rebuild the full V13.4.21 FactorDataPanel from local OHLCV before rerunning V13.4.22 evaluation.",
        "generatedAt": utc_now(),
    }


def _rebuild_factor_panel(args: argparse.Namespace) -> tuple[pd.DataFrame, dict[str, Any]]:
    panel_config = FactorDataPanelConfig(
        timerange=args.timerange,
        timeframe=args.timeframe,
        pairs=_parse_pairs(args.pairs),
        dataPath=args.data_path,
        useDynamicUniverse=bool(args.use_dynamic_universe),
        universeSnapshotsPath=args.universe_snapshots,
        sampleSize=200,
    )
    panel_build = build_factor_data_panel(panel_config)
    factor_result = compute_manual_factors(panel_build.panel)
    build_context = {
        "factorPanelInput": "rebuilt_from_local_public_ohlcv",
        "panelRebuilt": True,
        "timerange": args.timerange,
        "timeframe": args.timeframe,
        "loadedPairs": panel_build.loadReport.loadedPairs,
        "failedPairs": panel_build.loadReport.failedPairs,
        "rowsGenerated": int(len(panel_build.panel)),
        "rowsWithManualFactors": int(len(factor_result.panel)),
        "factorCoverage": factor_result.report.get("factorCoverage", {}),
        "panelWarnings": list(panel_build.warnings),
        "manualFactorWarnings": list(factor_result.report.get("warnings", [])),
        "manualFactorLibraryReportPath": str(DEFAULT_MANUAL_FACTOR_REPORT),
    }
    return factor_result.panel, build_context


def build_evaluation_report(args: argparse.Namespace) -> dict[str, Any]:
    warnings: list[str] = []
    try:
        if args.factor_panel:
            panel = _load_factor_panel(Path(args.factor_panel))
            build_context = {
                "factorPanelInput": str(args.factor_panel),
                "panelRebuilt": False,
                "timerange": args.timerange,
                "timeframe": args.timeframe,
            }
            if len(panel) < 1000:
                warnings.append("Provided factor panel has fewer than 1000 rows and appears to be a sample, not a full evaluation panel.")
                return _blocked_report("provided_factor_panel_too_small", warnings, args)
        else:
            panel, build_context = _rebuild_factor_panel(args)
    except Exception as exc:  # noqa: BLE001 - blocked reports are explicit outputs.
        warnings.append(f"Factor panel loading or rebuild failed: {exc}")
        return _blocked_report("factor_panel_unavailable", warnings, args)

    if panel.empty or len(panel) < 1000:
        warnings.append("Full factor panel was not available. Formal factor evaluation is blocked.")
        return _blocked_report("empty_or_too_small_factor_panel", warnings, args)

    label_config = ForwardLabelConfig(horizons=args.horizons, tpPct=args.tp_pct, slPct=args.sl_pct, timeframe=args.timeframe)
    label_result = build_forward_labels(panel, label_config)
    eval_config = FactorEvaluationConfig(
        horizons=args.horizons,
        quantiles=args.quantiles,
        tpPct=args.tp_pct,
        slPct=args.sl_pct,
        primaryHorizon=12 if 12 in args.horizons else args.horizons[0],
    )
    report = evaluate_factors(label_result.panel, eval_config)
    report.update(
        {
            "factorPanelContext": build_context,
            "labelColumns": label_result.labelColumns,
            "labelCoverage": label_result.horizonCoverage,
            "validLabelCount": label_result.validLabelCount,
            "labelWarnings": label_result.warnings,
            "warnings": warnings + label_result.warnings + list(report.get("warnings", [])),
            "outputReportPath": str(args.output_report),
            "outputSummaryPath": str(args.output_summary),
            "outputCandidatesPath": str(args.output_candidates),
        }
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate V13.4.21 manual factors against V13.4.22 forward labels.")
    parser.add_argument("--factor-panel", default="")
    parser.add_argument("--timerange", default="20260101-")
    parser.add_argument("--timeframe", default="1h")
    parser.add_argument("--pairs", default="")
    parser.add_argument("--data-path", default="user_data/data/okx/futures")
    parser.add_argument("--use-dynamic-universe", action="store_true")
    parser.add_argument("--universe-snapshots", default="reports/v13_4_13_dynamic_universe_snapshots.json")
    parser.add_argument("--horizons", type=_parse_int_list, default=[4, 8, 12, 24])
    parser.add_argument("--tp-pct", type=float, default=0.05)
    parser.add_argument("--sl-pct", type=float, default=0.025)
    parser.add_argument("--quantiles", type=int, default=5)
    parser.add_argument("--output-report", type=Path, default=DEFAULT_OUTPUT_REPORT)
    parser.add_argument("--output-summary", type=Path, default=DEFAULT_OUTPUT_SUMMARY)
    parser.add_argument("--output-candidates", type=Path, default=DEFAULT_OUTPUT_CANDIDATES)
    args = parser.parse_args()

    report = build_evaluation_report(args)
    write_factor_evaluation_outputs(report, args.output_report, args.output_summary, args.output_candidates)
    print(f"Factor evaluation status: {report.get('status')}")
    print(f"Sample count: {report.get('sampleCount')}")
    print(f"Valid label count: {report.get('validLabelCount')}")
    print(f"Evaluated factors: {report.get('evaluatedFactorCount')}")
    print(f"Report: {args.output_report}")
    print(f"Summary: {args.output_summary}")
    print(f"Candidates: {args.output_candidates}")
    if report.get("status") != "success":
        raise SystemExit("Factor evaluation blocked. Do not tag V13.4.22 until full panel evaluation succeeds.")


if __name__ == "__main__":
    main()
