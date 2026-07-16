"""Inventory files and resolve references before any storage cleanup."""

from __future__ import annotations

import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable, Iterator

from alphapilot.evolution.registry.hashing import sha256_file


TEXT_SUFFIXES = {".json", ".md", ".txt", ".sha256", ".yaml", ".yml", ".toml", ".py", ".ps1"}
IMMUTABLE_MARKERS = ("release", "formal", "evidence", "prereg", "snapshot")
ABSOLUTE_PATH_RE = re.compile(
    r"[A-Za-z]:[\\/][^\"'\r\n<>|]*?\.(?:parquet|csv|xlsx|json|md|sha256)",
    re.IGNORECASE,
)
RELATIVE_PATH_RE = re.compile(
    r"_alphapilot[\\/][^\"'\r\n<>|]*?\.(?:parquet|csv|xlsx|json|md|sha256)",
    re.IGNORECASE,
)
SHA256_RE = re.compile(r"(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])", re.IGNORECASE)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _load_hash_cache(path: Path | None) -> dict[str, Any]:
    if not path or not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    files = payload.get("files")
    return files if isinstance(files, dict) else {}


def _write_hash_cache(path: Path | None, files: dict[str, Any]) -> None:
    if not path:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(
            {"schemaVersion": "storage_hash_cache_v1", "updatedAt": _utc_now(), "files": files},
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _inventory(data_root: Path, hash_cache_path: Path | None) -> list[dict[str, Any]]:
    cached = _load_hash_cache(hash_cache_path)
    updated: dict[str, Any] = {}
    rows: list[dict[str, Any]] = []
    dirty = 0
    for path in sorted(item for item in data_root.rglob("*") if item.is_file()):
        resolved = path.resolve()
        relative = resolved.relative_to(data_root).as_posix()
        stat = path.stat()
        cache_row = cached.get(relative)
        if (
            isinstance(cache_row, dict)
            and cache_row.get("sizeBytes") == stat.st_size
            and cache_row.get("modifiedAtNs") == stat.st_mtime_ns
            and cache_row.get("sha256")
        ):
            digest = str(cache_row["sha256"])
        else:
            digest = sha256_file(path)
            dirty += 1
        updated[relative] = {
            "sizeBytes": stat.st_size,
            "modifiedAtNs": stat.st_mtime_ns,
            "sha256": digest,
        }
        rows.append(
            {
                "path": str(resolved),
                "relativePath": relative,
                "sha256": digest,
                "sizeBytes": stat.st_size,
                "modifiedAtNs": stat.st_mtime_ns,
                "referencedBy": [],
                "referenceCount": 0,
                "immutableEvidence": False,
                "safeToRemove": False,
            }
        )
        if dirty >= 100:
            _write_hash_cache(hash_cache_path, updated)
            dirty = 0
    _write_hash_cache(hash_cache_path, updated)
    return rows


def _document_chunks(path: Path, chunk_size: int = 4 * 1024 * 1024) -> Iterator[str]:
    overlap = ""
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            while chunk := handle.read(chunk_size):
                text = overlap + chunk
                yield text
                overlap = text[-4096:]
    except OSError:
        return


def _references_from_text(text: str, data_root: Path) -> tuple[set[str], set[str]]:
    normalized = text.replace("\\\\", "\\")
    paths: set[str] = set()
    for match in ABSOLUTE_PATH_RE.findall(normalized):
        candidate = Path(match.replace("/", "\\"))
        if _inside(candidate, data_root):
            paths.add(str(candidate.resolve()).casefold())
    for match in RELATIVE_PATH_RE.findall(normalized):
        candidate = data_root / Path(match.replace("\\", "/"))
        if _inside(candidate, data_root):
            paths.add(str(candidate.resolve()).casefold())
    return paths, {value.casefold() for value in SHA256_RE.findall(normalized)}


def _default_data_reference_documents(data_root: Path) -> list[Path]:
    documents: list[Path] = []
    for relative in ("_alphapilot/manifests", "_alphapilot/reports"):
        root = data_root / relative
        if root.exists():
            documents.extend(
                path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES
            )
    documents.extend(path for path in data_root.rglob("*.sha256") if path.is_file())
    return sorted(set(documents))


def _tracked_reference_documents(repository: Path) -> list[Path]:
    completed = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=repository,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        return []
    paths: list[Path] = []
    for raw in completed.stdout.split(b"\0"):
        if not raw:
            continue
        relative = raw.decode("utf-8", errors="ignore")
        path = repository / relative
        if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES:
            paths.append(path)
    return paths


def _git_tag_reference_texts(repository: Path) -> Iterator[tuple[str, str]]:
    tags = subprocess.run(
        ["git", "tag", "--list"],
        cwd=repository,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="ignore",
        check=False,
    )
    if tags.returncode != 0:
        return
    pattern = r"回测数据|_alphapilot|\.parquet|\.xlsx|\.sha256"
    for tag in sorted(filter(None, tags.stdout.splitlines())):
        result = subprocess.run(
            ["git", "grep", "-I", "-h", "-E", pattern, tag, "--", "reports", "research", "docs", "README.md"],
            cwd=repository,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            check=False,
        )
        if result.returncode in {0, 1} and result.stdout:
            yield f"git-tag:{repository.name}:{tag}", result.stdout


def _immutable_source(label: str) -> bool:
    lowered = label.casefold()
    return any(marker in lowered for marker in IMMUTABLE_MARKERS)


def build_reference_graph(
    data_root: Path | str,
    *,
    reference_documents: Iterable[Path | str] = (),
    repository_roots: Iterable[Path | str] = (),
    hash_cache_path: Path | str | None = None,
) -> dict[str, Any]:
    root = Path(data_root).resolve()
    if not root.is_dir():
        raise FileNotFoundError(root)
    rows = _inventory(root, Path(hash_cache_path) if hash_cache_path else None)
    by_path = {str(Path(row["path"]).resolve()).casefold(): row for row in rows}
    by_sha: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_sha.setdefault(str(row["sha256"]).casefold(), []).append(row)

    def record(label: str, text: str) -> None:
        referenced_paths, referenced_hashes = _references_from_text(text, root)
        targets = [by_path[value] for value in referenced_paths if value in by_path]
        for digest in referenced_hashes:
            targets.extend(by_sha.get(digest, []))
        for target in targets:
            if label not in target["referencedBy"]:
                target["referencedBy"].append(label)
            if _immutable_source(label):
                target["immutableEvidence"] = True

    documents = set(_default_data_reference_documents(root))
    documents.update(Path(value).resolve() for value in reference_documents)
    repositories = [Path(value).resolve() for value in repository_roots]
    for repository in repositories:
        documents.update(_tracked_reference_documents(repository))
    for document in sorted(documents):
        for chunk in _document_chunks(document):
            record(str(document), chunk)
        if document.suffix.lower() == ".sha256":
            adjacent = document.with_suffix("")
            target = by_path.get(str(adjacent.resolve()).casefold())
            if target:
                label = f"sidecar:{document}"
                if label not in target["referencedBy"]:
                    target["referencedBy"].append(label)
    for repository in repositories:
        for label, text in _git_tag_reference_texts(repository):
            record(label, text)
    for row in rows:
        row["referencedBy"] = sorted(row["referencedBy"])
        row["referenceCount"] = len(row["referencedBy"])
        row["safeToRemove"] = False
    return {
        "schemaVersion": "storage_reference_graph_v1",
        "dataRoot": str(root),
        "generatedAt": _utc_now(),
        "fileCount": len(rows),
        "referencedFileCount": sum(row["referenceCount"] > 0 for row in rows),
        "immutableEvidenceFileCount": sum(row["immutableEvidence"] for row in rows),
        "files": rows,
    }
