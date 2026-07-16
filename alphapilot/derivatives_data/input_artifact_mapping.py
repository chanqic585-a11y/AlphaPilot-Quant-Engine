"""Deterministic mapping of V13.27.1.11 evidence into V13.27.1.12 roles."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _shape(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _shape(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        shapes = {_canonical(_shape(item)) for item in value}
        return {"type": "array", "itemShapes": sorted(shapes)}
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    return "string"


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _schema_fingerprint(path: Path) -> str:
    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        shape = _shape(payload)
    else:
        shape = {"extension": path.suffix.lower(), "mediaType": "text/markdown"}
    return hashlib.sha256(_canonical(shape).encode("utf-8")).hexdigest()


def map_required_artifacts(
    *,
    repo_root: Path,
    role_candidates: Mapping[str, Sequence[str]],
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    blocked = False
    for logical_role, candidates in sorted(role_candidates.items()):
        normalized = sorted(dict.fromkeys(str(candidate).replace("\\", "/") for candidate in candidates))
        existing = [candidate for candidate in normalized if (repo_root / candidate).is_file()]
        if len(existing) == 1:
            selected = existing[0]
            path = repo_root / selected
            row = {
                "logicalRole": logical_role,
                "actualPath": selected,
                "exists": True,
                "contentHash": _sha256(path),
                "schemaFingerprint": _schema_fingerprint(path),
                "selectedBy": "single_existing_candidate",
                "selectionReason": "exactly one declared candidate exists",
                "ambiguousCandidates": [],
            }
        else:
            blocked = True
            row = {
                "logicalRole": logical_role,
                "actualPath": None,
                "exists": False,
                "contentHash": None,
                "schemaFingerprint": None,
                "selectedBy": "none" if not existing else "ambiguous",
                "selectionReason": "required input missing" if not existing else "multiple declared candidates exist",
                "ambiguousCandidates": existing,
            }
        rows.append(row)
    return {
        "schemaVersion": "v13_27_1_12_input_artifact_mapping_v1",
        "status": "blocked_input_mapping" if blocked else "mapped",
        "artifacts": rows,
    }

