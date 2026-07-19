"""Freeze zero-budget V36 TSMOM Formal handoff artifacts.

This stage hashes metadata and registered partitions only. It does not load
Formal market content, claim a Formal run, read results, or create a Release.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from alphapilot.data_foundation.checkpoint import write_json_atomic
from alphapilot.evolution.registry.hashing import sha256_file, stable_hash
from alphapilot.formal_validation.v36_contracts import (
    build_v36_data_snapshot,
    build_v36_preregistration,
    build_v36_split_policy,
)
from alphapilot.standard_replication.tsmom_engine import (
    TSMOM_SYMBOLS,
    build_tsmom_candidate_spec,
)


V36_OHLCV_COLUMN_MAP = {"confirmed": "confirm", "volume": "volCcyQuote"}


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"json_object_required:{path}")
    return value


def _write_once(path: Path, payload: Mapping[str, Any]) -> None:
    expected = dict(payload)
    if path.exists():
        current = _read_json(path)
        if current != expected:
            raise RuntimeError(f"immutable_artifact_conflict:{path.as_posix()}")
        return
    write_json_atomic(path, expected)


def _relative_file(path_value: str, *, data_root: Path) -> tuple[Path, Path]:
    path = Path(path_value).resolve()
    root = data_root.resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    try:
        relative = path.relative_to(root)
    except ValueError as error:
        raise ValueError(f"formal_partition_outside_data_root:{path}") from error
    return path, relative


def _dataset_references(
    candidate: Mapping[str, Any], *, data_root: Path
) -> list[dict[str, Any]]:
    timeframe = str(candidate.get("timeframe") or "")
    references: list[dict[str, Any]] = []
    for raw in dict(candidate.get("ohlcvCoverage") or {}).get("partitions", []):
        if not isinstance(raw, Mapping):
            raise ValueError("ohlcv_partition_reference_invalid")
        path, relative = _relative_file(str(raw.get("path") or ""), data_root=data_root)
        actual_hash = sha256_file(path)
        registered_hash = str(raw.get("sha256") or "")
        if registered_hash and actual_hash != registered_hash:
            raise ValueError(f"ohlcv_partition_hash_mismatch:{raw.get('instrumentId')}")
        references.append(
            {
                "instrumentId": str(raw.get("instrumentId") or ""),
                "timeframe": timeframe,
                "path": relative.as_posix(),
                "sha256": actual_hash,
                "provider": "okx",
                "exchange": "okx",
                "columnMap": dict(V36_OHLCV_COLUMN_MAP),
            }
        )
    if sorted(row["instrumentId"] for row in references) != sorted(TSMOM_SYMBOLS):
        raise ValueError("ohlcv_core_universe_incomplete")
    return sorted(references, key=lambda row: row["instrumentId"])


def _funding_references(*, data_root: Path) -> list[dict[str, Any]]:
    funding_root = (
        data_root
        / "_alphapilot"
        / "canonical"
        / "okx"
        / "swap"
        / "funding"
    )
    references: list[dict[str, Any]] = []
    for symbol in TSMOM_SYMBOLS:
        paths = sorted((funding_root / symbol).rglob("*.parquet"))
        if not paths:
            raise ValueError(f"funding_partition_missing:{symbol}")
        partitions = []
        for path in paths:
            absolute, relative = _relative_file(str(path), data_root=data_root)
            partitions.append(
                {"path": relative.as_posix(), "sha256": sha256_file(absolute)}
            )
        references.append(
            {
                "instrumentId": symbol,
                "provider": "okx",
                "exchange": "okx",
                "sourceEndpointContains": "okx.com/",
                "maximumGapHours": 8,
                "partitions": partitions,
            }
        )
    return references


def _blocked_evidence(
    readiness: Mapping[str, Any], *, implementation_commit: str
) -> dict[str, Any]:
    rows = []
    for candidate in readiness.get("candidates", []):
        if not isinstance(candidate, Mapping) or candidate.get("status") == "ready":
            continue
        rows.append(
            {
                "candidateId": candidate.get("candidateId"),
                "timeframe": candidate.get("timeframe"),
                "status": "blocked_before_preregistration",
                "blockers": sorted(str(value) for value in candidate.get("blockers", [])),
                "formalRunClaimBudget": 0,
                "formalRunCount": 0,
                "formalInputReadCount": 0,
                "resultReadCount": 0,
                "lockedOosAccessCount": 0,
                "releaseCount": 0,
                "demoArm": False,
                "orderCount": 0,
            }
        )
    core = {
        "schemaVersion": "v36_tsmom_blocked_candidate_evidence_v1",
        "campaignId": readiness.get("campaignId"),
        "implementationCommit": implementation_commit,
        "sourceReadinessHash": readiness.get("readinessHash"),
        "blockedCandidates": sorted(rows, key=lambda row: str(row["candidateId"])),
    }
    core["evidenceHash"] = stable_hash(core, prefix="v36_tsmom_blocked_evidence")
    return core


def prepare_handoff(
    *,
    repo_root: Path,
    data_root: Path,
    readiness_path: Path,
    policy_template_path: Path,
    implementation_commit: str,
    remote_freeze_tag: str,
) -> dict[str, Any]:
    """Prepare immutable preregistrations without consuming Formal budget."""

    root = Path(repo_root).resolve()
    data = Path(data_root).resolve()
    readiness = _read_json(Path(readiness_path).resolve())
    policy_template = _read_json(Path(policy_template_path).resolve())
    if len(str(implementation_commit)) != 40:
        raise ValueError("implementation_commit_invalid")
    if str(readiness.get("sourceCommit") or "") != str(implementation_commit):
        raise ValueError("readiness_implementation_commit_mismatch")
    for key in (
        "formalRunCount",
        "formalInputReadCount",
        "resultReadCount",
        "lockedOosAccessCount",
        "releaseCount",
        "orderCount",
    ):
        if int(readiness.get(key, -1)) != 0:
            raise ValueError(f"nonzero_{key}")
    if readiness.get("demoArm") is not False:
        raise ValueError("demo_arm_not_false")

    funding_references = _funding_references(data_root=data)
    snapshots: list[Path] = []
    preregistrations: list[Path] = []
    prepared_ids: list[str] = []
    for raw_candidate in readiness.get("candidates", []):
        if not isinstance(raw_candidate, Mapping) or raw_candidate.get("status") != "ready":
            continue
        candidate = dict(raw_candidate)
        candidate_id = str(candidate.get("candidateId") or "")
        candidate_spec = build_tsmom_candidate_spec(candidate_id)
        definition = dict(candidate_spec["definition"])
        window = dict(candidate.get("formalWindow") or {})
        snapshot = build_v36_data_snapshot(
            candidate_id=candidate_id,
            timeframe=str(candidate["timeframe"]),
            universe=TSMOM_SYMBOLS,
            common_start=str(window["start"]),
            common_cutoff_exclusive=str(window["cutoffExclusive"]),
            dataset_references=_dataset_references(candidate, data_root=data),
            funding_references=funding_references,
            source_snapshot_id=str(readiness.get("snapshotId") or ""),
        )
        split = build_v36_split_policy(
            timeframe=str(candidate["timeframe"]),
            sample_count=int(dict(candidate["ohlcvCoverage"])["commonRowCount"]),
            common_start=str(window["start"]),
            common_cutoff_exclusive=str(window["cutoffExclusive"]),
            maximum_hold_bars=int(definition["maximumHoldBars"]),
        )
        preregistration = build_v36_preregistration(
            implementation_commit=implementation_commit,
            readiness=readiness,
            candidate_id=candidate_id,
            snapshot=snapshot,
            split_policy=split,
            policy_template=policy_template,
            remote_freeze_tag=remote_freeze_tag,
        )
        snapshot_path = root / "research" / "data_snapshots" / f"{snapshot['snapshotId']}.json"
        preregistration_path = (
            root
            / "research"
            / "preregistrations"
            / f"{preregistration['campaignId']}.json"
        )
        _write_once(snapshot_path, snapshot)
        _write_once(preregistration_path, preregistration)
        snapshots.append(snapshot_path)
        preregistrations.append(preregistration_path)
        prepared_ids.append(candidate_id)

    blocked = _blocked_evidence(readiness, implementation_commit=implementation_commit)
    report_root = (
        root
        / "reports"
        / "formal_validation"
        / "v36_tsmom_formal_handoff"
        / str(readiness.get("campaignId") or "v36")
    )
    blocked_path = report_root / "blocked_candidate_evidence.json"
    _write_once(blocked_path, blocked)
    result = {
        "schemaVersion": "v36_tsmom_formal_handoff_preparation_v1",
        "status": "prepared_zero_budget",
        "campaignId": readiness.get("campaignId"),
        "implementationCommit": implementation_commit,
        "preparedCandidateIds": sorted(prepared_ids),
        "blockedCandidateIds": [
            row["candidateId"] for row in blocked["blockedCandidates"]
        ],
        "snapshotPaths": [str(path) for path in snapshots],
        "preregistrationPaths": [str(path) for path in preregistrations],
        "blockedEvidencePath": blocked_path.relative_to(root).as_posix(),
        "formalRunCount": 0,
        "formalInputReadCount": 0,
        "resultReadCount": 0,
        "lockedOosAccessCount": 0,
        "releaseCount": 0,
        "demoArm": False,
        "orderCount": 0,
    }
    result["preparationHash"] = stable_hash(
        result, prefix="v36_tsmom_formal_handoff_preparation"
    )
    _write_once(report_root / "pre_result_handoff.json", result)
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--readiness", type=Path, required=True)
    parser.add_argument("--policy-template", type=Path, required=True)
    parser.add_argument("--implementation-commit", required=True)
    parser.add_argument("--remote-freeze-tag", required=True)
    return parser


def run(argv: Sequence[str] | None = None) -> dict[str, Any]:
    args = _parser().parse_args(argv)
    return prepare_handoff(
        repo_root=args.repo_root,
        data_root=args.data_root,
        readiness_path=args.readiness,
        policy_template_path=args.policy_template,
        implementation_commit=args.implementation_commit,
        remote_freeze_tag=args.remote_freeze_tag,
    )


def main(argv: Sequence[str] | None = None) -> int:
    print(json.dumps(run(argv), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
