"""Verify and apply an explicitly authorized storage cleanup plan."""

from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

from alphapilot.evolution.registry.hashing import sha256_file

from .duplicate_classifier import _contained_exactly
from .retention_policy import duplicate_class_is_safe


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _has_reparse_component(path: Path, root: Path) -> bool:
    current = root.resolve()
    relative = path.resolve().relative_to(current)
    for part in relative.parts:
        current = current / part
        if not current.exists():
            continue
        stat = current.lstat()
        attributes = getattr(stat, "st_file_attributes", 0)
        if current.is_symlink() or attributes & getattr(os, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400):
            return True
    return False


def _verify_item(item: Mapping[str, Any], root: Path) -> dict[str, Any]:
    path = Path(str(item["path"]))
    authority = Path(str(item["authoritativePath"]))
    if not _inside(path, root) or not _inside(authority, root):
        raise ValueError("cleanup path outside authorized data root")
    if path.resolve() == authority.resolve():
        raise ValueError("candidate cannot be its own authoritative copy")
    if _has_reparse_component(path, root) or _has_reparse_component(authority, root):
        raise ValueError("cleanup path contains a reparse point")
    if int(item.get("referenceCount") or 0) != 0 or bool(item.get("immutableEvidence")):
        raise ValueError("referenced or immutable evidence cannot be removed")
    duplicate_class = str(item.get("duplicateClass") or "")
    if not duplicate_class_is_safe(duplicate_class) or not bool(item.get("contentVerified")):
        raise ValueError("duplicate class is not verified safe")
    if not path.is_file() or not authority.is_file():
        raise FileNotFoundError(path if not path.is_file() else authority)
    current_sha = sha256_file(path)
    authority_sha = sha256_file(authority)
    if current_sha != item.get("sha256"):
        raise ValueError("candidate hash changed after planning")
    if authority_sha != item.get("authoritativeSha256"):
        raise ValueError("authoritative copy hash changed after planning")
    if duplicate_class == "byte_identical" and current_sha != authority_sha:
        raise ValueError("byte-identical candidate no longer matches authority")
    if duplicate_class in {"content_equivalent", "rolling_snapshot_superseded"} and not _contained_exactly(path, authority):
        raise ValueError("tabular content is no longer contained by authority")
    return {
        "path": str(path.resolve()),
        "sha256": current_sha,
        "sizeBytes": path.stat().st_size,
        "duplicateClass": duplicate_class,
        "authoritativePath": str(authority.resolve()),
        "authoritativeSha256": authority_sha,
    }


def execute_cleanup(
    plan: Mapping[str, Any],
    *,
    data_root: Path | str,
    apply_cleanup: bool,
) -> dict[str, Any]:
    root = Path(data_root).resolve()
    if not root.is_dir():
        raise FileNotFoundError(root)
    planned_root = Path(str(plan.get("dataRoot") or "")).resolve()
    if planned_root != root:
        raise ValueError("plan data root does not match authorized data root")
    verified = [_verify_item(item, root) for item in plan.get("candidates", [])]
    deleted: list[dict[str, Any]] = []
    if apply_cleanup:
        for row in verified:
            Path(row["path"]).unlink()
            deleted.append(row)
    return {
        "schemaVersion": "storage_cleanup_apply_manifest_v1",
        "generatedAt": datetime.now(UTC).isoformat(),
        "dataRoot": str(root),
        "applyCleanup": bool(apply_cleanup),
        "verifiedCandidateCount": len(verified),
        "deletedFileCount": len(deleted),
        "reclaimedBytes": sum(int(row["sizeBytes"]) for row in deleted),
        "verifiedCandidates": verified,
        "deletedFiles": deleted,
    }


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", required=True)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--apply-cleanup", action="store_true")
    args = parser.parse_args()
    plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    result = execute_cleanup(plan, data_root=Path(args.data_root), apply_cleanup=args.apply_cleanup)
    output = Path(args.output_root)
    _write_json(output / "cleanup_apply_manifest.json", result)
    integrity = {
        "schemaVersion": "storage_cleanup_integrity_check_v1",
        "dataRoot": result["dataRoot"],
        "allDeletedPathsInsideAuthorizedRoot": all(_inside(Path(row["path"]), Path(result["dataRoot"])) for row in result["deletedFiles"]),
        "allAuthoritativeCopiesRemain": all(Path(row["authoritativePath"]).is_file() for row in result["deletedFiles"]),
        "deletedFileCount": result["deletedFileCount"],
        "status": "passed",
    }
    _write_json(output / "cleanup_integrity_check.json", integrity)
    print(json.dumps({"deletedFileCount": result["deletedFileCount"], "reclaimedBytes": result["reclaimedBytes"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
