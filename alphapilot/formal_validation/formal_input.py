"""Candidate-neutral frozen formal-input loader."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

import pandas as pd

from alphapilot.evolution.registry.hashing import sha256_file

from .candidate_adapter import CandidateAdapter, validate_candidate_binding


REQUIRED_COLUMNS = ("date", "open", "high", "low", "close", "volume")


class FormalInputError(RuntimeError):
    """Raised when frozen formal input differs from its preregistration."""


@dataclass(frozen=True)
class FormalInputBundle:
    preregistration: dict[str, Any]
    candidate: dict[str, Any]
    snapshot: dict[str, Any]
    frames: dict[str, pd.DataFrame]
    commonIndex: pd.DatetimeIndex
    inputMapping: dict[str, Any]
    holdoutLineage: dict[str, Any]


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FormalInputError(f"metadata_missing:{path.as_posix()}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise FormalInputError(f"metadata_not_object:{path.as_posix()}")
    return value


def _candidate(
    preregistration: Mapping[str, Any],
    *,
    repo_root: Path,
    candidate_id: str,
    candidate_adapter: CandidateAdapter,
) -> dict[str, Any]:
    validate_candidate_binding(
        adapter=candidate_adapter,
        preregistration=preregistration,
        requested_candidate_id=candidate_id,
    )
    try:
        candidate = dict(
            candidate_adapter.resolve_candidate(
                repo_root=repo_root,
                preregistration=preregistration,
            )
        )
    except (KeyError, ValueError) as error:
        raise FormalInputError("candidate_identity_missing") from error
    if (
        candidate.get("strategyDefinitionHash")
        != preregistration.get("strategyDefinitionHash")
        or candidate.get("exitPolicyHash") != preregistration.get("exitPolicyHash")
    ):
        raise FormalInputError("candidate_identity_mismatch")
    return candidate


def _validate_preregistration(
    preregistration: Mapping[str, Any],
    *,
    validator: Callable[[Mapping[str, Any]], bool],
) -> None:
    if not validator(preregistration):
        raise FormalInputError("preregistration_hash_mismatch")
    frozen_counts = {
        "candidateCount": 1,
        "parameterChanges": 0,
        "exitPolicyChanges": 0,
        "universeChanges": 0,
        "costChanges": 0,
    }
    for key, expected in frozen_counts.items():
        if preregistration.get(key) != expected:
            raise FormalInputError(f"frozen_contract_mismatch:{key}")
    locked = preregistration.get("lockedOosPolicy")
    if not isinstance(locked, Mapping):
        raise FormalInputError("locked_oos_policy_missing")
    if locked.get("contentRead") is not False or int(locked.get("accessCount", -1)) != 0:
        raise FormalInputError("locked_oos_access_not_zero")


def _registered_references(
    snapshot: Mapping[str, Any],
    *,
    universe: list[str],
    timeframe: str,
) -> dict[str, dict[str, Any]]:
    references = {
        str(row.get("instrumentId")): dict(row)
        for row in snapshot.get("datasetReferences", [])
        if isinstance(row, Mapping) and str(row.get("timeframe")) == timeframe
    }
    missing = sorted(set(universe) - set(references))
    extra = sorted(set(references) - set(universe))
    if missing or extra:
        raise FormalInputError(
            f"snapshot_universe_mismatch:missing={missing}:extra={extra}"
        )
    return references


def _load_partition(
    *,
    data_root: Path,
    reference: Mapping[str, Any],
    start: pd.Timestamp,
    cutoff_exclusive: pd.Timestamp,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    path = data_root / Path(str(reference.get("path", "")))
    if not path.is_file():
        raise FormalInputError(f"partition_missing:{reference.get('instrumentId')}")
    actual_hash = sha256_file(path)
    expected_hash = str(reference.get("sha256", ""))
    if actual_hash != expected_hash:
        raise FormalInputError(
            f"partition_hash_mismatch:{reference.get('instrumentId')}"
        )
    frame = pd.read_parquet(path)
    missing_columns = sorted(set(REQUIRED_COLUMNS) - set(frame.columns))
    if missing_columns:
        raise FormalInputError(
            f"partition_columns_missing:{reference.get('instrumentId')}:{missing_columns}"
        )
    frame = frame.copy()
    frame["date"] = pd.to_datetime(frame["date"], utc=True, errors="coerce")
    if frame["date"].isna().any():
        raise FormalInputError(f"partition_invalid_timestamp:{reference.get('instrumentId')}")
    if "confirmed" in frame.columns:
        frame = frame[pd.to_numeric(frame["confirmed"], errors="coerce") == 1]
    frame = frame[(frame["date"] >= start) & (frame["date"] < cutoff_exclusive)]
    frame = frame.sort_values("date").drop_duplicates("date", keep="last")
    frame = frame.reset_index(drop=True)
    if frame.empty:
        raise FormalInputError(f"partition_empty:{reference.get('instrumentId')}")
    return frame, {
        "instrumentId": str(reference.get("instrumentId")),
        "timeframe": str(reference.get("timeframe")),
        "relativePath": str(reference.get("path")),
        "provider": reference.get("provider"),
        "registeredSha256": expected_hash,
        "verifiedSha256": actual_hash,
        "rowCount": len(frame),
        "firstTimestamp": frame.iloc[0]["date"].isoformat(),
        "lastTimestamp": frame.iloc[-1]["date"].isoformat(),
    }


def load_formal_input(
    *,
    repo_root: Path,
    data_root: Path,
    preregistration_path: Path,
    candidate_id: str,
    candidate_adapter: CandidateAdapter,
    preregistration_validator: Callable[[Mapping[str, Any]], bool],
) -> FormalInputBundle:
    """Load only the frozen formal window and return auditable input metadata."""

    repo_root = Path(repo_root).resolve()
    data_root = Path(data_root).resolve()
    preregistration = _read_json(Path(preregistration_path).resolve())
    _validate_preregistration(
        preregistration, validator=preregistration_validator
    )
    candidate = _candidate(
        preregistration,
        repo_root=repo_root,
        candidate_id=candidate_id,
        candidate_adapter=candidate_adapter,
    )

    snapshot_id = str(preregistration.get("dataSnapshotId", ""))
    snapshot = _read_json(
        repo_root / "research" / "data_snapshots" / f"{snapshot_id}.json"
    )
    snapshot_hash_valid = bool(
        snapshot.get("snapshotId") == snapshot_id
        and snapshot.get("snapshotHash") == preregistration.get("dataSnapshotHash")
        and snapshot.get("coreUniverseHash")
        == preregistration.get("coreUniverseHash")
    )
    if not snapshot_hash_valid:
        raise FormalInputError("snapshot_identity_mismatch")

    universe_payload = preregistration.get("coreUniverse")
    if not isinstance(universe_payload, Mapping):
        raise FormalInputError("core_universe_missing")
    universe = [str(value) for value in universe_payload.get("instrumentIds", [])]
    if len(universe) != int(universe_payload.get("instrumentCount", -1)):
        raise FormalInputError("core_universe_count_mismatch")
    if universe != sorted(set(universe)):
        raise FormalInputError("core_universe_not_canonical")

    split = preregistration.get("splitPolicy")
    if not isinstance(split, Mapping):
        raise FormalInputError("split_policy_missing")
    timeframe = str(split.get("timeframe", ""))
    start = pd.Timestamp(str(split.get("commonStart")))
    cutoff_exclusive = pd.Timestamp(str(split.get("commonCutoffExclusive")))
    references = _registered_references(
        snapshot, universe=universe, timeframe=timeframe
    )

    frames: dict[str, pd.DataFrame] = {}
    partitions: list[dict[str, Any]] = []
    expected_index: pd.DatetimeIndex | None = None
    for symbol in universe:
        frame, partition = _load_partition(
            data_root=data_root,
            reference=references[symbol],
            start=start,
            cutoff_exclusive=cutoff_exclusive,
        )
        index = pd.DatetimeIndex(frame["date"])
        if expected_index is None:
            expected_index = index
        elif not expected_index.equals(index):
            raise FormalInputError(f"common_index_mismatch:{symbol}")
        frames[symbol] = frame
        partitions.append(partition)

    common_index = expected_index if expected_index is not None else pd.DatetimeIndex([])
    if len(common_index) != int(split.get("sampleCount", -1)):
        raise FormalInputError(
            f"sample_count_mismatch:expected={split.get('sampleCount')}:actual={len(common_index)}"
        )

    input_mapping = {
        "schemaVersion": "formal_input_mapping_v2",
        "campaignId": preregistration.get("campaignId"),
        "candidateId": candidate["candidateId"],
        "candidateIdentityValid": True,
        "strategyDefinitionHash": candidate["strategyDefinitionHash"],
        "exitPolicyHash": candidate["exitPolicyHash"],
        "implementationConformanceHash": preregistration.get(
            "implementationConformanceHash"
        ),
        "snapshotId": snapshot_id,
        "snapshotHash": snapshot.get("snapshotHash"),
        "snapshotHashValid": True,
        "coreUniverseHash": snapshot.get("coreUniverseHash"),
        "timeframe": timeframe,
        "instrumentCount": len(universe),
        "verifiedPartitionCount": len(partitions),
        "commonStart": start.isoformat(),
        "commonCutoffExclusive": cutoff_exclusive.isoformat(),
        "sampleCount": len(common_index),
        "partitions": partitions,
    }
    holdout_lineage = {
        "schemaVersion": "formal_holdout_lineage_v2",
        "campaignId": preregistration.get("campaignId"),
        "sourceCampaignId": preregistration.get("sourceCampaignId"),
        "formalWindow": {
            "start": start.isoformat(),
            "cutoffExclusive": cutoff_exclusive.isoformat(),
        },
        "cleanLockedOosAvailable": bool(
            preregistration["lockedOosPolicy"].get("cleanLockedOosAvailable")
        ),
        "contentRead": False,
        "lockedOosAccessCount": 0,
        "formalInputSource": "frozen_registered_snapshot_only",
    }
    return FormalInputBundle(
        preregistration=dict(preregistration),
        candidate=candidate,
        snapshot=snapshot,
        frames=frames,
        commonIndex=common_index,
        inputMapping=input_mapping,
        holdoutLineage=holdout_lineage,
    )
