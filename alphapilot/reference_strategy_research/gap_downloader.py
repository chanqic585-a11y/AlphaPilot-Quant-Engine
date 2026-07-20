"""Bounded, resumable executor for explicit public-data gap plans."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any


def _key(gap: dict[str, Any]) -> str:
    return f"{gap['instrumentId']}::{gap['timeframe']}"


def _write_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def execute_gap_plan(
    *,
    gaps: Sequence[dict[str, Any]],
    checkpoint_path: str | Path,
    fetcher: Callable[[dict[str, Any]], dict[str, Any] | None],
    dry_run: bool = True,
    maximum_requests: int = 20_000,
    maximum_bytes: int = 20 * 1024**3,
    minimum_free_bytes: int = 10 * 1024**3,
) -> dict[str, Any]:
    """Execute only missing partitions and preserve completed hash evidence.

    The caller supplies the public-data fetcher. Dry-run is the default and
    never invokes it. A resumed run skips only artifacts whose stored hash still
    matches, so an interrupted long workflow cannot silently accept corruption.
    """

    checkpoint = Path(checkpoint_path)
    state: dict[str, Any] = {
        "schemaVersion": "reference_gap_download_checkpoint_v1",
        "completed": {},
        "requestCount": 0,
        "bytesWritten": 0,
    }
    if checkpoint.exists():
        loaded = json.loads(checkpoint.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise RuntimeError("invalid gap-download checkpoint")
        state.update(loaded)

    completed = state.setdefault("completed", {})
    pending: list[dict[str, Any]] = []
    for gap in gaps:
        key = _key(gap)
        row = completed.get(key)
        artifact = Path(str((row or {}).get("artifactPath") or ""))
        expected = str((row or {}).get("contentHash") or "")
        if not artifact.is_file() or len(expected) != 64 or _sha256(artifact) != expected:
            pending.append(dict(gap))

    if dry_run:
        return {
            "status": "complete" if not pending else "planned",
            "completedCount": len(gaps) - len(pending),
            "pending": pending,
            "networkCalls": 0,
        }

    for gap in pending:
        if int(state["requestCount"]) >= maximum_requests:
            raise RuntimeError("gap download request budget exceeded")
        if int(state["bytesWritten"]) >= maximum_bytes:
            raise RuntimeError("gap download byte budget exceeded")
        free = shutil.disk_usage(checkpoint.parent.resolve().anchor or checkpoint.parent).free
        if free < minimum_free_bytes:
            raise RuntimeError("gap download free-space guard triggered")
        result = fetcher(dict(gap))
        if not isinstance(result, dict):
            raise RuntimeError("gap fetcher did not return artifact evidence")
        artifact = Path(str(result.get("artifactPath") or ""))
        expected = str(result.get("contentHash") or "")
        requests = int(result.get("requestCount") or 0)
        written = int(result.get("bytesWritten") or 0)
        if not artifact.is_file() or len(expected) != 64 or _sha256(artifact) != expected:
            raise RuntimeError("downloaded gap artifact failed hash verification")
        if requests < 1 or written < 0:
            raise RuntimeError("invalid gap fetch accounting")
        state["requestCount"] = int(state["requestCount"]) + requests
        state["bytesWritten"] = int(state["bytesWritten"]) + written
        if int(state["requestCount"]) > maximum_requests or int(state["bytesWritten"]) > maximum_bytes:
            raise RuntimeError("gap download budget exceeded by fetch result")
        completed[_key(gap)] = {**dict(gap), **result}
        _write_atomic(checkpoint, state)

    return {
        "status": "complete",
        "completedCount": len(gaps),
        "pending": [],
        "networkCalls": int(state["requestCount"]),
        "bytesWritten": int(state["bytesWritten"]),
    }
