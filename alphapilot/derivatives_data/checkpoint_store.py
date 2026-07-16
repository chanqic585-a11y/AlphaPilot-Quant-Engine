"""Atomic checkpoints and non-destructive existing-partition inspection."""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path
from typing import Any


DEFAULT_COLLECTION_CHECKPOINT: dict[str, Any] = {
    "lastVerifiedCursor": None,
    "complete": False,
    "totalRequestCount": 0,
    "totalDownloadedBytes": 0,
    "totalRetryCount": 0,
    "resumeCount": 0,
}


def load_collection_checkpoint(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return dict(DEFAULT_COLLECTION_CHECKPOINT)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("collection checkpoint must be a JSON object")
    return {**DEFAULT_COLLECTION_CHECKPOINT, **payload}


def write_collection_checkpoint(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".partial")
    normalized = {**DEFAULT_COLLECTION_CHECKPOINT, **payload}
    temporary.write_text(
        json.dumps(normalized, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, path)


def _validate_partition(path: Path) -> tuple[bool, str | None]:
    try:
        if path.suffix.lower() == ".json":
            json.loads(path.read_text(encoding="utf-8"))
        elif path.suffix.lower() == ".csv":
            with path.open("r", encoding="utf-8", newline="") as handle:
                next(csv.reader(handle), None)
        elif path.suffix.lower() == ".parquet" and path.stat().st_size == 0:
            raise ValueError("empty parquet file")
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as error:
        return False, f"{type(error).__name__}: {error}"
    return True, None


def scan_existing_partitions(data_root: Path) -> dict[str, Any]:
    partitions: list[dict[str, Any]] = []
    if data_root.exists():
        for path in sorted(item for item in data_root.rglob("*") if item.is_file()):
            relative = path.relative_to(data_root).as_posix()
            is_partial = path.name.endswith((".partial", ".tmp"))
            valid, validation_error = (False, "partial_file") if is_partial else _validate_partition(path)
            supported = path.suffix.lower() in {".json", ".csv", ".parquet"}
            partitions.append(
                {
                    "path": relative,
                    "bytes": path.stat().st_size,
                    "partial": is_partial,
                    "valid": valid,
                    "supportedFormat": supported,
                    "formalEligible": bool(valid and supported and not is_partial),
                    "validationError": validation_error,
                }
            )
    return {
        "dataRoot": str(data_root),
        "partitionCount": len(partitions),
        "validPartitionCount": sum(1 for row in partitions if row["valid"]),
        "partialFileCount": sum(1 for row in partitions if row["partial"]),
        "formalEligiblePartitionCount": sum(1 for row in partitions if row["formalEligible"]),
        "partitions": partitions,
    }
