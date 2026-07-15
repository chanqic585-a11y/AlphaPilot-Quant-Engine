"""Content-addressed dataset manifests used by Phase 3 research runs."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from alphapilot.evolution.registry.hashing import sha256_file, stable_hash


@dataclass(frozen=True)
class DatasetManifest:
    datasetId: str
    dataType: str
    provider: str
    exchange: str
    marketType: str
    symbols: tuple[str, ...]
    timeframe: str | None
    startTime: str
    endTime: str
    rowCount: int
    timezone: str
    schemaVersion: str
    contentHash: str
    sourcePath: str
    isPointInTime: bool
    isProxy: bool
    licenseOrUsageNote: str

    @classmethod
    def from_file(
        cls,
        path: Path | str,
        *,
        dataset_id: str,
        data_type: str,
        provider: str,
        exchange: str,
        market_type: str,
        symbols: tuple[str, ...],
        timeframe: str | None,
        start_time: str,
        end_time: str,
        row_count: int,
        is_point_in_time: bool,
        is_proxy: bool,
        license_or_usage_note: str,
        schema_version: str = "research_dataset_manifest_v1",
    ) -> "DatasetManifest":
        source = Path(path).resolve()
        return cls(
            datasetId=dataset_id,
            dataType=data_type,
            provider=provider,
            exchange=exchange,
            marketType=market_type,
            symbols=tuple(symbols),
            timeframe=timeframe,
            startTime=start_time,
            endTime=end_time,
            rowCount=int(row_count),
            timezone="UTC",
            schemaVersion=schema_version,
            contentHash=sha256_file(source),
            sourcePath=str(source),
            isPointInTime=bool(is_point_in_time),
            isProxy=bool(is_proxy),
            licenseOrUsageNote=license_or_usage_note,
        )

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["symbols"] = list(self.symbols)
        value["manifestHash"] = stable_hash(value, prefix="dataset_manifest")
        return value


def verify_manifest(manifest: DatasetManifest) -> bool:
    source = Path(manifest.sourcePath)
    return source.is_file() and sha256_file(source) == manifest.contentHash
