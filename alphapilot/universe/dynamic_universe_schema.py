"""Schemas for V13.4.13 historical Dynamic Universe snapshots."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class DynamicUniverseConfig:
    market: str = "okx_usdt_swap"
    refreshFrequency: str = "daily"
    maxPairs: int = 10
    candidateMode: str = "top30"
    timeframeForRanking: str = "1h"
    timerange: str = "20260101-"
    warmupDays: int = 30
    minimumHistoryDays: int = 30
    idealHistoryDays: int = 90
    missingCandleRateLimit: float = 0.05
    dataPath: str = "user_data/data/okx/futures"
    quoteVolumeEstimated: bool = True
    delistFilterAvailable: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DynamicUniversePairScore:
    pair: str
    universeScore: float | None
    rank: int | None
    quoteVolume24h: float | None
    quoteVolume3d: float | None
    volumeStability3d: float | None
    missingCandleRate: float | None
    absReturn24h: float | None
    absReturn3d: float | None
    volatility24h: float | None
    volatility3d: float | None
    volumeExpansion24h: float | None
    volumeExpansion3d: float | None
    excluded: bool = False
    excludeReason: str | None = None
    warnings: list[str] = field(default_factory=list)
    rankFactors: dict[str, float | None] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DynamicUniverseSnapshot:
    snapshotDate: str
    generatedAt: str
    market: str
    refreshFrequency: str
    maxPairs: int
    selectedPairs: list[str]
    pairScores: list[DynamicUniversePairScore]
    excludedPairs: list[str]
    insufficientDataPairs: list[str]
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["pairScores"] = [score.to_dict() for score in self.pairScores]
        return payload


@dataclass
class DynamicUniverseBuildReport:
    reportId: str
    version: str
    status: str
    config: DynamicUniverseConfig
    timerange: str
    refreshFrequency: str
    maxPairs: int
    candidateMode: str
    snapshotCount: int
    candidatePairsCount: int
    supportedPairs: list[str]
    excludedPairs: list[str]
    insufficientDataPairs: list[str]
    missingDataPairs: list[str]
    pairsWithEstimatedQuoteVolume: list[str]
    pairsWithHighMissingRate: list[str]
    averageSelectedPairs: float
    topMostSelectedPairs: list[dict[str, Any]]
    mostExcludedPairs: list[dict[str, Any]]
    lookaheadBiasProtection: list[str]
    outputSnapshotsPath: str
    outputSampleSnapshotsPath: str
    outputSummaryPath: str
    warnings: list[str] = field(default_factory=list)
    generatedAt: str = ""
    dryRunApproved: bool = False
    liveTradingApproved: bool = False
    nextStepRecommendation: str = "V13.4.14 - Probability Score Dataset and Label Builder"
    source: str = "alphapilot_v13_4_13_historical_dynamic_universe_builder"

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["config"] = self.config.to_dict()
        return payload


def find_snapshot_for_timestamp(snapshots: list[dict[str, Any]], timestamp_iso: str) -> dict[str, Any] | None:
    """Return the latest snapshot whose snapshotDate is not after timestamp date."""
    target_date = timestamp_iso[:10]
    candidates = [snapshot for snapshot in snapshots if str(snapshot.get("snapshotDate", "")) <= target_date]
    if not candidates:
        return None
    return sorted(candidates, key=lambda item: str(item.get("snapshotDate")))[-1]


def get_pairs_for_timestamp(snapshots: list[dict[str, Any]], timestamp_iso: str) -> list[str]:
    snapshot = find_snapshot_for_timestamp(snapshots, timestamp_iso)
    return list(snapshot.get("selectedPairs", [])) if snapshot else []


def get_pair_scores_for_date(snapshots: list[dict[str, Any]], snapshot_date: str) -> list[dict[str, Any]]:
    for snapshot in snapshots:
        if snapshot.get("snapshotDate") == snapshot_date:
            return list(snapshot.get("pairScores", []))
    return []

