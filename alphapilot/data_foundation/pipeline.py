"""Orchestrate catalog, canonical smoke assets, and immutable snapshots."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

from alphapilot.evolution.data_lineage.snapshot_registry import (
    build_data_snapshot_manifest,
    register_data_snapshot,
    verify_data_snapshot,
)
from alphapilot.evolution.registry.database import connect_registry
from alphapilot.evolution.registry.repositories import RegistryRepository

from .canonical import canonicalize_asset
from .catalog import DEFAULT_RAW_ROOT, build_raw_catalog
from .checkpoint import write_json_atomic
from .types import RawDataAsset


DEFAULT_MARKET_ROOT = Path("data/market")


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _assets_from_catalog(catalog: dict[str, Any]) -> list[RawDataAsset]:
    return [RawDataAsset(**value) for value in catalog.get("assets", []) if isinstance(value, dict)]


def _select_smoke_assets(
    assets: Iterable[RawDataAsset],
    *,
    symbols: set[str],
    timeframes: set[str],
    market_type: str,
) -> list[RawDataAsset]:
    selected = [
        asset
        for asset in assets
        if asset.selected
        and asset.dataKind == "ohlcv"
        and asset.marketType == market_type
        and asset.symbol in symbols
        and asset.timeframe in timeframes
    ]
    return sorted(selected, key=lambda item: (item.symbol or "", item.timeframe or "", item.relativePath))


def run_data_foundation(
    *,
    raw_root: Path | str = DEFAULT_RAW_ROOT,
    market_root: Path | str = DEFAULT_MARKET_ROOT,
    registry_path: Path | str = "data/evolution_registry.sqlite",
    symbols: Iterable[str] = ("BTC", "ETH", "SOL"),
    timeframes: Iterable[str] = ("15m", "1h", "4h", "1d"),
    market_type: str = "swap",
    exchange: str = "unknown",
    hash_mode: str = "none",
    overwrite: bool = False,
    register_snapshot: bool = True,
) -> dict[str, Any]:
    root = Path(raw_root).resolve()
    output_root = Path(market_root).resolve()
    requested_timeframes = {str(value).lower() for value in timeframes}
    supported_timeframes = {"5m", "15m", "1h", "4h", "1d"}
    unknown_timeframes = sorted(requested_timeframes - supported_timeframes)
    if unknown_timeframes:
        raise ValueError(f"Unsupported timeframe(s): {', '.join(unknown_timeframes)}")
    catalog_dir = output_root / "catalog"
    checkpoint_dir = output_root / "checkpoints"
    canonical_root = output_root / "canonical"
    pause_file = checkpoint_dir / "PAUSE_REQUESTED"
    catalog = build_raw_catalog(
        root,
        hash_mode=hash_mode,
        checkpoint_path=checkpoint_dir / "catalog_hash_checkpoint.json",
        pause_file=pause_file,
    )
    write_json_atomic(catalog_dir / "raw_catalog.json", catalog)
    assets = _assets_from_catalog(catalog)
    smoke_assets = _select_smoke_assets(
        assets,
        symbols={str(value).upper() for value in symbols},
        timeframes=requested_timeframes,
        market_type=market_type,
    )
    canonical_assets = [
        canonicalize_asset(asset, output_root=canonical_root, exchange=exchange, overwrite=overwrite)
        for asset in smoke_assets
    ]
    completed = [item for item in canonical_assets if item.status in {"created", "existing"} and item.outputPath]
    quality_rows = [item.quality for item in completed if item.quality]
    start_time = min((item.startTime for item in quality_rows if item.startTime), default=None)
    end_time = max((item.endTime for item in quality_rows if item.endTime), default=None)
    common_start_time = max((item.startTime for item in quality_rows if item.startTime), default=None)
    point_in_time_cutoff = min((item.endTime for item in quality_rows if item.endTime), default=None)
    manifest = None
    verification = None
    registered = False
    if completed:
        manifest = build_data_snapshot_manifest(
            files=[Path(item.outputPath) for item in completed if item.outputPath],
            root=canonical_root,
            source="alphapilot_v13_16_local_market_data",
            exchange=exchange,
            market_type=market_type,
            timeframe="multi" if len({item.timeframe for item in completed}) > 1 else completed[0].timeframe,
            start_time=start_time,
            end_time=end_time,
            point_in_time_cutoff=point_in_time_cutoff,
            universe_members=sorted({str(item.instrumentId) for item in completed if item.instrumentId}),
            metadata={
                "provenanceComplete": catalog.get("provenanceComplete", False),
                "formalPromotionEligible": bool(catalog.get("provenanceComplete", False)),
                "catalogSchemaVersion": catalog.get("schemaVersion"),
                "rewardRiskMinimum": 2.0,
                "commonStartTime": common_start_time,
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
    failed = [item for item in canonical_assets if item.status.startswith("failed")]
    status = "completed" if completed and not failed else "completed_with_blocks" if completed else "blocked"
    if not catalog.get("provenanceComplete") and status == "completed":
        status = "completed_with_provenance_warning"
    return {
        "reportId": "v13_16_data_foundation_report",
        "version": "V13.16.0",
        "status": status,
        "generatedAt": _utc_now(),
        "rawRoot": str(root),
        "marketRoot": str(output_root),
        "catalogSummary": {key: catalog.get(key) for key in (
            "totalFileCount",
            "selectedFileCount",
            "totalSizeBytes",
            "provenanceComplete",
            "selectionSummary",
            "flagSummary",
            "hashSummary",
        )},
        "smokeRequested": {"symbols": sorted({str(value).upper() for value in symbols}), "timeframes": sorted(requested_timeframes), "marketType": market_type},
        "smokeAssetCount": len(smoke_assets),
        "canonicalCreatedOrExistingCount": len(completed),
        "canonicalFailedCount": len(failed),
        "canonicalAssets": [item.to_dict() for item in canonical_assets],
        "dataSnapshot": manifest,
        "dataSnapshotVerification": verification,
        "dataSnapshotRegistered": registered,
        "formalPromotionEligible": bool(catalog.get("provenanceComplete", False) and verification and verification.get("valid")),
        "blockers": ([] if catalog.get("provenanceComplete") else ["source_provenance_not_verified"]),
        "safetyBoundary": {
            "localOrPublicDataOnly": True,
            "apiKeyUsed": False,
            "tradeApiUsed": False,
            "withdrawApiUsed": False,
            "accountRead": False,
            "orderCreated": False,
            "liveTradingEnabled": False,
        },
    }
