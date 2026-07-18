"""Run and report the frozen V13.27.1.15 Advisory-R prefilter."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

import pandas as pd

from alphapilot.data_foundation.checkpoint import write_json_atomic
from alphapilot.evolution.registry.hashing import sha256_file

from .candidates import build_candidate_inventory
from .prefilter import (
    evaluate_candidate,
    evaluate_portfolio_candidate,
    route_prefilter_survivors,
)
from .signals import replay_candidate
from .trial_ledger import build_trial_ledger


ROUND_TRIP_COST_RATE = 0.002


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _preregistration(repo_root: Path) -> tuple[Path, dict[str, Any]]:
    paths = sorted(
        (repo_root / "research" / "preregistrations").glob(
            "advisory_r_v15_*_prefilter_v2.json"
        )
    )
    if len(paths) != 1:
        raise RuntimeError("expected exactly one V15 prefilter preregistration")
    return paths[0], _read_json(paths[0])


def _snapshot(repo_root: Path, preregistration: Mapping[str, Any]) -> dict[str, Any]:
    path = (
        repo_root
        / "research"
        / "data_snapshots"
        / f"{preregistration['snapshotId']}.json"
    )
    snapshot = _read_json(path)
    if snapshot["snapshotHash"] != preregistration["snapshotHash"]:
        raise RuntimeError("snapshot hash differs from frozen preregistration")
    return snapshot


def _reference_map(snapshot: Mapping[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    return {
        (str(row["instrumentId"]), str(row["timeframe"])): dict(row)
        for row in snapshot["datasetReferences"]
    }


def _load_frame(data_root: Path, reference: Mapping[str, Any], cutoff: str) -> pd.DataFrame:
    path = data_root / Path(str(reference["path"]))
    if not path.is_file():
        raise FileNotFoundError(path)
    if sha256_file(path) != str(reference["sha256"]):
        raise RuntimeError(f"snapshot dataset hash mismatch: {reference['instrumentId']}")
    frame = pd.read_parquet(path)
    frame["date"] = pd.to_datetime(frame["date"], utc=True)
    frame = frame[frame["date"] <= pd.Timestamp(cutoff)]
    return frame.sort_values("date").drop_duplicates("date", keep="last").reset_index(drop=True)


def _frames_for_timeframe(
    *,
    data_root: Path,
    snapshot: Mapping[str, Any],
    universe: Sequence[str],
    timeframe: str,
) -> tuple[dict[str, pd.DataFrame], list[dict[str, Any]]]:
    references = _reference_map(snapshot)
    cutoff = str(snapshot["commonCutoffByTimeframe"][timeframe])
    frames: dict[str, pd.DataFrame] = {}
    availability: list[dict[str, Any]] = []
    for symbol in universe:
        reference = references.get((symbol, timeframe))
        if reference is None:
            availability.append(
                {"instrumentId": symbol, "timeframe": timeframe, "available": False}
            )
            continue
        frame = _load_frame(data_root, reference, cutoff)
        frames[symbol] = frame
        availability.append(
            {
                "instrumentId": symbol,
                "timeframe": timeframe,
                "available": True,
                "rowCount": len(frame),
                "effectiveBacktestStart": reference["effectiveBacktestStart"],
                "cutoff": cutoff,
                "provider": reference["provider"],
                "sha256": reference["sha256"],
            }
        )
    return frames, availability


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp")
    columns = sorted({str(key) for row in rows for key in row})
    with temporary.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows([{key: row.get(key) for key in columns} for row in rows])
    temporary.replace(path)


def _write_parquet(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp")
    pd.DataFrame([dict(row) for row in rows]).to_parquet(temporary, index=False)
    temporary.replace(path)


def _benchmarks(frames: Mapping[str, Mapping[str, pd.DataFrame]]) -> dict[str, Any]:
    by_timeframe: dict[str, Any] = {}
    for timeframe, timeframe_frames in frames.items():
        returns = {
            symbol: float(frame.iloc[-1]["close"] / frame.iloc[0]["close"] - 1.0)
            for symbol, frame in timeframe_frames.items()
            if len(frame) >= 2
        }
        by_timeframe[timeframe] = {
            "noTradeReturn": 0.0,
            "equalWeightRepresentativeReturn": (
                sum(returns.values()) / len(returns) if returns else None
            ),
            "instrumentReturns": returns,
        }
    return {
        "schemaVersion": "advisory_r_simple_benchmarks_v1",
        "byTimeframe": by_timeframe,
        "note": "Context only; candidate gates use realized cost-net R, not holding return.",
    }


def _summary_markdown(
    preregistration: Mapping[str, Any],
    results: Sequence[Mapping[str, Any]],
    route: Mapping[str, Any],
) -> str:
    policy_counts = Counter(str(row["exitPolicyMode"]) for row in results)
    lines = [
        f"# Advisory-R V15 Prefilter {preregistration['campaignId']}",
        "",
        "## Frozen scope",
        "",
        f"- Candidate count: `{len(results)}`",
        f"- Family count: `{preregistration['familyCount']}`",
        f"- Exit policy modes: `{dict(sorted(policy_counts.items()))}`",
        f"- Target-R gate mode: `{preregistration['targetRGateMode']}`",
        "- Holdout reads: `0`",
        "- Release count: `0`",
        "- ARM: `false`",
        "- Orders: `0`",
        "",
        "## Routing",
        "",
        f"- Formal survivors: `{len(route['formalCandidateIds'])}`",
        f"- Archived or family-deduplicated: `{len(route['archivedCandidateIds'])}`",
        f"- Diagnostic-only: `{len(route['diagnosticCandidateIds'])}`",
        f"- Formal stage allowed: `{str(route['formalStageAllowed']).lower()}`",
    ]
    if route["hardStopReason"]:
        lines.extend([f"- Hard stop: `{route['hardStopReason']}`", "", "No candidate was forced through."])
    lines.extend(["", "No exit policy was changed after results were read."])
    return "\n".join(lines) + "\n"


def _artifact_manifest(root: Path) -> dict[str, Any]:
    artifacts = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name != "artifact_manifest.json":
            artifacts.append(
                {
                    "path": path.relative_to(root).as_posix(),
                    "bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
    return {"schemaVersion": "advisory_r_artifact_manifest_v1", "artifacts": artifacts}


def run_prefilter_campaign(repo_root: Path, data_root: Path) -> Path:
    _, preregistration = _preregistration(repo_root)
    frozen_summaries = [dict(row) for row in preregistration["candidates"]]
    frozen_candidates = build_candidate_inventory()
    projected = [
        {key: candidate[key] for key in summary}
        for candidate, summary in zip(frozen_candidates, frozen_summaries)
    ]
    if projected != frozen_summaries:
        raise RuntimeError("candidate inventory changed after preregistration")
    snapshot = _snapshot(repo_root, preregistration)
    universe = [str(value) for value in preregistration["representativeUniverse"]["instrumentIds"]]
    frames: dict[str, dict[str, pd.DataFrame]] = {}
    availability: list[dict[str, Any]] = []
    for timeframe in ("1h", "4h"):
        frames[timeframe], rows = _frames_for_timeframe(
            data_root=data_root,
            snapshot=snapshot,
            universe=universe,
            timeframe=timeframe,
        )
        availability.extend(rows)

    events_by_candidate: dict[str, list[dict[str, Any]]] = {}
    results: list[dict[str, Any]] = []
    for candidate in frozen_candidates:
        candidate_frames = frames[str(candidate["timeframe"])]
        events = replay_candidate(
            candidate,
            candidate_frames,
            round_trip_cost_rate=ROUND_TRIP_COST_RATE,
        )
        events_by_candidate[str(candidate["candidateId"])] = events
        if candidate["strategyType"] == "portfolio":
            result = evaluate_portfolio_candidate(
                candidate,
                events,
                gates=preregistration["portfolioPrefilterGates"],
            )
        else:
            result = evaluate_candidate(
                candidate,
                events,
                gates=preregistration["prefilterGates"],
            )
        results.append(result)

    route = route_prefilter_survivors(
        results,
        maximum_survivors=int(preregistration["routing"]["maximumSurvivors"]),
    )
    campaign_root = repo_root / "reports" / "advisory_r_campaign" / str(preregistration["campaignId"])
    output = campaign_root / "prefilter"
    output.mkdir(parents=True, exist_ok=True)
    trial_ledger = build_trial_ledger(frozen_candidates)
    trial_rows = list(trial_ledger["trials"])
    all_events = [
        row
        for candidate_id in sorted(events_by_candidate)
        for row in events_by_candidate[candidate_id]
    ]
    novelty_audit = {
        "schemaVersion": "advisory_r_novelty_audit_v1",
        "postResultReplacementAllowed": False,
        "candidates": [
            {
                "candidateId": row["candidateId"],
                "familyId": row["familyId"],
                "originLineage": row["originLineage"],
                "semanticFingerprint": row["semanticFingerprint"],
                "novelTrial": True,
            }
            for row in frozen_candidates
        ],
    }
    archived = [
        {
            "candidateId": row["candidateId"],
            "familyId": row["familyId"],
            "failedGates": row["failedGates"],
            "nextAction": "archive_without_exit_policy_change",
        }
        for row in results
        if row["candidateId"] in route["archivedCandidateIds"]
    ]
    write_json_atomic(output / "strategy_inventory.json", frozen_candidates)
    write_json_atomic(output / "novelty_audit.json", novelty_audit)
    write_json_atomic(output / "trial_ledger.json", trial_ledger)
    _write_csv(output / "trial_ledger.csv", trial_rows)
    write_json_atomic(
        output / "representative_universe.json",
        {
            **preregistration["representativeUniverse"],
            "snapshotId": snapshot["snapshotId"],
            "snapshotHash": snapshot["snapshotHash"],
            "availability": availability,
        },
    )
    write_json_atomic(output / "prefilter_results.json", {"results": results, "route": route})
    write_json_atomic(
        output / "exit_policy_attribution.json",
        {
            "postResultPolicyChanges": 0,
            "candidates": [
                {
                    "candidateId": row["candidateId"],
                    "exitPolicyMode": row["exitPolicyMode"],
                    "exitPolicyHash": row["exitPolicyHash"],
                    "diagnostics": row["exitDiagnostics"],
                }
                for row in results
            ],
        },
    )
    write_json_atomic(output / "simple_benchmarks.json", _benchmarks(frames))
    write_json_atomic(
        output / "prefilter_gate_matrix.json",
        {
            "targetRGateMode": "advisory",
            "minimumTargetR": None,
            "candidates": [
                {
                    "candidateId": row["candidateId"],
                    "passed": row["passed"],
                    "gates": row["gates"],
                }
                for row in results
            ],
        },
    )
    write_json_atomic(output / "archived_prefilter_failures.json", {"failures": archived})
    (output / "prefilter_summary.md").write_text(
        _summary_markdown(preregistration, results, route), encoding="utf-8"
    )
    _write_parquet(output / "candidate_events.parquet", all_events)
    write_json_atomic(campaign_root / "route_decision.json", route)
    write_json_atomic(campaign_root / "artifact_manifest.json", _artifact_manifest(campaign_root))
    return campaign_root


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--data-root", type=Path, required=True)
    args = parser.parse_args()
    result = run_prefilter_campaign(args.repo_root.resolve(), args.data_root.resolve())
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
