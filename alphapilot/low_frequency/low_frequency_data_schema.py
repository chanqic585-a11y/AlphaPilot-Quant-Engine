"""Schemas for V13.4.32 low-frequency data quality reports."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


DEFAULT_LOW_FREQUENCY_PAIRS = ["BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT"]
DEFAULT_LOW_FREQUENCY_TIMEFRAMES = ["4h", "1d"]
DEFAULT_OPTIONAL_TIMEFRAMES = ["1h"]
TIMEFRAME_MINUTES = {
    "1h": 60,
    "4h": 240,
    "1d": 1440,
}


@dataclass(frozen=True)
class LowFrequencyDataCheckConfig:
    timerange: str = "20240101-"
    pairs: list[str] = field(default_factory=lambda: list(DEFAULT_LOW_FREQUENCY_PAIRS))
    timeframes: list[str] = field(default_factory=lambda: list(DEFAULT_LOW_FREQUENCY_TIMEFRAMES))
    optionalTimeframes: list[str] = field(default_factory=lambda: list(DEFAULT_OPTIONAL_TIMEFRAMES))
    dataPath: str = "user_data/data/okx/futures"
    missingRateWarningPct: float = 0.1
    missingRateInvalidPct: float = 1.0
    minimumCandles: int = 200

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PairTimeframeDataQuality:
    pair: str
    timeframe: str
    path: str | None
    status: str
    firstTimestamp: str | None
    lastTimestamp: str | None
    actualCandleCount: int
    expectedCandleCount: int
    missingCandleCount: int
    missingRatePct: float | None
    duplicateTimestampCount: int
    invalidOhlcRows: int
    zeroPriceRows: int
    negativeVolumeRows: int
    extremeReturnRows: int
    maxZeroVolumeStreak: int
    dataQualityStatus: str
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LowFrequencyDataReport:
    reportId: str
    version: str
    status: str
    timerange: str
    dataPath: str
    pairs: list[str]
    timeframes: list[str]
    optionalTimeframes: list[str]
    summary: dict[str, Any]
    pairTimeframeQuality: list[PairTimeframeDataQuality]
    warnings: list[str]
    generatedAt: str

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["pairTimeframeQuality"] = [item.to_dict() for item in self.pairTimeframeQuality]
        return payload
