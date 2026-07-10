"""Typed records for the V13.16 market-data foundation."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class RawDataAsset:
    sourcePath: str
    relativePath: str
    sourceGroup: str
    fileFormat: str
    dataKind: str
    marketType: str
    instrumentId: str | None
    symbol: str | None
    timeframe: str | None
    partition: str | None
    duplicateFamily: str | None
    sizeBytes: int
    modifiedAtNs: int
    selected: bool = True
    exclusionReason: str | None = None
    provenanceStatus: str = "unknown"
    exchange: str | None = None
    sha256: str | None = None
    flags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FrameQuality:
    rows: int
    startTime: str | None
    endTime: str | None
    duplicateTimestampCount: int
    backwardTimestampCount: int
    gapEventCount: int
    missingBarCount: int
    invalidOhlcCount: int
    negativeVolumeCount: int
    unconfirmedDroppedCount: int
    sourceRows: int
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["errors"] = list(self.errors)
        value["warnings"] = list(self.warnings)
        return value


@dataclass(frozen=True)
class CanonicalAsset:
    sourcePath: str
    outputPath: str | None
    status: str
    marketType: str
    instrumentId: str | None
    timeframe: str | None
    contentSha256: str | None
    quality: FrameQuality | None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["quality"] = self.quality.to_dict() if self.quality else None
        return value
