"""Index and lazily validate reusable OKX official OHLCV partitions."""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from alphapilot.evolution.registry.hashing import sha256_file


OFFICIAL_PARTITION_SCHEMA_VERSION = "okx_official_partition_manifest_v1"


@dataclass(frozen=True)
class IndexedOfficialPartition:
    instrumentId: str
    timeframe: str
    rows: int
    startTime: str
    endTime: str
    outputPath: str
    outputSha256: str
    sourceEndpoint: str
    manifestCount: int


@dataclass(frozen=True)
class _ManifestCandidate:
    instrument_id: str
    timeframe: str
    rows: int
    start_time: str
    end_time: str
    output_path: str
    output_sha256: str
    source_endpoint: str


class OfficialPartitionIndex:
    """Load manifest metadata once and hash only requested candidates."""

    def __init__(
        self,
        *,
        canonical_root: Path,
        candidates: dict[tuple[str, str, str], tuple[_ManifestCandidate, ...]],
    ) -> None:
        self._canonical_root = canonical_root.resolve()
        self._candidates = candidates

    @classmethod
    def from_manifests(
        cls,
        manifest_root: Path,
        canonical_root: Path,
    ) -> "OfficialPartitionIndex":
        grouped: dict[tuple[str, str, str], list[_ManifestCandidate]] = defaultdict(list)
        for manifest_path in manifest_root.glob("*.json"):
            try:
                row = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, ValueError, TypeError):
                continue
            if row.get("schemaVersion") != OFFICIAL_PARTITION_SCHEMA_VERSION:
                continue
            values = {
                "instrument_id": str(row.get("instrumentId") or ""),
                "timeframe": str(row.get("timeframe") or ""),
                "source_endpoint": str(row.get("sourceEndpoint") or ""),
                "start_time": str(row.get("startTime") or ""),
                "end_time": str(row.get("endTime") or ""),
                "output_path": str(row.get("outputPath") or ""),
                "output_sha256": str(row.get("outputSha256") or ""),
            }
            if not all(values.values()):
                continue
            try:
                rows = int(row.get("rows") or 0)
            except (TypeError, ValueError):
                continue
            if rows <= 0:
                continue
            candidate = _ManifestCandidate(rows=rows, **values)
            grouped[
                (
                    candidate.instrument_id,
                    candidate.timeframe,
                    candidate.source_endpoint,
                )
            ].append(candidate)
        ordered = {
            key: tuple(sorted(rows, key=lambda item: item.end_time, reverse=True))
            for key, rows in grouped.items()
        }
        return cls(canonical_root=canonical_root, candidates=ordered)

    def latest_valid(
        self,
        instrument_id: str,
        timeframe: str,
        endpoint: str,
    ) -> IndexedOfficialPartition | None:
        candidates = self._candidates.get((instrument_id, timeframe, endpoint), ())
        for candidate in candidates:
            output = Path(candidate.output_path)
            try:
                inside_canonical_root = output.resolve().is_relative_to(
                    self._canonical_root
                )
            except (OSError, ValueError):
                inside_canonical_root = False
            if (
                not inside_canonical_root
                or not output.is_file()
                or sha256_file(output) != candidate.output_sha256
            ):
                continue
            return IndexedOfficialPartition(
                instrumentId=candidate.instrument_id,
                timeframe=candidate.timeframe,
                rows=candidate.rows,
                startTime=candidate.start_time,
                endTime=candidate.end_time,
                outputPath=candidate.output_path,
                outputSha256=candidate.output_sha256,
                sourceEndpoint=candidate.source_endpoint,
                manifestCount=len(candidates),
            )
        return None
