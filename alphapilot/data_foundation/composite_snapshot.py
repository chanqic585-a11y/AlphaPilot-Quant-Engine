"""Build a verified snapshot from canonical base files and public increments."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from alphapilot.evolution.data_lineage.snapshot_registry import (
    build_data_snapshot_manifest,
    register_data_snapshot,
    verify_data_snapshot,
)
from alphapilot.evolution.registry.database import connect_registry
from alphapilot.evolution.registry.repositories import RegistryRepository

from .checkpoint import write_json_atomic
from .okx_public import CANONICAL_SOURCE_NAMES, TIMEFRAME_MILLISECONDS


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _iso(timestamp_ms: int) -> str:
    return pd.Timestamp(timestamp_ms, unit="ms", tz="UTC").isoformat()


def _canonical_paths(
    canonical_root: Path,
    *,
    market_type: str,
    instrument_id: str,
    timeframe: str,
) -> list[Path]:
    return sorted(
        path
        for source_name in CANONICAL_SOURCE_NAMES
        for path in (canonical_root / source_name / market_type / "ohlcv" / instrument_id / timeframe).glob("*.parquet")
    )


def inspect_canonical_group(
    paths: Iterable[Path | str],
    *,
    timeframe: str,
    canonical_root: Path | str | None = None,
) -> dict[str, Any]:
    if timeframe not in TIMEFRAME_MILLISECONDS:
        raise ValueError(f"Unsupported timeframe: {timeframe}")
    root = Path(canonical_root).resolve() if canonical_root is not None else None
    resolved_paths = sorted({Path(path).resolve() for path in paths})
    if not resolved_paths:
        return {
            "valid": False,
            "fileCount": 0,
            "rows": 0,
            "uniqueRows": 0,
            "startTime": None,
            "endTime": None,
            "duplicateTimestampCount": 0,
            "gapEventCount": 0,
            "missingBarCount": 0,
            "misalignedIntervalCount": 0,
            "sourceCounts": {},
            "errors": ["canonical_group_missing"],
        }

    timestamp_parts: list[pd.Series] = []
    source_counts: dict[str, int] = {}
    errors: list[str] = []
    for path in resolved_paths:
        try:
            frame = pd.read_parquet(path, columns=["timestamp_ms"])
        except Exception as exc:  # noqa: BLE001 - report every corrupt canonical fragment.
            errors.append(f"read_failed:{path.name}:{exc}")
            continue
        values = pd.to_numeric(frame["timestamp_ms"], errors="coerce").dropna().astype("int64")
        timestamp_parts.append(values)
        source_name = "outside_root"
        if root is not None:
            try:
                source_name = path.relative_to(root).parts[0]
            except ValueError:
                errors.append(f"outside_canonical_root:{path}")
        source_counts[source_name] = source_counts.get(source_name, 0) + 1

    if not timestamp_parts:
        errors.append("canonical_group_has_no_readable_rows")
        return {
            "valid": False,
            "fileCount": len(resolved_paths),
            "rows": 0,
            "uniqueRows": 0,
            "startTime": None,
            "endTime": None,
            "duplicateTimestampCount": 0,
            "gapEventCount": 0,
            "missingBarCount": 0,
            "misalignedIntervalCount": 0,
            "sourceCounts": source_counts,
            "errors": errors,
        }

    all_timestamps = pd.concat(timestamp_parts, ignore_index=True)
    duplicate_count = int(len(all_timestamps) - all_timestamps.nunique())
    unique_timestamps = all_timestamps.drop_duplicates().sort_values().reset_index(drop=True)
    interval_ms = TIMEFRAME_MILLISECONDS[timeframe]
    differences = unique_timestamps.diff().dropna().astype("int64")
    invalid_intervals = differences[differences != interval_ms]
    gap_differences = invalid_intervals[(invalid_intervals > interval_ms) & (invalid_intervals % interval_ms == 0)]
    misaligned_count = int(len(invalid_intervals) - len(gap_differences))
    missing_bar_count = int(sum(int(value // interval_ms) - 1 for value in gap_differences))
    if duplicate_count:
        errors.append("duplicate_timestamps_across_fragments")
    if len(gap_differences):
        errors.append("gaps_across_fragments")
    if misaligned_count:
        errors.append("misaligned_intervals_across_fragments")

    first = int(unique_timestamps.iloc[0]) if len(unique_timestamps) else None
    last = int(unique_timestamps.iloc[-1]) if len(unique_timestamps) else None
    return {
        "valid": not errors,
        "fileCount": len(resolved_paths),
        "rows": int(len(all_timestamps)),
        "uniqueRows": int(len(unique_timestamps)),
        "startTime": _iso(first) if first is not None else None,
        "endTime": _iso(last) if last is not None else None,
        "duplicateTimestampCount": duplicate_count,
        "gapEventCount": int(len(gap_differences)),
        "missingBarCount": missing_bar_count,
        "misalignedIntervalCount": misaligned_count,
        "sourceCounts": dict(sorted(source_counts.items())),
        "errors": errors,
    }


def build_composite_data_snapshot(
    *,
    market_root: Path | str = "data/market",
    registry_path: Path | str = "data/evolution_registry.sqlite",
    instruments: Iterable[str] = ("BTC-USDT-SWAP", "ETH-USDT-SWAP", "SOL-USDT-SWAP"),
    timeframes: Iterable[str] = ("15m", "1h", "4h", "1d"),
    market_type: str = "swap",
    register_snapshot: bool = True,
) -> dict[str, Any]:
    output_root = Path(market_root).resolve()
    canonical_root = output_root / "canonical"
    instrument_list = sorted({str(value).upper() for value in instruments})
    timeframe_list = list(dict.fromkeys(str(value).lower() for value in timeframes))
    invalid_timeframes = sorted(set(timeframe_list) - set(TIMEFRAME_MILLISECONDS))
    if invalid_timeframes:
        raise ValueError(f"Unsupported timeframe(s): {', '.join(invalid_timeframes)}")

    group_rows: list[dict[str, Any]] = []
    snapshot_files: set[Path] = set()
    for instrument_id in instrument_list:
        for timeframe in timeframe_list:
            paths = _canonical_paths(
                canonical_root,
                market_type=market_type,
                instrument_id=instrument_id,
                timeframe=timeframe,
            )
            quality = inspect_canonical_group(paths, timeframe=timeframe, canonical_root=canonical_root)
            group_rows.append({"instrumentId": instrument_id, "timeframe": timeframe, **quality})
            snapshot_files.update(paths)

    errors = [
        f"{row['instrumentId']}:{row['timeframe']}:{error}"
        for row in group_rows
        for error in row["errors"]
    ]
    starts = [str(row["startTime"]) for row in group_rows if row["startTime"]]
    ends = [str(row["endTime"]) for row in group_rows if row["endTime"]]
    relative_sources = {
        path.relative_to(canonical_root).parts[0]
        for path in snapshot_files
    }
    provenance_complete = "unknown" not in relative_sources
    manifest = None
    verification = None
    registered = False
    if snapshot_files and not errors:
        manifest = build_data_snapshot_manifest(
            files=snapshot_files,
            root=canonical_root,
            source="alphapilot_v13_16_composite_market_data",
            exchange="okx" if provenance_complete else "mixed",
            market_type=market_type,
            timeframe="multi" if len(timeframe_list) > 1 else timeframe_list[0],
            start_time=min(starts, default=None),
            end_time=max(ends, default=None),
            point_in_time_cutoff=min(ends, default=None),
            universe_members=instrument_list,
            metadata={
                "commonStartTime": max(starts, default=None),
                "provenanceComplete": provenance_complete,
                "formalPromotionEligible": provenance_complete,
                "provenanceStatus": (
                    "okx_public_verified"
                    if provenance_complete
                    else "mixed_unverified_local_base_plus_verified_okx_public_increment"
                ),
                "canonicalSources": sorted(relative_sources),
                "groupQuality": group_rows,
                "rewardRiskMinimum": 2.0,
            },
        )
        manifest_path = output_root / "snapshots" / f"{manifest['dataSnapshotId']}.json"
        write_json_atomic(manifest_path, manifest)
        verification = verify_data_snapshot(manifest, root=canonical_root)
        if register_snapshot and verification["valid"]:
            connection = connect_registry(registry_path)
            try:
                register_data_snapshot(manifest, RegistryRepository(connection))
                registered = True
            finally:
                connection.close()

    formal_eligible = bool(
        manifest
        and verification
        and verification.get("valid")
        and provenance_complete
        and not errors
    )
    blockers = list(errors)
    if not provenance_complete:
        blockers.append("local_base_source_provenance_not_verified")
    status = "blocked"
    if manifest and not errors:
        status = "completed" if provenance_complete else "completed_with_provenance_warning"
    return {
        "reportId": "v13_16_composite_data_snapshot_report",
        "version": "V13.16.0",
        "status": status,
        "generatedAt": _utc_now(),
        "requestedGroupCount": len(instrument_list) * len(timeframe_list),
        "validGroupCount": sum(bool(row["valid"]) for row in group_rows),
        "canonicalFileCount": len(snapshot_files),
        "groups": group_rows,
        "dataSnapshot": manifest,
        "dataSnapshotVerification": verification,
        "dataSnapshotRegistered": registered,
        "formalPromotionEligible": formal_eligible,
        "blockers": blockers,
        "safetyBoundary": {
            "localOrPublicDataOnly": True,
            "apiKeyUsed": False,
            "accountRead": False,
            "tradeApiUsed": False,
            "withdrawApiUsed": False,
            "orderCreated": False,
            "liveTradingEnabled": False,
        },
    }
