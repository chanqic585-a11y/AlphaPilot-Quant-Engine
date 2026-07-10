"""Discover and classify local AlphaPilot historical market-data files."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

from alphapilot.evolution.registry.hashing import sha256_file

from .checkpoint import load_json, pause_requested, write_json_atomic
from .types import RawDataAsset


DEFAULT_RAW_ROOT = Path(r"D:\Codex-Workspace\回测数据")
CATALOG_SCHEMA_VERSION = "market_data_catalog_v1"

FIVE_MINUTE_RE = re.compile(
    r"^(?P<symbol>.+)_USDT_5m_from_(?P<start>\d{8})\.csv$",
    re.IGNORECASE,
)
SWAP_XLSX_RE = re.compile(
    r"^(?P<symbol>.+)_USDT_SWAP_(?P<kind>swap_candles_(?P<timeframe>15m|1H|4H|1D)|funding_rates)_(?P<partition>ALL|20\d{2})(?P<suffix>_\d{8}_\d{6})?\.xlsx$",
    re.IGNORECASE,
)
SPOT_XLSX_RE = re.compile(
    r"^(?P<symbol>.+)_USDT_spot_candles_(?P<timeframe>15m|1H|4H|1D)_(?P<partition>ALL|20\d{2})\.xlsx$",
    re.IGNORECASE,
)
CHECKPOINT_RE = re.compile(r"_CKPT\.csv$", re.IGNORECASE)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _timeframe(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.lower()
    return {"1h": "1h", "4h": "4h", "1d": "1d", "15m": "15m", "5m": "5m"}.get(normalized)


def _asset(
    path: Path,
    root: Path,
    *,
    source_group: str,
    file_format: str,
    data_kind: str,
    market_type: str,
    instrument_id: str | None,
    symbol: str | None,
    timeframe: str | None,
    partition: str | None,
    provenance_status: str,
    exchange: str | None,
    flags: Iterable[str] = (),
) -> RawDataAsset:
    stat = path.stat()
    duplicate_family = None
    if instrument_id and data_kind:
        duplicate_family = ":".join(
            [market_type, data_kind, instrument_id, timeframe or "none"]
        )
    return RawDataAsset(
        sourcePath=str(path.resolve()),
        relativePath=path.resolve().relative_to(root.resolve()).as_posix(),
        sourceGroup=source_group,
        fileFormat=file_format,
        dataKind=data_kind,
        marketType=market_type,
        instrumentId=instrument_id,
        symbol=symbol,
        timeframe=timeframe,
        partition=partition,
        duplicateFamily=duplicate_family,
        sizeBytes=stat.st_size,
        modifiedAtNs=stat.st_mtime_ns,
        provenanceStatus=provenance_status,
        exchange=exchange,
        flags=sorted(set(flags)),
    )


def classify_path(path: Path, root: Path) -> RawDataAsset:
    relative = path.resolve().relative_to(root.resolve())
    source_group = relative.parts[0] if relative.parts else "unknown"
    name = path.name
    if source_group == "5m":
        match = FIVE_MINUTE_RE.match(name)
        if match:
            symbol = match.group("symbol").upper()
            return _asset(
                path,
                root,
                source_group=source_group,
                file_format="csv",
                data_kind="ohlcv",
                market_type="unknown",
                instrument_id=f"{symbol}-USDT",
                symbol=symbol,
                timeframe="5m",
                partition=f"from_{match.group('start')}",
                provenance_status="missing_source_manifest",
                exchange=None,
                flags=("market_type_unverified", "exchange_unverified"),
            )
    if source_group == "合约数据":
        match = SWAP_XLSX_RE.match(name)
        if match:
            symbol = match.group("symbol").upper()
            timeframe = _timeframe(match.group("timeframe"))
            flags = ["exchange_unverified"]
            if match.group("suffix"):
                flags.append("timestamped_duplicate_export")
            return _asset(
                path,
                root,
                source_group=source_group,
                file_format="xlsx",
                data_kind="funding" if match.group("kind").lower() == "funding_rates" else "ohlcv",
                market_type="swap",
                instrument_id=f"{symbol}-USDT-SWAP",
                symbol=symbol,
                timeframe=timeframe,
                partition=match.group("partition").upper(),
                provenance_status="schema_inferred_exchange_unverified",
                exchange=None,
                flags=flags,
            )
        if CHECKPOINT_RE.search(name):
            stem = name.split("_USDT_SWAP", 1)[0].upper()
            timeframe = next((value for value in ("15m", "1h", "4h", "1d") if value.lower() in name.lower()), None)
            return _asset(
                path,
                root,
                source_group=source_group,
                file_format="csv",
                data_kind="ohlcv",
                market_type="swap",
                instrument_id=f"{stem}-USDT-SWAP",
                symbol=stem,
                timeframe=timeframe,
                partition="checkpoint",
                provenance_status="schema_inferred_exchange_unverified",
                exchange=None,
                flags=("checkpoint_file", "exchange_unverified"),
            )
    if source_group == "现货数据":
        match = SPOT_XLSX_RE.match(name)
        if match:
            symbol = match.group("symbol").upper()
            return _asset(
                path,
                root,
                source_group=source_group,
                file_format="xlsx",
                data_kind="ohlcv",
                market_type="spot",
                instrument_id=f"{symbol}-USDT",
                symbol=symbol,
                timeframe=_timeframe(match.group("timeframe")),
                partition=match.group("partition").upper(),
                provenance_status="schema_inferred_exchange_unverified",
                exchange=None,
                flags=("exchange_unverified",),
            )
    return _asset(
        path,
        root,
        source_group=source_group,
        file_format=path.suffix.lower().lstrip(".") or "unknown",
        data_kind="unknown",
        market_type="unknown",
        instrument_id=None,
        symbol=None,
        timeframe=None,
        partition=None,
        provenance_status="unclassified",
        exchange=None,
        flags=("unclassified",),
    )


def _apply_selection_policy(assets: list[RawDataAsset]) -> None:
    families: dict[str, list[RawDataAsset]] = defaultdict(list)
    for asset in assets:
        if "checkpoint_file" in asset.flags:
            asset.selected = False
            asset.exclusionReason = "checkpoint_file"
        elif "timestamped_duplicate_export" in asset.flags:
            asset.selected = False
            asset.exclusionReason = "timestamped_duplicate_export"
        elif asset.dataKind == "unknown":
            asset.selected = False
            asset.exclusionReason = "unclassified"
        if asset.duplicateFamily:
            families[asset.duplicateFamily].append(asset)
    for family_assets in families.values():
        all_assets = [asset for asset in family_assets if asset.partition == "ALL" and asset.selected]
        if all_assets:
            selected_all = sorted(all_assets, key=lambda item: item.relativePath)[0]
            for asset in family_assets:
                if asset is selected_all or not asset.selected:
                    continue
                asset.selected = False
                asset.exclusionReason = "duplicate_of_all_partition"


def discover_raw_assets(root: Path | str = DEFAULT_RAW_ROOT) -> list[RawDataAsset]:
    source_root = Path(root).resolve()
    if not source_root.is_dir():
        raise FileNotFoundError(source_root)
    assets = [
        classify_path(path, source_root)
        for path in sorted(source_root.rglob("*"))
        if path.is_file()
    ]
    _apply_selection_policy(assets)
    return assets


def _checkpoint_key(asset: RawDataAsset) -> str:
    return asset.relativePath


def _hash_assets(
    assets: list[RawDataAsset],
    *,
    hash_mode: str,
    checkpoint_path: Path | None,
    pause_file: Path | None,
) -> dict[str, Any]:
    if hash_mode not in {"none", "selected", "all"}:
        raise ValueError("hash_mode must be none, selected, or all")
    checkpoint = load_json(checkpoint_path) if checkpoint_path else {}
    completed = checkpoint.get("files") if isinstance(checkpoint.get("files"), dict) else {}
    updated = dict(completed)
    hashed = 0
    reused = 0
    dirty_since_checkpoint = 0
    for asset in assets:
        should_hash = hash_mode == "all" or (hash_mode == "selected" and asset.selected)
        if not should_hash:
            continue
        if pause_requested(pause_file):
            break
        cached = completed.get(_checkpoint_key(asset))
        if (
            isinstance(cached, dict)
            and cached.get("sizeBytes") == asset.sizeBytes
            and cached.get("modifiedAtNs") == asset.modifiedAtNs
            and cached.get("sha256")
        ):
            asset.sha256 = str(cached["sha256"])
            reused += 1
        else:
            asset.sha256 = sha256_file(Path(asset.sourcePath))
            updated[_checkpoint_key(asset)] = {
                "sizeBytes": asset.sizeBytes,
                "modifiedAtNs": asset.modifiedAtNs,
                "sha256": asset.sha256,
            }
            hashed += 1
            dirty_since_checkpoint += 1
        if checkpoint_path and dirty_since_checkpoint >= 25:
            write_json_atomic(
                checkpoint_path,
                {"schemaVersion": "catalog_hash_checkpoint_v1", "files": updated, "updatedAt": _utc_now()},
            )
            dirty_since_checkpoint = 0
    if checkpoint_path and (dirty_since_checkpoint or not checkpoint_path.exists()):
        write_json_atomic(
            checkpoint_path,
            {"schemaVersion": "catalog_hash_checkpoint_v1", "files": updated, "updatedAt": _utc_now()},
        )
    return {"hashedFileCount": hashed, "reusedHashCount": reused, "pauseRequested": pause_requested(pause_file)}


def build_raw_catalog(
    root: Path | str = DEFAULT_RAW_ROOT,
    *,
    hash_mode: str = "none",
    checkpoint_path: Path | str | None = None,
    pause_file: Path | str | None = None,
) -> dict[str, Any]:
    source_root = Path(root).resolve()
    assets = discover_raw_assets(source_root)
    hash_summary = _hash_assets(
        assets,
        hash_mode=hash_mode,
        checkpoint_path=Path(checkpoint_path) if checkpoint_path else None,
        pause_file=Path(pause_file) if pause_file else None,
    )
    exclusions = Counter(asset.exclusionReason or "selected" for asset in assets)
    flags = Counter(flag for asset in assets for flag in asset.flags)
    formats = Counter(asset.fileFormat for asset in assets)
    groups = Counter(asset.sourceGroup for asset in assets)
    return {
        "schemaVersion": CATALOG_SCHEMA_VERSION,
        "rawRoot": str(source_root),
        "generatedAt": _utc_now(),
        "totalFileCount": len(assets),
        "selectedFileCount": sum(asset.selected for asset in assets),
        "totalSizeBytes": sum(asset.sizeBytes for asset in assets),
        "provenanceComplete": all(asset.exchange and asset.provenanceStatus == "verified" for asset in assets if asset.selected),
        "selectionSummary": dict(sorted(exclusions.items())),
        "flagSummary": dict(sorted(flags.items())),
        "formatSummary": dict(sorted(formats.items())),
        "sourceGroupSummary": dict(sorted(groups.items())),
        "hashSummary": hash_summary,
        "assets": [asset.to_dict() for asset in assets],
    }
