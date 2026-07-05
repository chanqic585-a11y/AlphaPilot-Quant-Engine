"""Funding-rate schema skeleton for public market data expansion."""

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
class FundingRateSnapshot:
    exchange: str
    pair: str
    marketType: str
    timestamp: str
    fundingRate: float | None
    nextFundingTime: str | None
    sourceId: str
    qualityStatus: str
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_funding_rate_schema() -> PublicDataSchema:
    return PublicDataSchema(
        schemaId="funding_rate_snapshot_v1",
        version="V13.4.28",
        dataType="funding_rate",
        storageStatus="schema_only_not_collected",
        primaryKeys=["exchange", "pair", "marketType", "timestamp"],
        fields=[
            PublicDataField("exchange", "string", True, False, "Exchange identifier.", "First version targets OKX public data."),
            PublicDataField("pair", "string", True, False, "Unified pair such as BTC/USDT:USDT.", "Must match local OHLCV pair naming."),
            PublicDataField("marketType", "string", True, False, "Market type, expected futures/swap.", "No spot funding rate is expected."),
            PublicDataField("timestamp", "iso_datetime", True, False, "Funding observation timestamp.", "Store UTC ISO strings."),
            PublicDataField("fundingRate", "float", False, True, "Observed funding rate.", "Null if public source is unavailable."),
            PublicDataField("nextFundingTime", "iso_datetime", False, True, "Next funding timestamp if available.", "Null when unavailable."),
            PublicDataField("sourceId", "string", True, False, "Data source registry id.", "Example: okx_public_funding_rate."),
            PublicDataField("qualityStatus", "string", True, False, "ok, warning, unavailable, or error.", "Never promote missing data to ok."),
            PublicDataField("warnings", "list[string]", True, False, "Collection or coverage warnings.", "Must include source limitations."),
        ],
        qualityRules=[
            PublicDataQualityRule("funding_rate_nullable", "warning", "Funding rate may be unavailable for a pair/date.", "Store null and warning; do not fabricate."),
            PublicDataQualityRule("timestamp_required", "error", "A usable record must have a timestamp.", "Reject record if missing."),
            PublicDataQualityRule("public_source_only", "error", "Funding data must come from public endpoints or local public cache.", "Reject private/API-key sources."),
        ],
        unavailableHandling="Store null fields and explicit warnings. Do not backfill with synthetic funding rates.",
        safetyNotes=public_data_safety_notes(),
    )
