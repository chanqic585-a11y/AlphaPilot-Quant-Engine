"""Open-interest schema skeleton for public market data expansion."""

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
class OpenInterestSnapshot:
    exchange: str
    pair: str
    marketType: str
    timestamp: str
    openInterest: float | None
    openInterestCurrency: str | None
    sourceId: str
    qualityStatus: str
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_open_interest_schema() -> PublicDataSchema:
    return PublicDataSchema(
        schemaId="open_interest_snapshot_v1",
        version="V13.4.28",
        dataType="open_interest",
        storageStatus="schema_only_not_collected",
        primaryKeys=["exchange", "pair", "marketType", "timestamp"],
        fields=[
            PublicDataField("exchange", "string", True, False, "Exchange identifier.", "First version targets OKX public data."),
            PublicDataField("pair", "string", True, False, "Unified pair such as BTC/USDT:USDT.", "Must match local OHLCV pair naming."),
            PublicDataField("marketType", "string", True, False, "Market type, expected futures/swap.", "Open interest is futures/swap context."),
            PublicDataField("timestamp", "iso_datetime", True, False, "Open-interest observation timestamp.", "Store UTC ISO strings."),
            PublicDataField("openInterest", "float", False, True, "Observed open interest value.", "Null if public source is unavailable."),
            PublicDataField("openInterestCurrency", "string", False, True, "Native unit/currency if available.", "Do not assume quote currency."),
            PublicDataField("sourceId", "string", True, False, "Data source registry id.", "Example: okx_public_open_interest."),
            PublicDataField("qualityStatus", "string", True, False, "ok, warning, unavailable, or error.", "Never promote missing data to ok."),
            PublicDataField("warnings", "list[string]", True, False, "Collection or coverage warnings.", "Must include unit limitations."),
        ],
        qualityRules=[
            PublicDataQualityRule("oi_nullable", "warning", "Open interest may be unavailable for a pair/date.", "Store null and warning; do not fabricate."),
            PublicDataQualityRule("unit_required_when_value_present", "warning", "Open-interest unit should be known when a value exists.", "Flag warning if missing."),
            PublicDataQualityRule("public_source_only", "error", "Open-interest data must come from public endpoints or local public cache.", "Reject private/API-key sources."),
        ],
        unavailableHandling="Store null values with warnings. Do not convert units without explicit metadata.",
        safetyNotes=public_data_safety_notes(),
    )
