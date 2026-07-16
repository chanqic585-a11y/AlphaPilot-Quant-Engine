"""Freeze an audited data-only derivatives snapshot."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from alphapilot.data_foundation.checkpoint import write_json_atomic
from alphapilot.evolution.registry.hashing import stable_hash


REQUIRED_AUDITS = {
    "apiCapability",
    "dataQuality",
    "pitUniverse",
    "familyReadiness",
}


def freeze_data_snapshot(
    *,
    audits: dict[str, Any],
    output_root: Path,
    git_commit: str,
    environment_hash: str,
) -> dict[str, Any]:
    statuses = dict(audits.get("auditStatuses") or {})
    completed = {name for name, status in statuses.items() if status == "completed"}
    if not REQUIRED_AUDITS.issubset(completed):
        missing = sorted(REQUIRED_AUDITS - completed)
        raise ValueError(f"all audits must be completed before freeze: {missing}")
    body = {
        "schemaVersion": "v13_27_1_12_derivatives_data_snapshot_v1",
        "sourceManifestHashes": sorted(audits.get("sourceManifestHashes") or []),
        "normalizedHashes": sorted(audits.get("normalizedHashes") or []),
        "derivedHashes": sorted(audits.get("derivedHashes") or []),
        "pitHash": audits.get("pitHash"),
        "familyReadiness": dict(audits.get("familyReadiness") or {}),
        "createdAt": audits.get("createdAt"),
        "gitCommit": git_commit,
        "environmentManifestHash": environment_hash,
        "auditStatuses": {name: statuses[name] for name in sorted(REQUIRED_AUDITS)},
        "containsStrategyResults": False,
        "containsHoldoutResults": False,
    }
    digest = stable_hash(body)
    snapshot = {
        **body,
        "snapshotId": f"derivatives_data_snapshot_{digest[:20]}",
        "snapshotHash": f"sha256:{digest}",
        "hashVerified": True,
    }
    write_json_atomic(output_root / f"{snapshot['snapshotId']}.json", snapshot)
    return snapshot
