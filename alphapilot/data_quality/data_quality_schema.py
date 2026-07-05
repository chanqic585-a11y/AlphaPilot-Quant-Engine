"""Schemas for V13.4.27 local OHLCV data integrity review.

These schemas describe research diagnostics only. They do not request exchange
data, read accounts, create orders, run backtests, or auto trade.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class PairTimeframeQuality:
    pair: str
    timeframe: str
    path: str | None
    status: str
    rowCount: int
    uniqueTimestampCount: int
    firstTimestamp: str | None
    lastTimestamp: str | None
    expectedCandles: int
    missingCandleCount: int
    missingRatePct: float
    duplicateTimestampCount: int
    nonMonotonicTimestampCount: int
    gapCount: int
    maxGapMinutes: float | None
    invalidOhlcCount: int
    nanPriceCount: int
    negativeVolumeCount: int
    zeroVolumeCount: int
    maxConsecutiveZeroVolume: int
    volumeSpikeCount: int
    extremeReturnCount: int
    maxAbsReturnPct: float | None
    quoteVolumeAvailable: bool
    quoteVolumeEstimated: bool
    pairFormatValid: bool
    marketType: str
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DataIntegritySummary:
    status: str
    timerange: str
    dataPath: str
    timeframesChecked: list[str]
    pairCount: int
    pairTimeframeCount: int
    validCount: int
    warningCount: int
    invalidCount: int
    missingFileCount: int
    averageMissingRatePct: float
    maxMissingRatePct: float
    totalDuplicateTimestamps: int
    totalInvalidOhlcRows: int
    totalExtremeReturnRows: int
    pairFormatIssueCount: int
    spotSwapMismatchCount: int
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DataIntegrityResult:
    summary: DataIntegritySummary
    pairTimeframeQuality: list[PairTimeframeQuality]

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": self.summary.to_dict(),
            "pairTimeframeQuality": [item.to_dict() for item in self.pairTimeframeQuality],
        }
