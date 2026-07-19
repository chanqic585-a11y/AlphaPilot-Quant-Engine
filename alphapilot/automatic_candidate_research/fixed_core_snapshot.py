"""Build a hash-verified snapshot manifest from the frozen fixed-core cohort."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Sequence

from alphapilot.evolution.registry.hashing import stable_hash

from .contracts import V36ContractError


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build_fixed_core_snapshot_manifest(
    *,
    core_universe_path: Path,
    data_root: Path,
    output_path: Path,
    timeframes: Sequence[str] = ("1h",),
) -> dict[str, Any]:
    """Reference existing canonical files without copying or claiming PIT history."""

    core_path = Path(core_universe_path).resolve()
    root = Path(data_root).resolve()
    if not core_path.is_file():
        raise V36ContractError("fixed_core_universe_missing")
    payload = json.loads(core_path.read_text(encoding="utf-8-sig"))
    if payload.get("cohortType") != "fixed_core_cohort":
        raise V36ContractError("fixed_core_cohort_type_invalid")
    if payload.get("historicalPitUniverse") is not False:
        raise V36ContractError("fixed_core_pit_boundary_missing")
    requested = tuple(dict.fromkeys(str(value) for value in timeframes))
    if not requested:
        raise V36ContractError("fixed_core_timeframes_missing")

    partitions: list[dict[str, Any]] = []
    for member in payload.get("members") or []:
        instrument_id = str(member.get("instrumentId") or "")
        profiles = member.get("profiles") or {}
        if not instrument_id:
            raise V36ContractError("fixed_core_instrument_missing")
        for timeframe in requested:
            profile = profiles.get(timeframe)
            if not isinstance(profile, dict):
                raise V36ContractError(
                    f"fixed_core_profile_missing:{instrument_id}:{timeframe}"
                )
            partition_path = (root / str(profile.get("filePath") or "")).resolve()
            try:
                partition_path.relative_to(root)
            except ValueError as exc:
                raise V36ContractError("fixed_core_partition_outside_data_root") from exc
            if not partition_path.is_file():
                raise V36ContractError(
                    f"fixed_core_partition_missing:{instrument_id}:{timeframe}"
                )
            actual_hash = _sha256(partition_path)
            if actual_hash != str(profile.get("sha256") or ""):
                raise V36ContractError(
                    f"fixed_core_partition_hash_mismatch:{instrument_id}:{timeframe}"
                )
            partitions.append(
                {
                    "instrumentId": instrument_id,
                    "timeframe": timeframe,
                    "outputPath": str(partition_path),
                    "outputSha256": actual_hash,
                    "rowCount": int(profile.get("rowCount") or 0),
                    "provenanceStatus": str(profile.get("provenanceStatus") or ""),
                }
            )

    identity = {
        "coreUniverseHash": str(payload.get("coreUniverseHash") or ""),
        "timeframes": list(requested),
        "partitions": [
            {
                "instrumentId": row["instrumentId"],
                "timeframe": row["timeframe"],
                "outputSha256": row["outputSha256"],
            }
            for row in partitions
        ],
    }
    manifest = {
        "schemaVersion": "v36_fixed_core_snapshot_manifest_v1",
        "snapshotId": stable_hash(identity, prefix="fixed_core_snapshot"),
        "status": "completed",
        "cohortType": "fixed_core_cohort",
        "historicalPitUniverse": False,
        "crossSectionalUse": "not_claimed",
        "sourceCoreUniversePath": str(core_path),
        "sourceCoreUniverseHash": str(payload.get("coreUniverseHash") or ""),
        "partitionCount": len(partitions),
        "partitions": partitions,
    }
    destination = Path(output_path).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(destination)
    return manifest
