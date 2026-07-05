"""Public data collector skeleton for V13.4.28.

This module intentionally does not perform network requests. It defines the
future collector surface and returns explicit unavailable results until each
public data source is implemented and validated.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True)
class PublicDataCollectorResult:
    requestId: str
    sourceId: str
    dataType: str
    status: str
    records: list[dict[str, Any]]
    warnings: list[str]
    safetyBoundary: dict[str, bool] = field(
        default_factory=lambda: {
            "publicDataOnly": True,
            "apiKeyRequired": False,
            "privateEndpointUsed": False,
            "tradeApiUsed": False,
            "withdrawApiUsed": False,
            "accountRead": False,
            "positionRead": False,
            "orderCreated": False,
            "autoTrading": False,
        }
    )
    generatedAt: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class PublicDataCollectorSkeleton:
    """Describes planned public data collection without fetching anything."""

    def _unavailable(self, source_id: str, data_type: str) -> PublicDataCollectorResult:
        return PublicDataCollectorResult(
            requestId=f"{data_type}_collector_skeleton_v1",
            sourceId=source_id,
            dataType=data_type,
            status="unavailable_skeleton_only",
            records=[],
            warnings=[
                "V13.4.28 registers schema and source metadata only.",
                "No public endpoint request is executed by this skeleton.",
                "No API key, private endpoint, account data, position data, order creation, or auto trading is used.",
            ],
        )

    def collect_funding_rate(self, pair: str, timeframe: str | None = None) -> PublicDataCollectorResult:
        _ = (pair, timeframe)
        return self._unavailable("okx_public_funding_rate", "funding_rate")

    def collect_open_interest(self, pair: str, timeframe: str | None = None) -> PublicDataCollectorResult:
        _ = (pair, timeframe)
        return self._unavailable("okx_public_open_interest", "open_interest")

    def collect_orderbook_spread_proxy(self, pair: str) -> PublicDataCollectorResult:
        _ = pair
        return self._unavailable("okx_public_orderbook_snapshot", "orderbook_spread_proxy")

    def collect_liquidation(self, pair: str, timeframe: str | None = None) -> PublicDataCollectorResult:
        _ = (pair, timeframe)
        return self._unavailable("public_liquidation_source_unverified", "liquidation")

    def collect_market_regime_proxy(self, pair: str, timeframe: str) -> PublicDataCollectorResult:
        _ = (pair, timeframe)
        return self._unavailable("local_market_regime_proxy", "market_regime_proxy")


def collector_skeleton_manifest() -> dict[str, Any]:
    collector = PublicDataCollectorSkeleton()
    return {
        "status": "skeleton_only_not_executing_network_requests",
        "methods": [
            "collect_funding_rate",
            "collect_open_interest",
            "collect_orderbook_spread_proxy",
            "collect_liquidation",
            "collect_market_regime_proxy",
        ],
        "sampleUnavailableResults": [
            collector.collect_funding_rate("BTC/USDT:USDT").to_dict(),
            collector.collect_open_interest("BTC/USDT:USDT").to_dict(),
            collector.collect_orderbook_spread_proxy("BTC/USDT:USDT").to_dict(),
            collector.collect_liquidation("BTC/USDT:USDT").to_dict(),
            collector.collect_market_regime_proxy("BTC/USDT:USDT", "1h").to_dict(),
        ],
    }
