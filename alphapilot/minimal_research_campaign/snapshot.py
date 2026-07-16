"""Manifest-only shared snapshot construction."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from alphapilot.evolution.registry.hashing import stable_hash


def build_snapshot_manifest(
    core_universe: Mapping[str, Any],
    dataset_references: Sequence[Mapping[str, Any]],
    *,
    git_commit: str,
) -> dict[str, Any]:
    references = [
        dict(row)
        for row in sorted(
            dataset_references,
            key=lambda item: (
                str(item.get("instrumentId")),
                str(item.get("timeframe")),
                str(item.get("path")),
            ),
        )
    ]
    effective_starts: dict[str, dict[str, str]] = {}
    for row in references:
        instrument_id = str(row["instrumentId"])
        timeframe = str(row["timeframe"])
        effective_starts.setdefault(instrument_id, {})[timeframe] = str(
            row["effectiveBacktestStart"]
        )
    core = {
        "schemaVersion": "minimal_manifest_only_snapshot_v1",
        "storageMode": "manifest_only",
        "physicalCopiesCreated": 0,
        "coreUniverseHash": str(core_universe["coreUniverseHash"]),
        "datasetReferences": references,
        "fileHashes": {str(row["path"]): str(row["sha256"]) for row in references},
        "commonCutoffByTimeframe": dict(core_universe.get("commonCutoffByTimeframe") or {}),
        "effectiveStarts": effective_starts,
        "gitCommit": git_commit,
    }
    snapshot_hash = stable_hash(core, prefix="minimal_shared_snapshot")
    snapshot_digest = snapshot_hash.rsplit("_", 1)[-1]
    return {
        **core,
        "snapshotId": f"minimal_snapshot_{snapshot_digest[:24]}",
        "snapshotHash": snapshot_hash,
    }
