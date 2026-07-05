"""Schemas for V13.4.28 market data coverage and expansion report."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class MissingPairTimeframe:
    pair: str
    timeframe: str
    expectedPath: str
    reason: str
    repairPlanned: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DataCoverageGap:
    pair: str
    timeframe: str
    status: str
    reason: str
    warnings: list[str]
    rowCount: int
    missingRatePct: float
    repairStatus: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CoverageRepairReport:
    reportId: str
    version: str
    status: str
    downloadCommand: str
    preRepairSummary: dict[str, Any]
    postRepairSummary: dict[str, Any]
    missingPairTimeframes: list[MissingPairTimeframe]
    dataCoverageGaps: list[DataCoverageGap]
    repairConclusion: str
    generatedAt: str
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "reportId": self.reportId,
            "version": self.version,
            "status": self.status,
            "downloadCommand": self.downloadCommand,
            "preRepairSummary": self.preRepairSummary,
            "postRepairSummary": self.postRepairSummary,
            "missingPairTimeframes": [item.to_dict() for item in self.missingPairTimeframes],
            "dataCoverageGaps": [item.to_dict() for item in self.dataCoverageGaps],
            "repairConclusion": self.repairConclusion,
            "generatedAt": self.generatedAt,
            "warnings": self.warnings,
        }


@dataclass(frozen=True)
class MarketDataExpansionReport:
    reportId: str
    version: str
    status: str
    coverageRepair: dict[str, Any]
    fundingRateSchema: dict[str, Any]
    openInterestSchema: dict[str, Any]
    orderbookProxySchema: dict[str, Any]
    liquidationSchema: dict[str, Any]
    marketRegimeProxySchema: dict[str, Any]
    dataSourceRegistry: list[dict[str, Any]]
    collectorSkeleton: dict[str, Any]
    nextStepRecommendation: list[str]
    dryRunApproved: bool
    liveTradingApproved: bool
    safetyBoundary: dict[str, bool]
    generatedAt: str
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
