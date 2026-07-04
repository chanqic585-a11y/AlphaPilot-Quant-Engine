"""CLI for V13.4.14 probability score dataset and label builder."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from alphapilot.probability.label_builder import build_probability_samples, no_lookahead_rules, utc_now
from alphapilot.probability.probability_schema import ProbabilityDatasetConfig, ProbabilityDatasetReport
from alphapilot.probability.probability_score_table import (
    build_probability_score_table,
    insufficient_sample_buckets,
    summarize_probability_gates,
    top_negative_buckets,
    top_positive_buckets,
)

REPORT_ID = "v13_4_14_probability_dataset_report"
REPORT_VERSION = "V13.4.14"

DEFAULT_UNIVERSE_SNAPSHOTS = Path("reports/v13_4_13_dynamic_universe_snapshots.json")
DEFAULT_OUTPUT_REPORT = Path("reports/v13_4_14_probability_dataset_report.json")
DEFAULT_OUTPUT_SCORE_TABLE = Path("reports/v13_4_14_probability_score_table.json")
DEFAULT_OUTPUT_SUMMARY = Path("reports/v13_4_14_probability_dataset_summary.md")
DEFAULT_OUTPUT_SAMPLE_DATASET = Path("reports/v13_4_14_probability_sample_dataset.json")


def _parse_windows(raw: str) -> list[int]:
    windows = [int(part.strip()) for part in raw.split(",") if part.strip()]
    if not windows:
        raise ValueError("At least one window is required.")
    return sorted(set(windows))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_summary(report: dict[str, Any], score_table: list[dict[str, Any]], sample_dataset_path: Path, path: Path) -> None:
    lines = [
        "# V13.4.14 Probability Score Dataset Summary",
        "",
        "## Build Status",
        "",
        f"- status: {report['status']}",
        f"- inputUniverseSnapshots: {report['inputUniverseSnapshots']}",
        f"- snapshotCount: {report['snapshotCount']}",
        f"- sampleCount: {report['sampleCount']}",
        f"- labeledSampleCount: {report['labeledSampleCount']}",
        f"- insufficientDataCount: {report['insufficientDataCount']}",
        f"- windows: {', '.join(str(item) for item in report['windows'])}",
        f"- primaryWindow: {report['primaryWindow']}",
        f"- TP: {report['tpPct']}",
        f"- SL: {report['slPct']}",
        "",
        "## Probability Gate Summary",
        "",
    ]
    for key, value in report["probabilityGateSummary"].items():
        if isinstance(value, dict):
            lines.append(f"- {key}:")
            lines.extend(f"  - {inner_key}: {inner_value}" for inner_key, inner_value in value.items())
        else:
            lines.append(f"- {key}: {value}")

    lines.extend(["", "## Top Positive Buckets", ""])
    if report["topPositiveBuckets"]:
        for row in report["topPositiveBuckets"][:10]:
            lines.append(
                f"- {row['bucketId']}: samples={row['sampleCount']}, "
                f"tpProb={row['hitTpBeforeSlProbability']}, pf={row['profitFactor']}, expectancy={row['expectancy']}"
            )
    else:
        lines.append("- none")

    lines.extend(["", "## Top Negative Buckets", ""])
    if report["topNegativeBuckets"]:
        for row in report["topNegativeBuckets"][:10]:
            lines.append(
                f"- {row['bucketId']}: samples={row['sampleCount']}, "
                f"tpProb={row['hitTpBeforeSlProbability']}, pf={row['profitFactor']}, expectancy={row['expectancy']}"
            )
    else:
        lines.append("- none")

    lines.extend(["", "## Insufficient Sample Buckets", ""])
    if report["insufficientSampleBuckets"]:
        for row in report["insufficientSampleBuckets"][:10]:
            lines.append(f"- {row['bucketId']}: samples={row['sampleCount']}")
    else:
        lines.append("- none")

    lines.extend(
        [
            "",
            "## No-Lookahead Rules",
            "",
        ]
    )
    lines.extend(f"- {rule}" for rule in report["noLookaheadRules"])

    lines.extend(
        [
            "",
            "## Outputs",
            "",
            f"- report: {DEFAULT_OUTPUT_REPORT}",
            f"- probabilityScoreTable: {report['scoreTablePath']}",
            f"- sampleDataset: {sample_dataset_path}",
            f"- bucketRows: {len(score_table)}",
            "",
            "## Warnings",
            "",
        ]
    )
    if report["warnings"]:
        lines.extend(f"- {warning}" for warning in report["warnings"])
    else:
        lines.append("- none")

    lines.extend(
        [
            "",
            "## Safety",
            "",
            "V13.4.14 reads local public OHLCV and historical universe snapshots only. It does not implement a strategy, run a backtest, enter Dry-run, use API keys, call Trade API or Withdraw API, read accounts, read positions, create orders, or auto trade.",
            "",
            f"Next step: {report['nextStepRecommendation']}",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def build_outputs(config: ProbabilityDatasetConfig, output_score_table: Path) -> tuple[ProbabilityDatasetReport, list[dict[str, Any]], list[dict[str, Any]]]:
    dataset = build_probability_samples(config)
    score_rows = build_probability_score_table(dataset.samples, config.primaryWindow, config.minBucketSamples)
    score_table = [row.to_dict() for row in score_rows]
    gate_summary = summarize_probability_gates(score_rows)
    gate_summary["minimumSampleThreshold"] = config.minBucketSamples
    report = ProbabilityDatasetReport(
        reportId=REPORT_ID,
        version=REPORT_VERSION,
        status="success" if dataset.samples else "blocked_no_labeled_samples",
        config=config,
        inputUniverseSnapshots=config.universeSnapshotsPath,
        snapshotCount=dataset.snapshotCount,
        sampleCount=len(dataset.samples),
        labeledSampleCount=sum(1 for sample in dataset.samples if str(config.primaryWindow) in sample.labels),
        insufficientDataCount=dataset.insufficientDataCount,
        windows=config.windows,
        tpPct=config.tpPct,
        slPct=config.slPct,
        primaryWindow=config.primaryWindow,
        scoreTablePath=str(output_score_table),
        sampleDatasetPreview=[sample.to_dict() for sample in dataset.samples[:25]],
        topPositiveBuckets=top_positive_buckets(score_rows),
        topNegativeBuckets=top_negative_buckets(score_rows),
        insufficientSampleBuckets=insufficient_sample_buckets(score_rows),
        probabilityGateSummary=gate_summary,
        noLookaheadRules=no_lookahead_rules(),
        warnings=dataset.warnings,
        generatedAt=utc_now(),
    )
    sample_dataset = [sample.to_dict() for sample in dataset.samples[:100]]
    return report, score_table, sample_dataset


def main() -> None:
    parser = argparse.ArgumentParser(description="Build V13.4.14 probability score dataset artifacts.")
    parser.add_argument("--universe-snapshots", type=Path, default=DEFAULT_UNIVERSE_SNAPSHOTS)
    parser.add_argument("--timerange", default="20260101-")
    parser.add_argument("--timeframe", default="1h")
    parser.add_argument("--tp-pct", type=float, default=0.05)
    parser.add_argument("--sl-pct", type=float, default=0.025)
    parser.add_argument("--windows", default="8,12,24")
    parser.add_argument("--data-path", default="user_data/data/okx/futures")
    parser.add_argument("--output-report", type=Path, default=DEFAULT_OUTPUT_REPORT)
    parser.add_argument("--output-score-table", type=Path, default=DEFAULT_OUTPUT_SCORE_TABLE)
    parser.add_argument("--output-summary", type=Path, default=DEFAULT_OUTPUT_SUMMARY)
    parser.add_argument("--output-sample-dataset", type=Path, default=DEFAULT_OUTPUT_SAMPLE_DATASET)
    args = parser.parse_args()

    windows = _parse_windows(args.windows)
    primary_window = 12 if 12 in windows else windows[0]
    config = ProbabilityDatasetConfig(
        universeSnapshotsPath=str(args.universe_snapshots),
        dataPath=args.data_path,
        timerange=args.timerange,
        timeframe=args.timeframe,
        tpPct=args.tp_pct,
        slPct=args.sl_pct,
        windows=windows,
        primaryWindow=primary_window,
    )
    report, score_table, sample_dataset = build_outputs(config, args.output_score_table)
    _write_json(args.output_score_table, score_table)
    _write_json(args.output_sample_dataset, sample_dataset)
    _write_json(args.output_report, report.to_dict())
    _write_summary(report.to_dict(), score_table, args.output_sample_dataset, args.output_summary)

    print(f"Probability dataset status: {report.status}")
    print(f"Snapshot count: {report.snapshotCount}")
    print(f"Sample count: {report.sampleCount}")
    print(f"Labeled sample count: {report.labeledSampleCount}")
    print(f"Insufficient data count: {report.insufficientDataCount}")
    print(f"Score table: {args.output_score_table}")
    print(f"Sample dataset: {args.output_sample_dataset}")
    print(f"Report: {args.output_report}")
    print(f"Summary: {args.output_summary}")
    if report.status != "success":
        print("No labeled samples were generated. Do not tag V13.4.14 until data availability is fixed.")


if __name__ == "__main__":
    main()
