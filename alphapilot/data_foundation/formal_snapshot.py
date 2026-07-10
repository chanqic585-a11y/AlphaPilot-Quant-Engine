"""Validate official partitions and freeze an immutable formal snapshot."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from alphapilot.evolution.data_lineage.snapshot_registry import (
    build_data_snapshot_manifest,
    register_data_snapshot,
    verify_data_snapshot,
)
from alphapilot.evolution.registry.hashing import sha256_file, stable_hash
from alphapilot.evolution.registry.repositories import RegistryRepository
from alphapilot.evolution.registry.types import DataSnapshotRecord
from alphapilot.evolution.workflow.types import StrategyDataContractRecord

from .checkpoint import write_json_atomic
from .official_history import OfficialCollectionResult, OfficialPartition
from .okx_public import TIMEFRAME_MILLISECONDS
from .warehouse import WarehouseLayout


class FormalSnapshotError(RuntimeError):
    """Raised when official evidence cannot satisfy the formal data gate."""


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def _validate_partition(
    partition: OfficialPartition,
    layout: WarehouseLayout,
) -> pd.DataFrame:
    if partition.provenanceStatus != "official_okx_public":
        raise FormalSnapshotError(
            f"formal_partition_provenance_invalid:{partition.instrumentId}:{partition.timeframe}"
        )
    if not partition.outputPath or not partition.outputSha256:
        raise FormalSnapshotError(
            f"formal_partition_missing:{partition.instrumentId}:{partition.timeframe}"
        )
    path = Path(partition.outputPath)
    if not path.is_file() or not _inside(path, layout.canonicalRoot):
        raise FormalSnapshotError(f"formal_partition_path_invalid:{path}")
    if sha256_file(path) != partition.outputSha256:
        raise FormalSnapshotError(f"formal_partition_checksum_mismatch:{path}")
    frame = pd.read_parquet(path)
    required = {
        "timestamp_ms",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "confirmed",
        "exchange",
        "source_endpoint",
        "collected_at",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise FormalSnapshotError(
            f"formal_partition_columns_missing:{','.join(missing)}"
        )
    if frame.empty or (frame["confirmed"] != 1).any():
        raise FormalSnapshotError(f"formal_partition_unconfirmed:{path}")
    if set(frame["exchange"].astype(str).str.lower()) != {"okx"}:
        raise FormalSnapshotError(f"formal_partition_exchange_invalid:{path}")
    timestamps = pd.to_numeric(frame["timestamp_ms"], errors="coerce")
    differences = timestamps.sort_values().diff().dropna()
    interval = TIMEFRAME_MILLISECONDS[partition.timeframe]
    if (
        timestamps.isna().any()
        or timestamps.duplicated().any()
        or (differences != interval).any()
    ):
        raise FormalSnapshotError(
            f"formal_partition_gap_detected:{partition.instrumentId}:{partition.timeframe}"
        )
    return frame


def _validate_funding(path_value: str, layout: WarehouseLayout) -> Path:
    path = Path(path_value)
    if not path.is_file() or not _inside(path, layout.canonicalRoot):
        raise FormalSnapshotError(f"formal_funding_path_invalid:{path}")
    frame = pd.read_parquet(path)
    required = {
        "instrument_id",
        "funding_rate",
        "timestamp_ms",
        "source_endpoint",
        "collected_at",
    }
    missing = sorted(required - set(frame.columns))
    if missing or frame.empty:
        raise FormalSnapshotError(
            f"formal_funding_invalid:{path}:{','.join(missing)}"
        )
    return path


def freeze_formal_snapshot(
    collection: OfficialCollectionResult,
    contract: StrategyDataContractRecord,
    layout: WarehouseLayout,
    repository: RegistryRepository,
) -> DataSnapshotRecord:
    if collection.status != "completed":
        raise FormalSnapshotError(f"official_collection_not_complete:{collection.status}")
    if collection.strategyDataContractId != contract.strategyDataContractId:
        raise FormalSnapshotError("official_collection_contract_mismatch")
    frames = [
        (partition, _validate_partition(partition, layout))
        for partition in collection.partitions
    ]
    instruments = sorted({partition.instrumentId for partition, _ in frames})
    minimum_members = int(
        (contract.contract.get("universePolicy") or {}).get("minimumMembers", 1)
    )
    if len(instruments) < minimum_members:
        raise FormalSnapshotError(
            f"formal_universe_too_small:{len(instruments)}:{minimum_members}"
        )
    expected_timeframes = {
        str(value)
        for value in (
            contract.contract.get("signalTimeframe"),
            contract.contract.get("executionTimeframe"),
            contract.contract.get("executionFallbackTimeframe"),
        )
        if value
    }
    by_instrument = {
        instrument: {
            partition.timeframe
            for partition, _ in frames
            if partition.instrumentId == instrument
        }
        for instrument in instruments
    }
    incomplete = [
        instrument
        for instrument, timeframes in by_instrument.items()
        if not expected_timeframes.issubset(timeframes)
    ]
    if incomplete:
        raise FormalSnapshotError(
            f"formal_universe_timeframes_missing:{','.join(incomplete)}"
        )
    funding_paths = [
        _validate_funding(value, layout) for value in collection.fundingPaths
    ]
    if len(funding_paths) < minimum_members:
        raise FormalSnapshotError(
            f"formal_funding_coverage_too_small:{len(funding_paths)}:{minimum_members}"
        )
    all_paths = [Path(partition.outputPath) for partition, _ in frames if partition.outputPath]
    all_paths.extend(funding_paths)
    starts = [str(partition.startTime) for partition, _ in frames if partition.startTime]
    ends = [str(partition.endTime) for partition, _ in frames if partition.endTime]
    manifest = build_data_snapshot_manifest(
        files=all_paths,
        root=layout.canonicalRoot,
        source="okx_public_official",
        exchange="okx",
        market_type=str(contract.contract["marketType"]),
        timeframe="multi",
        start_time=min(starts),
        end_time=max(ends),
        point_in_time_cutoff=min(ends),
        universe_members=instruments,
        metadata={
            "provenanceComplete": True,
            "pointInTimeValidated": True,
            "formalResearchEligible": True,
            "formalPromotionEligible": True,
            "evidenceClass": "formal_backtest",
            "strategyDataContractId": contract.strategyDataContractId,
            "strategyDataContractHash": contract.contentHash,
            "universeManifestHash": stable_hash(
                {
                    "instruments": instruments,
                    "coverage": by_instrument,
                },
                prefix="universe",
            ),
            "qualityManifestHash": stable_hash(
                {
                    "partitionHashes": sorted(
                        str(partition.outputSha256) for partition, _ in frames
                    ),
                    "fundingHashes": sorted(sha256_file(path) for path in funding_paths),
                },
                prefix="quality",
            ),
        },
    )
    verification = verify_data_snapshot(manifest, root=layout.canonicalRoot)
    if not verification["valid"]:
        raise FormalSnapshotError(
            f"formal_snapshot_verification_failed:{verification['errors']}"
        )
    write_json_atomic(
        layout.manifestRoot / "snapshots" / f"{manifest['dataSnapshotId']}.json",
        manifest,
    )
    return register_data_snapshot(manifest, repository)
