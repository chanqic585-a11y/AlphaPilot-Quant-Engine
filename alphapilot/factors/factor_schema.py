"""Schemas for the AlphaPilot factor research layer.

These dataclasses describe research artifacts only. They are not trading
signals, strategy entries, or order instructions.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class FactorDataField:
    fieldId: str
    dataType: str
    description: str
    required: bool = True
    source: str = "local_research_panel"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FactorDataPanelSchema:
    panelId: str
    purpose: str
    primaryIndex: list[str]
    fields: list[FactorDataField]
    futureFields: list[FactorDataField] = field(default_factory=list)
    researchOnly: bool = True

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["fields"] = [item.to_dict() for item in self.fields]
        payload["futureFields"] = [item.to_dict() for item in self.futureFields]
        return payload


@dataclass(frozen=True)
class ManualFactorSpec:
    factorId: str
    name: str
    description: str
    formula: str
    requiredFields: list[str]
    expectedDirection: str
    applicableRegime: list[str]
    riskNotes: list[str]
    outputColumn: str | None = None
    source: str = "alphapilot_manual_factor_library_v01"
    researchOnly: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FactorDataPanelConfig:
    timerange: str = "20260101-"
    timeframe: str = "1h"
    pairs: list[str] = field(default_factory=list)
    dataPath: str = "user_data/data/okx/futures"
    useDynamicUniverse: bool = False
    universeSnapshotsPath: str | None = "reports/v13_4_13_dynamic_universe_snapshots.json"
    sampleSize: int = 200
    source: str = "alphapilot_factor_data_panel_v13_4_21"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FactorDataRow:
    timestamp: str
    pair: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    quoteVolume: float | None
    quoteVolumeEstimated: bool
    vwap: float | None
    vwapEstimated: bool
    returns_1: float | None
    returns_3: float | None
    returns_6: float | None
    returns_12: float | None
    marketReturn: float | None
    btcReturn: float | None
    btcReturn_12: float | None
    universeMember: bool
    universeMembershipSource: str
    regimeLabel: str
    liquidityBucket: str
    volatilityBucket: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FactorDataPanelReport:
    reportId: str
    version: str
    status: str
    config: FactorDataPanelConfig
    rowsGenerated: int
    sampleRowsWritten: int
    timeframe: str
    timerange: str
    loadedPairs: list[str]
    failedPairs: list[dict[str, str]]
    missingTimeframes: list[str]
    formatUsed: dict[str, str]
    factorColumnsGenerated: list[str]
    factorCoverage: dict[str, dict[str, Any]]
    topMissingFactors: list[dict[str, Any]]
    quoteVolumeEstimatedCount: int
    vwapEstimatedCount: int
    universeMembershipAvailable: bool
    universeMembershipSource: str
    dynamicUniverseSnapshotsUsed: int
    warnings: list[str]
    noLookaheadAssurance: list[str]
    dryRunApproved: bool
    liveTradingApproved: bool
    outputPanelSamplePath: str
    outputReportPath: str
    outputSummaryPath: str
    manualFactorLibraryReportPath: str
    nextStepRecommendation: str
    generatedAt: str

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["config"] = self.config.to_dict()
        return payload


@dataclass(frozen=True)
class FactorEvaluationMetric:
    metricId: str
    name: str
    description: str
    preferredDirection: str
    caveats: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_factor_data_panel_schema() -> FactorDataPanelSchema:
    fields = [
        FactorDataField("timestamp", "datetime", "UTC candle timestamp."),
        FactorDataField("pair", "string", "Trading pair identifier such as BTC/USDT:USDT."),
        FactorDataField("open", "float", "Open price for the candle."),
        FactorDataField("high", "float", "High price for the candle."),
        FactorDataField("low", "float", "Low price for the candle."),
        FactorDataField("close", "float", "Close price for the candle."),
        FactorDataField("volume", "float", "Base asset candle volume."),
        FactorDataField("quoteVolume", "float", "Quote volume when available.", required=False),
        FactorDataField("vwap", "float", "Volume weighted average price when available.", required=False),
        FactorDataField("returns_1", "float", "One-bar close-to-close return."),
        FactorDataField("returns_3", "float", "Three-bar close-to-close return."),
        FactorDataField("returns_6", "float", "Six-bar close-to-close return."),
        FactorDataField("returns_12", "float", "Twelve-bar close-to-close return."),
        FactorDataField("marketReturn", "float", "Broad universe return proxy for the timestamp."),
        FactorDataField("btcReturn", "float", "BTC return over the same horizon."),
        FactorDataField("universeMember", "boolean", "Whether pair is in the historical dynamic universe."),
        FactorDataField("regimeLabel", "string", "Regime label at timestamp."),
        FactorDataField("liquidityBucket", "string", "Liquidity bucket from research liquidity gate."),
        FactorDataField("volatilityBucket", "string", "Volatility bucket for regime-aware research."),
    ]
    future_fields = [
        FactorDataField("fundingRate", "float", "Public funding rate if available.", required=False),
        FactorDataField("openInterest", "float", "Public open interest if available.", required=False),
        FactorDataField("longShortRatio", "float", "Public long/short ratio if available.", required=False),
        FactorDataField("orderbookSpread", "float", "Public orderbook spread sample.", required=False),
        FactorDataField("orderbookDepth", "float", "Public orderbook depth sample.", required=False),
        FactorDataField("newsSentiment", "float", "Optional external sentiment score.", required=False),
        FactorDataField("macroEventFlag", "boolean", "Optional macro event flag.", required=False),
    ]
    return FactorDataPanelSchema(
        panelId="factor_data_panel_v01",
        purpose="Organize OHLCV, returns, regime, liquidity, and universe membership into a time by pair research panel.",
        primaryIndex=["timestamp", "pair"],
        fields=fields,
        futureFields=future_fields,
    )
