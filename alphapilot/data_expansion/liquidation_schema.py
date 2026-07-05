"""Liquidation schema skeleton for public market data expansion."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from alphapilot.data_expansion.data_quality_schema import (
    PublicDataField,
    PublicDataQualityRule,
    PublicDataSchema,
    public_data_safety_notes,
)


@dataclass(frozen=True)
class LiquidationSnapshot:
    exchange: str
    pair: str
    marketType: str
    timestamp: str
    longLiquidationVolume: float | None
    shortLiquidationVolume: float | None
    liquidationCurrency: str | None
    sourceId: str
    qualityStatus: str
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_liquidation_schema() -> PublicDataSchema:
    return PublicDataSchema(
        schemaId="liquidation_snapshot_v1",
        version="V13.4.28",
        dataType="liquidation",
        storageStatus="schema_only_not_collected",
        primaryKeys=["exchange", "pair", "marketType", "timestamp"],
        fields=[
            PublicDataField("exchange", "string", True, False, "Exchange identifier.", "Public availability may vary by exchange."),
            PublicDataField("pair", "string", True, False, "Unified pair such as BTC/USDT:USDT.", "Must match local OHLCV pair naming."),
            PublicDataField("marketType", "string", True, False, "Market type, expected futures/swap.", "Liquidation context is futures/swap."),
            PublicDataField("timestamp", "iso_datetime", True, False, "Liquidation bucket timestamp.", "Store UTC ISO strings."),
            PublicDataField("longLiquidationVolume", "float", False, True, "Long-side liquidation volume if publicly available.", "Null when unavailable."),
            PublicDataField("shortLiquidationVolume", "float", False, True, "Short-side liquidation volume if publicly available.", "Null when unavailable."),
            PublicDataField("liquidationCurrency", "string", False, True, "Native unit/currency if available.", "Do not infer units."),
            PublicDataField("sourceId", "string", True, False, "Data source registry id.", "Status is planned until a public source is verified."),
            PublicDataField("qualityStatus", "string", True, False, "ok, warning, unavailable, or error.", "Never promote missing data to ok."),
            PublicDataField("warnings", "list[string]", True, False, "Collection or coverage warnings.", "Must state public-source limitations."),
        ],
        qualityRules=[
            PublicDataQualityRule("liquidation_public_availability", "warning", "Liquidation data may not be available through a reliable public source.", "Return unavailable; do not fabricate."),
            PublicDataQualityRule("unit_required_when_value_present", "warning", "Liquidation unit should be known when a value exists.", "Flag warning if missing."),
            PublicDataQualityRule("public_source_only", "error", "Liquidation data must come from public endpoints or verified public datasets.", "Reject private/API-key sources."),
        ],
        unavailableHandling="Return unavailable until a stable public source is verified.",
        safetyNotes=public_data_safety_notes(),
    )
