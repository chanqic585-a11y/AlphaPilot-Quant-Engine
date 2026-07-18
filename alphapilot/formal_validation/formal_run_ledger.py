"""Atomic one-shot claim ledger for the V18 formal campaign."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from alphapilot.data_foundation.checkpoint import write_json_atomic


class FormalRunClaimError(RuntimeError):
    """Raised when a formal window would be claimed more than once."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _identity(value: Mapping[str, Any]) -> dict[str, str]:
    required = ("codeCommit", "preregistrationHash", "inputSnapshotHash")
    normalized = {key: str(value.get(key) or "") for key in required}
    if any(not normalized[key] for key in required):
        raise ValueError("formal run identity is incomplete")
    return normalized


def _read(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise FormalRunClaimError("formal run ledger is invalid")
    return payload


def claim_formal_run(
    path: Path,
    *,
    run_id: str,
    identity: Mapping[str, Any],
    checkpoint: Mapping[str, Any] | None = None,
    resume_checkpoint: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Create one claim atomically, or resume its exact deterministic checkpoint."""

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    normalized_identity = _identity(identity)
    payload: dict[str, Any] = {
        "schemaVersion": "s01_v18_atomic_run_ledger_v1",
        "runId": str(run_id),
        "identity": normalized_identity,
        "state": "running",
        "attemptCount": 1,
        "checkpoint": dict(checkpoint) if checkpoint is not None else None,
        "claimedAt": _utc_now(),
        "resumed": False,
    }
    encoded = (json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode(
        "utf-8"
    )
    try:
        descriptor = os.open(
            destination,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
    except FileExistsError:
        existing = _read(destination)
        if existing.get("state") in {"completed", "failed"}:
            raise FormalRunClaimError("formal run ledger is terminal")
        if existing.get("state") != "running":
            raise FormalRunClaimError("formal run ledger state is invalid")
        if existing.get("runId") != str(run_id) or existing.get("identity") != normalized_identity:
            raise FormalRunClaimError("formal run claim identity mismatch")
        expected = existing.get("checkpoint")
        supplied = dict(resume_checkpoint) if resume_checkpoint is not None else None
        if (
            not isinstance(expected, dict)
            or expected.get("deterministic") is not True
            or supplied != expected
        ):
            raise FormalRunClaimError(
                "resume requires an identical deterministic checkpoint"
            )
        return {**existing, "resumed": True}
    else:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        return payload


def complete_formal_run(
    path: Path,
    *,
    run_id: str,
    identity: Mapping[str, Any],
    result_manifest_hash: str,
) -> dict[str, Any]:
    payload = _read(Path(path))
    if payload.get("state") != "running":
        raise FormalRunClaimError("formal run ledger is terminal")
    if payload.get("runId") != str(run_id) or payload.get("identity") != _identity(identity):
        raise FormalRunClaimError("formal run completion identity mismatch")
    completed = {
        **payload,
        "state": "completed",
        "resultManifestHash": str(result_manifest_hash),
        "completedAt": _utc_now(),
        "resumed": False,
    }
    write_json_atomic(Path(path), completed)
    return completed


def fail_formal_run(
    path: Path,
    *,
    run_id: str,
    identity: Mapping[str, Any],
    reason: str,
) -> dict[str, Any]:
    """Close a claimed formal run permanently without recording sensitive details."""

    payload = _read(Path(path))
    if payload.get("state") != "running":
        raise FormalRunClaimError("formal run ledger is terminal")
    if payload.get("runId") != str(run_id) or payload.get("identity") != _identity(identity):
        raise FormalRunClaimError("formal run failure identity mismatch")
    failed = {
        **payload,
        "state": "failed",
        "failureReason": str(reason),
        "failedAt": _utc_now(),
        "resumed": False,
    }
    write_json_atomic(Path(path), failed)
    return failed
