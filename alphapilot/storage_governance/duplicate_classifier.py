"""Classify duplicates by hashes and verified tabular content."""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

from .retention_policy import choose_authoritative_record


ROLLING_NAME_RE = re.compile(r"^(?P<start>\d+)-(?P<end>\d+)-[^.]+\.parquet$", re.IGNORECASE)


def _record_map(graph: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(Path(row["path"]).resolve()): dict(row) for row in graph.get("files", [])}


def _coverage(path: Path) -> tuple[int, int]:
    match = ROLLING_NAME_RE.match(path.name)
    if not match:
        return (0, 0)
    return (int(match.group("start")), int(match.group("end")))


def _table_profile(path: Path) -> tuple[pd.DataFrame, str]:
    frame = pd.read_parquet(path)
    key = next((name for name in ("timestamp_ms", "date", "timestampUtc", "fundingTime") if name in frame.columns), "")
    if not key:
        raise ValueError(f"no causal timestamp column: {path}")
    ordered = frame.sort_values(key).drop_duplicates(key, keep="last").reset_index(drop=True)
    return ordered, key


def _contained_exactly(candidate: Path, authority: Path) -> bool:
    try:
        old, old_key = _table_profile(candidate)
        latest, latest_key = _table_profile(authority)
    except (OSError, ValueError, TypeError):
        return False
    if old_key != latest_key or list(old.columns) != list(latest.columns) or old.empty:
        return False
    start, end = old[old_key].iloc[0], old[old_key].iloc[-1]
    selected = latest.loc[latest[latest_key].between(start, end)].reset_index(drop=True)
    return len(selected) == len(old) and selected.equals(old)


def classify_duplicates(graph: Mapping[str, Any], *, data_root: Path | str) -> dict[str, Any]:
    root = Path(data_root).resolve()
    records = _record_map(graph)
    groups: list[dict[str, Any]] = []
    assigned: set[str] = set()

    by_hash: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in records.values():
        by_hash[str(row.get("sha256") or "")].append(row)
    for digest, rows in sorted(by_hash.items()):
        if not digest or len(rows) < 2:
            continue
        authority = choose_authoritative_record(rows)
        members = sorted(str(Path(row["path"]).resolve()) for row in rows)
        groups.append(
            {
                "duplicateClass": "byte_identical",
                "identity": f"sha256:{digest}",
                "authoritativePath": str(Path(authority["path"]).resolve()),
                "authoritativeSha256": digest,
                "members": members,
                "contentVerified": True,
            }
        )
        assigned.update(members)

    canonical_root = root / "_alphapilot" / "canonical"
    by_identity: dict[Path, list[Path]] = defaultdict(list)
    if canonical_root.exists():
        for path in canonical_root.rglob("*.parquet"):
            by_identity[path.parent.resolve()].append(path.resolve())
    for identity, paths in sorted(by_identity.items(), key=lambda item: str(item[0])):
        candidates = [path for path in paths if str(path) not in assigned]
        if len(candidates) < 2:
            continue
        enriched = []
        for path in candidates:
            row = dict(records[str(path)])
            start, end = _coverage(path)
            row["coverageStart"] = start
            row["coverageEnd"] = end
            enriched.append(row)
        authority_row = choose_authoritative_record(enriched)
        authority = Path(str(authority_row["path"])).resolve()
        superseded: list[str] = []
        conflicts: list[str] = []
        for path in sorted(candidates):
            if path == authority:
                continue
            if _contained_exactly(path, authority):
                superseded.append(str(path))
            else:
                conflicts.append(str(path))
        if superseded:
            groups.append(
                {
                    "duplicateClass": "rolling_snapshot_superseded",
                    "identity": str(identity.relative_to(root)).replace("\\", "/"),
                    "authoritativePath": str(authority),
                    "authoritativeSha256": records[str(authority)]["sha256"],
                    "members": superseded,
                    "contentVerified": True,
                }
            )
            assigned.update(superseded)
        if conflicts:
            groups.append(
                {
                    "duplicateClass": "conflicting",
                    "identity": str(identity.relative_to(root)).replace("\\", "/"),
                    "authoritativePath": str(authority),
                    "authoritativeSha256": records[str(authority)]["sha256"],
                    "members": conflicts,
                    "contentVerified": False,
                }
            )
            assigned.update(conflicts)

    raw_representation_groups: dict[str, list[str]] = defaultdict(list)
    for path_text in records:
        path = Path(path_text)
        name = path.name.upper()
        if path.suffix.lower() == ".xlsx" and ("_ALL" in name or re.search(r"_20\d{2}", name)):
            identity = re.sub(r"_(?:ALL|20\d{2})(?:_\d{8}_\d{6})?\.XLSX$", "", name)
            raw_representation_groups[str(path.parent / identity)].append(path_text)
    for identity, members in sorted(raw_representation_groups.items()):
        if len(members) < 2:
            continue
        groups.append(
            {
                "duplicateClass": "annual_vs_all_representation",
                "identity": identity,
                "authoritativePath": None,
                "authoritativeSha256": None,
                "members": sorted(members),
                "contentVerified": False,
                "reason": "requires full continuity and row-equivalence proof before cleanup",
            }
        )
    return {
        "schemaVersion": "storage_duplicate_groups_v1",
        "dataRoot": str(root),
        "groupCount": len(groups),
        "groups": groups,
        "uniqueFileCount": max(0, len(records) - len(assigned)),
    }
