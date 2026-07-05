"""Market-regime proxy schema for combining public context fields."""

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
class MarketRegimeProxySnapshot:
    pair: str
    timeframe: str
    timestamp: str
    btcRegime: str | None
    fundingRegime: str | None
    openInterestRegime: str | None
    spreadRegime: str | None
    qualityStatus: str
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_market_regime_proxy_schema() -> PublicDataSchema:
    return PublicDataSchema(
        schemaId="market_regime_proxy_snapshot_v1",
        version="V13.4.28",
        dataType="market_regime_proxy",
        storageStatus="schema_only_not_collected",
        primaryKeys=["pair", "timeframe", "timestamp"],
        fields=[
            PublicDataField("pair", "string", True, False, "Unified pair such as BTC/USDT:USDT.", "Must match local OHLCV pair naming."),
            PublicDataField("timeframe", "string", True, False, "Research timeframe.", "Use 1h or 4h first."),
            PublicDataField("timestamp", "iso_datetime", True, False, "Proxy label timestamp.", "Store UTC ISO strings."),
            PublicDataField("btcRegime", "string", False, True, "BTC market regime from local OHLCV labels.", "Null if BTC label unavailable."),
            PublicDataField("fundingRegime", "string", False, True, "Funding context bucket.", "Null until funding data is collected."),
            PublicDataField("openInterestRegime", "string", False, True, "Open-interest context bucket.", "Null until OI data is collected."),
            PublicDataField("spreadRegime", "string", False, True, "Spread/liquidity context bucket.", "Null until public orderbook proxy exists."),
            PublicDataField("qualityStatus", "string", True, False, "ok, warning, unavailable, or error.", "Reflect missing component data."),
            PublicDataField("warnings", "list[string]", True, False, "Input coverage limitations.", "Must mention missing context fields."),
        ],
        qualityRules=[
            PublicDataQualityRule("no_imputed_public_context", "error", "Missing funding/OI/spread context must not be imputed as favorable.", "Keep null and warning."),
            PublicDataQualityRule("btc_label_required_for_v1", "warning", "BTC regime is the minimum usable proxy component.", "Mark unavailable if absent."),
            PublicDataQualityRule("research_context_only", "error", "Regime proxy labels are research context, not trading commands.", "Do not wire to execution."),
        ],
        unavailableHandling="Return partial proxy with null components and explicit warnings.",
        safetyNotes=public_data_safety_notes(),
    )
