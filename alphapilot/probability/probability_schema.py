"""Schemas for V13.4.14 probability score dataset artifacts.

The probability dataset is a historical research artifact only. It reads local
public OHLCV and universe snapshots; it does not run a strategy backtest, enter
Dry-run, call exchange APIs, read accounts, create orders, or auto trade.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ProbabilityDatasetConfig:
    universeSnapshotsPath: str = "reports/v13_4_13_dynamic_universe_snapshots.json"
    dataPath: str = "user_data/data/okx/futures"
    timerange: str = "20260101-"
    timeframe: str = "1h"
    tpPct: float = 0.05
    slPct: float = 0.025
    windows: list[int] = field(default_factory=lambda: [8, 12, 24])
    primaryWindow: int = 12
    minBucketSamples: int = 50

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ProbabilityLabel:
    windowBars: int
    hitTpBeforeSl: bool
    hitSlBeforeTp: bool
    noHit: bool
    mfePct: float | None
    maePct: float | None
    futureReturnAtWindowEnd: float | None
    barsToTp: int | None
    barsToSl: int | None
    outcomeReturnPct: float | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ProbabilityCandidateSample:
    sampleId: str
    timestamp: str
    pair: str
    timeframe: str
    snapshotDate: str
    regimeCandidate: str
    close: float | None
    volume: float | None
    quoteVolume: float | None
    rsi14: float | None
    ema20: float | None
    ema50: float | None
    ema200: float | None
    macdHist: float | None
    bbMiddle: float | None
    bbUpper: float | None
    bbLower: float | None
    atrPct: float | None
    volumeRatio: float | None
    btcState: str
    liquidityBucket: str
    volatilityBucket: str
    rsiBucket: str
    distanceToEma20Bucket: str
    distanceToBollingerBucket: str
    labels: dict[str, ProbabilityLabel]
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["labels"] = {key: label.to_dict() for key, label in self.labels.items()}
        return payload


@dataclass
class ProbabilityBucketRow:
    bucketId: str
    regimeCandidate: str
    liquidityBucket: str
    volatilityBucket: str
    rsiBucket: str
    emaDistanceBucket: str
    bbPositionBucket: str
    btcState: str
    sampleCount: int
    hitTpBeforeSlProbability: float | None
    hitSlBeforeTpProbability: float | None
    averageMfePct: float | None
    averageMaePct: float | None
    averageReturnPct: float | None
    profitFactor: float | None
    expectancy: float | None
    confidenceLevel: str
    decision: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ProbabilityDatasetReport:
    reportId: str
    version: str
    status: str
    config: ProbabilityDatasetConfig
    inputUniverseSnapshots: str
    snapshotCount: int
    sampleCount: int
    labeledSampleCount: int
    insufficientDataCount: int
    windows: list[int]
    tpPct: float
    slPct: float
    primaryWindow: int
    scoreTablePath: str
    sampleDatasetPreview: list[dict[str, Any]]
    topPositiveBuckets: list[dict[str, Any]]
    topNegativeBuckets: list[dict[str, Any]]
    insufficientSampleBuckets: list[dict[str, Any]]
    probabilityGateSummary: dict[str, Any]
    noLookaheadRules: list[str]
    warnings: list[str]
    generatedAt: str
    dryRunApproved: bool = False
    liveTradingApproved: bool = False
    nextStepRecommendation: str = "V13.4.15 - Dynamic Regime Strategy V0.1 Implementation"
    source: str = "alphapilot_v13_4_14_probability_dataset_label_builder"

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["config"] = self.config.to_dict()
        return payload

