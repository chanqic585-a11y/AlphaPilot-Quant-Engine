"""Candidate-neutral frozen formal-input loader."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import pandas as pd

from alphapilot.evolution.registry.hashing import sha256_file

from .candidate_adapter import CandidateAdapter, validate_candidate_binding


REQUIRED_COLUMNS = ("date", "open", "high", "low", "close", "volume")
_MAPPABLE_COLUMNS = {*REQUIRED_COLUMNS, "confirmed"}


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


def _apply_column_map(
    frame: pd.DataFrame,
    *,
    reference: Mapping[str, Any],
) -> tuple[pd.DataFrame, bool]:
    raw_mapping = reference.get("columnMap") or {}
    if not isinstance(raw_mapping, Mapping):
        raise FormalInputError(
            f"partition_column_map_invalid:{reference.get('instrumentId')}"
        )
    rename: dict[str, str] = {}
    for canonical, source in raw_mapping.items():
        target = str(canonical)
        source_name = str(source)
        if target not in _MAPPABLE_COLUMNS or not source_name:
            raise FormalInputError(
                f"partition_column_map_invalid:{reference.get('instrumentId')}"
            )
        if source_name not in frame.columns:
            raise FormalInputError(
                f"partition_column_map_source_missing:"
                f"{reference.get('instrumentId')}:{source_name}"
            )
        if target in frame.columns and source_name != target:
            raise FormalInputError(
                f"partition_column_map_collision:{reference.get('instrumentId')}:{target}"
            )
        rename[source_name] = target
    return frame.rename(columns=rename), bool(rename)


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
    frame, mapping_applied = _apply_column_map(
        pd.read_parquet(path), reference=reference
    )
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
        "columnMap": dict(reference.get("columnMap") or {}),
        "columnMappingApplied": mapping_applied,
        "firstTimestamp": frame.iloc[0]["date"].isoformat(),
        "lastTimestamp": frame.iloc[-1]["date"].isoformat(),
    }


def _registered_funding_references(
    snapshot: Mapping[str, Any],
    *,
    universe: Sequence[str],
    required: bool,
) -> dict[str, dict[str, Any]]:
    raw = snapshot.get("fundingDatasetReferences") or []
    if not isinstance(raw, list):
        raise FormalInputError("funding_references_invalid")
    references: dict[str, dict[str, Any]] = {}
    for value in raw:
        if not isinstance(value, Mapping):
            raise FormalInputError("funding_references_invalid")
        instrument_id = str(value.get("instrumentId") or "")
        if not instrument_id or instrument_id in references:
            raise FormalInputError("funding_reference_identity_invalid")
        references[instrument_id] = dict(value)
    if not references:
        if required:
            raise FormalInputError("funding_evidence_missing")
        return {}
    missing = sorted(set(universe) - set(references))
    extra = sorted(set(references) - set(universe))
    if missing or extra:
        raise FormalInputError(
            f"funding_universe_mismatch:missing={missing}:extra={extra}"
        )
    return references


def _funding_columns(
    frame: pd.DataFrame,
    *,
    instrument_id: str,
) -> pd.DataFrame:
    timestamp_column = next(
        (name for name in ("timestamp_ms", "fundingTime", "date") if name in frame),
        None,
    )
    rate_column = next(
        (name for name in ("funding_rate", "fundingRate") if name in frame),
        None,
    )
    if timestamp_column is None or rate_column is None:
        raise FormalInputError(f"funding_columns_missing:{instrument_id}")
    selected = frame[[timestamp_column, rate_column]].rename(
        columns={timestamp_column: "timestamp", rate_column: "fundingRate"}
    )
    if pd.api.types.is_numeric_dtype(selected["timestamp"]):
        selected["timestamp"] = pd.to_datetime(
            pd.to_numeric(selected["timestamp"], errors="coerce"),
            unit="ms",
            utc=True,
            errors="coerce",
        )
    else:
        selected["timestamp"] = pd.to_datetime(
            selected["timestamp"], utc=True, errors="coerce"
        )
    selected["fundingRate"] = pd.to_numeric(
        selected["fundingRate"], errors="coerce"
    )
    if selected["timestamp"].isna().any() or not selected["fundingRate"].map(
        lambda value: pd.notna(value) and math.isfinite(float(value))
    ).all():
        raise FormalInputError(f"funding_value_invalid:{instrument_id}")
    return selected


def _load_funding_reference(
    *,
    data_root: Path,
    reference: Mapping[str, Any],
    start: pd.Timestamp,
    cutoff_exclusive: pd.Timestamp,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    instrument_id = str(reference.get("instrumentId") or "")
    provider = str(reference.get("provider") or "").lower()
    exchange = str(reference.get("exchange") or "").lower()
    endpoint_token = str(reference.get("sourceEndpointContains") or "").lower()
    maximum_gap_hours = float(reference.get("maximumGapHours") or 0.0)
    if (
        not instrument_id
        or not provider
        or provider != exchange
        or not endpoint_token
        or maximum_gap_hours <= 0.0
    ):
        raise FormalInputError(f"funding_provenance_invalid:{instrument_id}")
    partitions = reference.get("partitions") or []
    if not isinstance(partitions, list) or not partitions:
        raise FormalInputError(f"funding_partition_missing:{instrument_id}")

    frames: list[pd.DataFrame] = []
    partition_evidence: list[dict[str, Any]] = []
    for raw_partition in partitions:
        if not isinstance(raw_partition, Mapping):
            raise FormalInputError(f"funding_partition_invalid:{instrument_id}")
        relative = Path(str(raw_partition.get("path") or ""))
        path = data_root / relative
        if not path.is_file():
            raise FormalInputError(f"funding_partition_missing:{instrument_id}")
        actual_hash = sha256_file(path)
        expected_hash = str(raw_partition.get("sha256") or "")
        if not expected_hash or actual_hash != expected_hash:
            raise FormalInputError(f"funding_partition_hash_mismatch:{instrument_id}")
        raw_frame = pd.read_parquet(path)
        if "instrument_id" in raw_frame:
            instruments = set(raw_frame["instrument_id"].dropna().astype(str))
            if instruments and instruments != {instrument_id}:
                raise FormalInputError(f"funding_instrument_mismatch:{instrument_id}")
        if "source_endpoint" not in raw_frame or not raw_frame[
            "source_endpoint"
        ].astype(str).str.lower().str.contains(endpoint_token, regex=False).all():
            raise FormalInputError(f"funding_provenance_invalid:{instrument_id}")
        selected = _funding_columns(raw_frame, instrument_id=instrument_id)
        frames.append(selected)
        partition_evidence.append(
            {
                "relativePath": relative.as_posix(),
                "registeredSha256": expected_hash,
                "verifiedSha256": actual_hash,
                "rowCount": len(selected),
            }
        )
    combined = pd.concat(frames, ignore_index=True).sort_values("timestamp")
    conflicts = combined.groupby("timestamp")["fundingRate"].nunique(dropna=False)
    if (conflicts > 1).any():
        raise FormalInputError(f"funding_duplicate_conflict:{instrument_id}")
    combined = combined.drop_duplicates("timestamp", keep="last").reset_index(drop=True)
    combined = combined[
        (combined["timestamp"] >= start)
        & (combined["timestamp"] < cutoff_exclusive)
    ].reset_index(drop=True)
    maximum_gap = pd.Timedelta(hours=maximum_gap_hours)
    observed_gap = combined["timestamp"].diff().dropna().max()
    if pd.notna(observed_gap) and observed_gap > maximum_gap:
        raise FormalInputError(f"funding_schedule_incomplete:{instrument_id}")
    if (
        combined.empty
        or combined.iloc[0]["timestamp"] > start
        or combined.iloc[-1]["timestamp"] < cutoff_exclusive - maximum_gap
    ):
        raise FormalInputError(f"funding_window_incomplete:{instrument_id}")
    return combined, {
        "instrumentId": instrument_id,
        "provider": provider,
        "exchange": exchange,
        "maximumGapHours": maximum_gap_hours,
        "firstTimestamp": combined.iloc[0]["timestamp"].isoformat(),
        "lastTimestamp": combined.iloc[-1]["timestamp"].isoformat(),
        "eventCount": len(combined),
        "partitions": partition_evidence,
    }


def _attach_funding_cashflows(
    frame: pd.DataFrame,
    *,
    funding: pd.DataFrame,
    start: pd.Timestamp,
    cutoff_exclusive: pd.Timestamp,
) -> pd.DataFrame:
    result = frame.copy()
    bar_times = pd.DatetimeIndex(result["date"])
    cashflows = pd.Series(0.0, index=range(len(result)), dtype="float64")
    event_counts = pd.Series(0, index=range(len(result)), dtype="int64")
    window = funding[
        (funding["timestamp"] >= start)
        & (funding["timestamp"] < cutoff_exclusive)
    ]
    for row in window.itertuples(index=False):
        position = int(bar_times.searchsorted(row.timestamp, side="right") - 1)
        if position < 0 or position >= len(result):
            raise FormalInputError("funding_event_outside_bar_window")
        cashflows.iloc[position] += float(row.fundingRate)
        event_counts.iloc[position] += 1
    result["fundingRate"] = cashflows.to_numpy()
    result["fundingEventPresent"] = event_counts.gt(0).to_numpy()
    result["fundingEventCount"] = event_counts.to_numpy()
    return result


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
    funding_references = _registered_funding_references(
        snapshot,
        universe=universe,
        required=bool(candidate.get("fundingEvidenceRequired")),
    )

    frames: dict[str, pd.DataFrame] = {}
    partitions: list[dict[str, Any]] = []
    funding_partitions: list[dict[str, Any]] = []
    expected_index: pd.DatetimeIndex | None = None
    for symbol in universe:
        frame, partition = _load_partition(
            data_root=data_root,
            reference=references[symbol],
            start=start,
            cutoff_exclusive=cutoff_exclusive,
        )
        if funding_references:
            funding, funding_partition = _load_funding_reference(
                data_root=data_root,
                reference=funding_references[symbol],
                start=start,
                cutoff_exclusive=cutoff_exclusive,
            )
            frame = _attach_funding_cashflows(
                frame,
                funding=funding,
                start=start,
                cutoff_exclusive=cutoff_exclusive,
            )
            funding_partitions.append(funding_partition)
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
        "columnMappingApplied": any(
            bool(row.get("columnMappingApplied")) for row in partitions
        ),
        "commonStart": start.isoformat(),
        "commonCutoffExclusive": cutoff_exclusive.isoformat(),
        "sampleCount": len(common_index),
        "partitions": partitions,
        "fundingEvidence": {
            "required": bool(candidate.get("fundingEvidenceRequired")),
            "scheduleComplete": bool(funding_references),
            "sameExchangeVerified": bool(funding_references),
            "missingRateZeroFilled": False,
            "nonSettlementCashflowZeroApplied": bool(funding_references),
            "verifiedInstrumentCount": len(funding_partitions),
            "instruments": funding_partitions,
        },
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
