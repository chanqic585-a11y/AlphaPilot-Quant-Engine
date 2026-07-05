"""Schemas for V13.4.27 market regime labels."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class MarketRegimeLabel:
    timestamp: str
    close: float
    labels: list[str]
    primaryLabel: str
    ema20: float | None
    ema50: float | None
    ema200: float | None
    return3dPct: float | None
    return7dPct: float | None
    rollingVolatilityPct: float | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BtcSanityPoint:
    requestedDate: str
    nearestTimestamp: str | None
    close: float | None
    warning: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MarketBreadthSnapshot:
    timestamp: str
    pairCount: int
    positiveReturn24hPct: float | None
    averageReturn24hPct: float | None
    medianReturn24hPct: float | None
    aboveEma50Pct: float | None
    aboveEma200Pct: float | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MarketRegimeReview:
    status: str
    timerange: str
    btcPair: str
    regimeDistribution: dict[str, int]
    dominantRegimes: list[str]
    btcSanityPoints: list[BtcSanityPoint]
    breadthSummary: dict[str, Any]
    labels: list[MarketRegimeLabel] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "timerange": self.timerange,
            "btcPair": self.btcPair,
            "regimeDistribution": self.regimeDistribution,
            "dominantRegimes": self.dominantRegimes,
            "btcSanityPoints": [item.to_dict() for item in self.btcSanityPoints],
            "breadthSummary": self.breadthSummary,
            "labels": [item.to_dict() for item in self.labels],
            "warnings": self.warnings,
        }
