"""Metadata-first ingestion for readable and opaque research sources."""

from __future__ import annotations

import zipfile
from dataclasses import dataclass
from pathlib import Path

from alphapilot.evolution.registry.hashing import sha256_file


@dataclass(frozen=True)
class SourceIngestResult:
    sourcePath: str
    sourceHash: str
    sourceType: str
    metadataOnly: bool
    formulaExtractionAllowed: bool
    archiveMembers: tuple[str, ...] = ()


_READABLE_TYPES = {
    ".pdf": "document",
    ".md": "document",
    ".html": "document",
    ".htm": "document",
    ".mq4": "executable_source",
    ".mq5": "executable_source",
    ".py": "executable_source",
    ".set": "parameter_file",
    ".json": "api_or_research_document",
}


def ingest_source(path: Path) -> SourceIngestResult:
    target = Path(path).resolve()
    if not target.is_file():
        raise FileNotFoundError(target)
    suffix = target.suffix.lower()
    if suffix in {".ex4", ".ex5"}:
        source_type = "compiled_black_box"
        metadata_only = True
        extractable = False
    elif suffix == ".zip":
        source_type = "reference_archive"
        metadata_only = True
        extractable = False
    else:
        source_type = _READABLE_TYPES.get(suffix, "unknown")
        metadata_only = source_type == "unknown"
        extractable = source_type in {
            "document",
            "executable_source",
            "api_or_research_document",
        }
    members: tuple[str, ...] = ()
    if suffix == ".zip":
        with zipfile.ZipFile(target) as archive:
            members = tuple(sorted(item.filename for item in archive.infolist()))
    return SourceIngestResult(
        sourcePath=target.as_posix(),
        sourceHash=sha256_file(target),
        sourceType=source_type,
        metadataOnly=metadata_only,
        formulaExtractionAllowed=extractable,
        archiveMembers=members,
    )
