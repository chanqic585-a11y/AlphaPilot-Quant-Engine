"""Preregistration-bound checkpoints for resumable validation runs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from alphapilot.data_foundation.checkpoint import write_json_atomic


CHECKPOINT_SCHEMA_VERSION = 1


def save_checkpoint(
    path: Path,
    *,
    preregistration_hash: str,
    completed: Mapping[str, Any],
) -> None:
    """Atomically persist completed candidate results for one locked protocol."""

    if not preregistration_hash:
        raise ValueError("preregistration_hash is required")
    write_json_atomic(
        Path(path),
        {
            "schemaVersion": CHECKPOINT_SCHEMA_VERSION,
            "preregistrationHash": preregistration_hash,
            "completed": dict(completed),
        },
    )


def load_checkpoint(path: Path, *, preregistration_hash: str) -> dict[str, Any]:
    """Load a checkpoint only when it belongs to the expected locked protocol."""

    path = Path(path)
    if not path.is_file():
        return {
            "schemaVersion": CHECKPOINT_SCHEMA_VERSION,
            "preregistrationHash": preregistration_hash,
            "completed": {},
        }
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("checkpoint must be a JSON object")
    if payload.get("preregistrationHash") != preregistration_hash:
        raise ValueError("preregistration hash mismatch")
    completed = payload.get("completed")
    if not isinstance(completed, dict):
        raise ValueError("checkpoint completed field must be an object")
    return payload
