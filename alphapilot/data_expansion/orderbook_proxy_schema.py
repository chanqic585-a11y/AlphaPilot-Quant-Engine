"""Orderbook/spread proxy schema skeleton for public market data expansion."""

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
class OrderbookSpreadProxySnapshot:
    exchange: str
    pair: str
    marketType: str
    timestamp: str
    bestBid: float | None
    bestAsk: float | None
    spreadBps: float | None
    depthSampleAvailable: bool
    sourceId: str
    qualityStatus: str
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_orderbook_proxy_schema() -> PublicDataSchema:
    return PublicDataSchema(
        schemaId="orderbook_spread_proxy_snapshot_v1",
        version="V13.4.28",
        dataType="orderbook_spread_proxy",
        storageStatus="schema_only_not_collected",
        primaryKeys=["exchange", "pair", "marketType", "timestamp"],
        fields=[
            PublicDataField("exchange", "string", True, False, "Exchange identifier.", "First version targets OKX public data."),
            PublicDataField("pair", "string", True, False, "Unified pair such as BTC/USDT:USDT.", "Must match local OHLCV pair naming."),
            PublicDataField("marketType", "string", True, False, "Market type, expected futures/swap.", "Use the same market as OHLCV research."),
            PublicDataField("timestamp", "iso_datetime", True, False, "Public orderbook sample timestamp.", "Store UTC ISO strings."),
            PublicDataField("bestBid", "float", False, True, "Best bid price from public orderbook snapshot.", "Null when unavailable."),
            PublicDataField("bestAsk", "float", False, True, "Best ask price from public orderbook snapshot.", "Null when unavailable."),
            PublicDataField("spreadBps", "float", False, True, "Best bid/ask spread in basis points.", "Only compute when bid and ask are valid."),
            PublicDataField("depthSampleAvailable", "bool", True, False, "Whether any depth sample was available.", "False is acceptable for skeleton output."),
            PublicDataField("sourceId", "string", True, False, "Data source registry id.", "Example: okx_public_orderbook_snapshot."),
            PublicDataField("qualityStatus", "string", True, False, "ok, warning, unavailable, or error.", "Never promote missing data to ok."),
            PublicDataField("warnings", "list[string]", True, False, "Collection or coverage warnings.", "Must include snapshot limitations."),
        ],
        qualityRules=[
            PublicDataQualityRule("bid_ask_consistency", "error", "bestAsk must be greater than or equal to bestBid when both exist.", "Reject inconsistent snapshots."),
            PublicDataQualityRule("spread_nullable", "warning", "Spread is null when bid/ask are missing.", "Store warning; do not fabricate."),
            PublicDataQualityRule("public_source_only", "error", "Orderbook proxy data must come from public endpoints or local public cache.", "Reject private/API-key sources."),
        ],
        unavailableHandling="Store unavailable status and warning when a public orderbook sample is absent.",
        safetyNotes=public_data_safety_notes(),
    )
