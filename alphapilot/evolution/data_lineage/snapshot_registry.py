"""File-level point-in-time snapshot manifests for reproducible research."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from alphapilot.evolution.registry.hashing import sha256_file, stable_hash
from alphapilot.evolution.registry.repositories import RegistryRepository
from alphapilot.evolution.registry.types import DataSnapshotRecord, utc_now


MANIFEST_DERIVED_FIELDS = {"dataSnapshotId", "manifestHash", "createdAt"}


def _manifest_path(path: Path, root: Path | None) -> str:
    resolved = path.resolve()
    if root is None:
        return resolved.as_posix()
    root_resolved = root.resolve()
    try:
        return resolved.relative_to(root_resolved).as_posix()
    except ValueError as exc:
        raise ValueError(f"Snapshot file is outside the declared root: {resolved}") from exc


def build_data_snapshot_manifest(
    *,
    files: Iterable[Path | str],
    source: str,
    exchange: str | None,
    market_type: str | None,
    timeframe: str | None,
    start_time: str | None,
    end_time: str | None,
    point_in_time_cutoff: str | None,
    universe_members: Iterable[str],
    root: Path | str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root_path = Path(root) if root is not None else None
    file_rows: list[dict[str, Any]] = []
    for item in files:
        path = Path(item)
        if not path.is_file():
            raise FileNotFoundError(path)
        file_rows.append(
            {
                "path": _manifest_path(path, root_path),
                "size": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    file_rows.sort(key=lambda item: item["path"])
    core = {
        "schemaVersion": "data_snapshot_manifest_v1",
        "source": source,
        "exchange": exchange,
        "marketType": market_type,
        "timeframe": timeframe,
        "startTime": start_time,
        "endTime": end_time,
        "pointInTimeCutoff": point_in_time_cutoff,
        "universeMembers": sorted({str(item) for item in universe_members}),
        "files": file_rows,
        "metadata": metadata or {},
    }
    manifest_hash = stable_hash(core)
    return {
        **core,
        "dataSnapshotId": f"data_snapshot_{manifest_hash}",
        "manifestHash": manifest_hash,
        "createdAt": utc_now(),
    }


def verify_data_snapshot(
    manifest: dict[str, Any],
    *,
    root: Path | str | None = None,
) -> dict[str, Any]:
    root_path = Path(root).resolve() if root is not None else None
    errors: list[str] = []
    identity_payload = {
        key: value for key, value in manifest.items() if key not in MANIFEST_DERIVED_FIELDS
    }
    try:
        expected_hash = stable_hash(identity_payload)
    except (TypeError, ValueError):
        expected_hash = None
        errors.append("manifest_not_canonical")
    if expected_hash is not None:
        if manifest.get("manifestHash") != expected_hash:
            errors.append("manifest_hash_mismatch")
        if manifest.get("dataSnapshotId") != f"data_snapshot_{expected_hash}":
            errors.append("data_snapshot_id_mismatch")

    files = manifest.get("files", [])
    if not isinstance(files, list):
        errors.append("manifest_files_not_array")
        files = []
    for index, item in enumerate(files):
        if not isinstance(item, dict):
            errors.append(f"invalid_file_entry:{index}")
            continue
        relative = str(item.get("path") or "")
        if root_path is not None:
            path = (root_path / relative).resolve()
            try:
                path.relative_to(root_path)
            except ValueError:
                errors.append(f"outside_root:{relative}")
                continue
        else:
            path = Path(relative)
        if not path.is_file():
            errors.append(f"missing_file:{relative}")
            continue
        if path.stat().st_size != int(item.get("size") or 0):
            errors.append(f"size_mismatch:{relative}")
        if sha256_file(path) != item.get("sha256"):
            errors.append(f"sha256_mismatch:{relative}")
    return {
        "valid": not errors,
        "dataSnapshotId": manifest.get("dataSnapshotId"),
        "checkedFileCount": len(files),
        "errors": errors,
    }


def register_data_snapshot(
    manifest: dict[str, Any],
    repository: RegistryRepository,
) -> DataSnapshotRecord:
    record = DataSnapshotRecord(
        dataSnapshotId=str(manifest["dataSnapshotId"]),
        source=str(manifest["source"]),
        exchange=manifest.get("exchange"),
        marketType=manifest.get("marketType"),
        timeframe=manifest.get("timeframe"),
        startTime=manifest.get("startTime"),
        endTime=manifest.get("endTime"),
        pointInTimeCutoff=manifest.get("pointInTimeCutoff"),
        manifest=manifest,
        contentHash=str(manifest["manifestHash"]),
        createdAt=str(manifest.get("createdAt") or utc_now()),
    )
    return repository.create_data_snapshot(record)
