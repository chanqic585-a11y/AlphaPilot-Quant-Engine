"""Read and verify a reference-strategy ZIP without extracting source code."""

from __future__ import annotations

import hashlib
import json
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any


_FORBIDDEN_SUFFIXES = {".apk", ".dll", ".exe", ".ex4", ".ex5"}


def _canonical_hash(payload: dict[str, Any], excluded: str) -> str:
    value = {key: item for key, item in payload.items() if key != excluded}
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _safe_member(name: str) -> PurePosixPath:
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or "\\" in name:
        raise ValueError(f"unsafe archive member: {name}")
    if path.suffix.lower() in _FORBIDDEN_SUFFIXES:
        raise ValueError(f"executable archive member is prohibited: {name}")
    return path


def _decode_json(payload: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(payload.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid JSON in {label}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must contain a JSON object")
    return value


@dataclass(frozen=True)
class ReferenceStrategyPackage:
    archivePath: str
    archiveSha256: str
    manifest: dict[str, Any]
    candidateSet: dict[str, Any]
    candidates: tuple[dict[str, Any], ...]
    sourceFilesLoaded: bool = False


def load_reference_package(path: str | Path) -> ReferenceStrategyPackage:
    """Verify package identity and return metadata only.

    Listed files are hashed in memory. No member is extracted and no source file
    is imported or executed.
    """

    archive_path = Path(path).resolve()
    if not archive_path.is_file():
        raise FileNotFoundError(archive_path)
    archive_hash = hashlib.sha256(archive_path.read_bytes()).hexdigest()

    with zipfile.ZipFile(archive_path) as archive:
        members = {_safe_member(item.filename): item for item in archive.infolist()}
        manifest_paths = [item for item in members if item.name == "package_manifest.json"]
        if len(manifest_paths) != 1:
            raise ValueError("archive must contain exactly one package_manifest.json")
        manifest_path = manifest_paths[0]
        root = manifest_path.parent
        manifest = _decode_json(archive.read(members[manifest_path]), str(manifest_path))
        if manifest.get("schemaVersion") != "alphapilot_reference_strategy_package_manifest_v1":
            raise ValueError("unsupported package manifest schema")
        if manifest.get("manifestHash") != _canonical_hash(manifest, "manifestHash"):
            raise ValueError("manifest hash mismatch")

        file_rows = manifest.get("files")
        if not isinstance(file_rows, list) or manifest.get("fileCount") != len(file_rows):
            raise ValueError("manifest file count mismatch")
        verified: dict[str, bytes] = {}
        for row in file_rows:
            if not isinstance(row, dict):
                raise ValueError("manifest file entry must be an object")
            relative = _safe_member(str(row.get("path") or ""))
            member_path = root / relative
            if member_path not in members:
                raise ValueError(f"manifest file missing: {relative}")
            payload = archive.read(members[member_path])
            if row.get("sha256") != hashlib.sha256(payload).hexdigest():
                raise ValueError(f"file hash mismatch: {relative}")
            if row.get("sizeBytes") != len(payload):
                raise ValueError(f"file size mismatch: {relative}")
            verified[relative.as_posix()] = payload

        candidate_key = "candidates/candidate_specs.json"
        if candidate_key not in verified:
            raise ValueError("candidate_specs.json is not listed in the manifest")
        candidate_set = _decode_json(verified[candidate_key], candidate_key)
        if candidate_set.get("schemaVersion") != "alphapilot_reference_strategy_candidate_set_v1":
            raise ValueError("unsupported candidate-set schema")
        candidates = candidate_set.get("candidates")
        if not isinstance(candidates, list):
            raise ValueError("candidate set must contain a candidates list")
        if candidate_set.get("candidateCount") != len(candidates):
            raise ValueError("candidate-set count mismatch")
        if manifest.get("candidateCount") != len(candidates):
            raise ValueError("manifest candidate count mismatch")
        if candidate_set.get("sourceArchiveSha256") != manifest.get("sourceArchiveSha256"):
            raise ValueError("source archive identity mismatch")
        for candidate in candidates:
            if not isinstance(candidate, dict):
                raise ValueError("candidate entry must be an object")
            expected = _canonical_hash(candidate, "candidateSpecHash")
            if candidate.get("candidateSpecHash") != expected:
                raise ValueError(f"candidate hash mismatch: {candidate.get('candidateId')}")

    return ReferenceStrategyPackage(
        archivePath=str(archive_path),
        archiveSha256=archive_hash,
        manifest=manifest,
        candidateSet=candidate_set,
        candidates=tuple(dict(row) for row in candidates),
    )
