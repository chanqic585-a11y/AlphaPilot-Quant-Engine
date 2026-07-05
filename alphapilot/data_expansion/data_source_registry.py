"""Public data source registry for V13.4.28.

The registry is descriptive only. It does not create clients, fetch data, use
API keys, call private endpoints, or authorize trading.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class PublicDataSource:
    sourceId: str
    exchange: str
    dataType: str
    requiresApiKey: bool
    usesPrivateEndpoint: bool
    supportsHistorical: bool
    supportsRealtime: bool
    status: str
    notes: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


DATA_SOURCE_REGISTRY: tuple[PublicDataSource, ...] = (
    PublicDataSource(
        sourceId="okx_public_ohlcv",
        exchange="okx",
        dataType="ohlcv",
        requiresApiKey=False,
        usesPrivateEndpoint=False,
        supportsHistorical=True,
        supportsRealtime=False,
        status="active_local_freqtrade_path",
        notes="Current local OHLCV path uses Freqtrade public download-data outputs.",
    ),
    PublicDataSource(
        sourceId="okx_public_funding_rate",
        exchange="okx",
        dataType="funding_rate",
        requiresApiKey=False,
        usesPrivateEndpoint=False,
        supportsHistorical=True,
        supportsRealtime=True,
        status="planned_not_collected",
        notes="Schema registered for future public funding-rate collection; V13.4.28 does not fetch it.",
    ),
    PublicDataSource(
        sourceId="okx_public_open_interest",
        exchange="okx",
        dataType="open_interest",
        requiresApiKey=False,
        usesPrivateEndpoint=False,
        supportsHistorical=True,
        supportsRealtime=True,
        status="planned_not_collected",
        notes="Schema registered for future public OI collection; units and history coverage must be validated.",
    ),
    PublicDataSource(
        sourceId="okx_public_ticker",
        exchange="okx",
        dataType="ticker",
        requiresApiKey=False,
        usesPrivateEndpoint=False,
        supportsHistorical=False,
        supportsRealtime=True,
        status="planned_not_collected",
        notes="Public ticker can support spread and market-state checks later; V13.4.28 does not poll it.",
    ),
    PublicDataSource(
        sourceId="okx_public_orderbook_snapshot",
        exchange="okx",
        dataType="orderbook_spread_proxy",
        requiresApiKey=False,
        usesPrivateEndpoint=False,
        supportsHistorical=False,
        supportsRealtime=True,
        status="planned_not_collected",
        notes="Public orderbook snapshots can support spread proxy later; V13.4.28 does not collect snapshots.",
    ),
    PublicDataSource(
        sourceId="local_freqtrade_ohlcv",
        exchange="local",
        dataType="ohlcv",
        requiresApiKey=False,
        usesPrivateEndpoint=False,
        supportsHistorical=True,
        supportsRealtime=False,
        status="active_local_cache",
        notes="Local public OHLCV cache under user_data/data/okx/futures.",
    ),
)


def get_data_source_registry() -> list[dict[str, Any]]:
    return [item.to_dict() for item in DATA_SOURCE_REGISTRY]
