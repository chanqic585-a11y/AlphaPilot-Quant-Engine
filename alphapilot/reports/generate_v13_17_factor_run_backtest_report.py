"""Generate the V13.17 point-in-time FactorRun and research-backtest report."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from alphapilot.data_foundation.checkpoint import write_json_atomic
from alphapilot.evolution.factor_runs.labels import DirectionalLabelConfig
from alphapilot.evolution.factor_runs.materializer import materialize_factor_matrix
from alphapilot.evolution.factor_runs.research_runner import run_factor_research
from alphapilot.evolution.registry.database import connect_registry
from alphapilot.evolution.registry.repositories import RegistryRepository


DEFAULT_SNAPSHOT_ID = "data_snapshot_7a348587674343ecd30d6f6f1138febcea32400448026569738e584e95019e35"


def _git_commit() -> str | None:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None


def _summary(report: dict) -> str:
    lines = [
        "# AlphaPilot V13.17 FactorRun and Backtest Summary",
        "",
        f"- Status: `{report['status']}`",
        f"- DataSnapshot: `{report['dataSnapshotId']}`",
        f"- Matrix rows: `{report['matrix']['rowCount']}`",
        f"- FactorRuns: `{len(report['matrix']['factorRunIds'])}`",
        f"- Experiments: `{len(report['experiments'])}`",
        f"- Models: `{len(report['models'])}`",
        f"- Strategy candidates: `{len(report['strategyCandidates'])}`",
        f"- Formal promotion eligible: `{str(report['formalPromotionEligible']).lower()}`",
        "",
    ]
    for experiment in report["experiments"]:
        selected = experiment["evaluation"]["selectedModelType"]
        oos = experiment["evaluation"]["modelResults"][selected]["strategy"]
        locked = experiment["evaluation"]["lockedTest"]["strategy"]
        lines.extend(
            [
                f"## {experiment['direction'].title()}",
                "",
                f"- Selected model: `{selected}`",
                f"- OOS trades: `{oos['tradeCount']}`",
                f"- OOS win rate: `{oos['winRate']}`",
                f"- OOS average net R: `{oos['averageNetR']}`",
                f"- OOS profit factor: `{oos['profitFactor']}`",
                f"- Locked trades: `{locked['tradeCount']}`",
                f"- Locked average net R: `{locked['averageNetR']}`",
                f"- Blockers: `{', '.join(experiment['blockers'])}`",
                "",
            ]
        )
    lines.extend(
        [
            "The fixed research gate did not pass. The local historical base also has no",
            "authoritative source manifest. No candidate, Demo release, Live release, or",
            "order is fabricated to bypass performance or provenance evidence.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot-id", default=DEFAULT_SNAPSHOT_ID)
    parser.add_argument("--registry", default="data/evolution_registry.sqlite")
    parser.add_argument("--canonical-root", default="data/market/canonical")
    parser.add_argument("--output-root", default="data/market/factor_runs")
    parser.add_argument("--timeframe", default="4h")
    parser.add_argument("--code-commit", default=None)
    parser.add_argument("--report", default="reports/v13_17_factor_run_backtest_report.json")
    parser.add_argument("--summary", default="reports/v13_17_factor_run_backtest_summary.md")
    args = parser.parse_args()
    commit = args.code_commit or _git_commit()
    connection = connect_registry(args.registry)
    try:
        repository = RegistryRepository(connection)
        snapshot = repository.get_data_snapshot(args.snapshot_id)
        if snapshot is None:
            raise ValueError(f"DataSnapshot is not registered: {args.snapshot_id}")
        labels = DirectionalLabelConfig()
        matrix = materialize_factor_matrix(
            snapshot=snapshot,
            repository=repository,
            canonical_root=args.canonical_root,
            output_root=args.output_root,
            timeframe=args.timeframe,
            label_config=labels,
            code_commit=commit,
        )
        report = run_factor_research(
            matrix=matrix,
            repository=repository,
            label_config=labels,
            code_commit=commit,
        )
    finally:
        connection.close()
    write_json_atomic(Path(args.report), report)
    Path(args.summary).write_text(_summary(report), encoding="utf-8", newline="\n")
    print(
        json.dumps(
            {
                "reportId": report["reportId"],
                "version": report["version"],
                "status": report["status"],
                "matrixRows": report["matrix"]["rowCount"],
                "factorRunCount": len(report["matrix"]["factorRunIds"]),
                "experimentCount": len(report["experiments"]),
                "modelCount": len(report["models"]),
                "strategyCandidateCount": len(report["strategyCandidates"]),
                "formalPromotionEligible": report["formalPromotionEligible"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
