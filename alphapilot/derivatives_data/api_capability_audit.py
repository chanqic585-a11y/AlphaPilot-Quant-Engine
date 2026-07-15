"""Deterministic audit of public derivatives-data capabilities used by V2 research."""

from __future__ import annotations

from typing import Any

from alphapilot.evolution.registry.hashing import stable_hash


REQUIRED_CAPABILITY_FIELDS = frozenset(
    {
        "exchange",
        "endpoint",
        "dataType",
        "earliestAvailable",
        "latestAvailable",
        "pagination",
        "rateLimit",
        "requiresAuth",
        "publicOnly",
        "historicalDepth",
        "symbolCoverage",
        "knownLimitations",
    }
)

OKX_DOCS = "https://www.okx.com/docs-v5/en/"
OKX_DOWNLOADS = "https://www.okx.com/en-gb/historical-data"
BINANCE_DOCS = (
    "https://developers.binance.com/en/docs/catalog/"
    "core-trading-derivatives-trading-usd-s-m-futures/api/rest-api/market-data"
)


def _capability(
    capability_id: str,
    *,
    exchange: str,
    endpoint: str,
    data_type: str,
    earliest: str | None,
    latest: str,
    pagination: str,
    rate_limit: str,
    historical_depth: str,
    symbol_coverage: str,
    limitations: list[str],
    formal_historical_eligible: bool,
    documentation_url: str,
) -> dict[str, Any]:
    return {
        "capabilityId": capability_id,
        "exchange": exchange,
        "endpoint": endpoint,
        "dataType": data_type,
        "earliestAvailable": earliest,
        "latestAvailable": latest,
        "pagination": pagination,
        "rateLimit": rate_limit,
        "requiresAuth": False,
        "publicOnly": True,
        "historicalDepth": historical_depth,
        "symbolCoverage": symbol_coverage,
        "knownLimitations": limitations,
        "formalHistoricalEligible": formal_historical_eligible,
        "documentationUrl": documentation_url,
    }


def _capabilities() -> list[dict[str, Any]]:
    return [
        _capability(
            "okx_history_candles",
            exchange="OKX",
            endpoint="GET /api/v5/market/history-candles",
            data_type="ohlcv",
            earliest=None,
            latest="current",
            pagination="after/before timestamp; maximum 300 rows",
            rate_limit="20 requests per 2 seconds per IP",
            historical_depth="recent_years",
            symbol_coverage="active OKX spot/futures/swap instruments",
            limitations=["API documentation does not promise a fixed earliest date per instrument"],
            formal_historical_eligible=True,
            documentation_url=OKX_DOCS,
        ),
        _capability(
            "okx_historical_download_ohlc",
            exchange="OKX",
            endpoint="Historical Market Data / Candlestick download",
            data_type="ohlcv_bulk",
            earliest="2023-07",
            latest="published_archives",
            pagination="download partitions",
            rate_limit="website download service; no REST limit published",
            historical_depth="from_2023_07",
            symbol_coverage="published OKX archive coverage",
            limitations=["archive coverage must be verified per instrument and partition"],
            formal_historical_eligible=True,
            documentation_url=OKX_DOWNLOADS,
        ),
        _capability(
            "okx_historical_download_funding",
            exchange="OKX",
            endpoint="Historical Market Data / Funding rate download",
            data_type="funding",
            earliest="2022-03",
            latest="published_archives",
            pagination="download partitions",
            rate_limit="website download service; no REST limit published",
            historical_depth="from_2022_03",
            symbol_coverage="published OKX perpetual instruments",
            limitations=["archive coverage must be verified per instrument and partition"],
            formal_historical_eligible=True,
            documentation_url=OKX_DOWNLOADS,
        ),
        _capability(
            "okx_open_interest_current",
            exchange="OKX",
            endpoint="GET /api/v5/public/open-interest",
            data_type="open_interest",
            earliest=None,
            latest="current",
            pagination="none; current snapshot",
            rate_limit="20 requests per 2 seconds per IP",
            historical_depth="current_snapshot",
            symbol_coverage="active OKX futures/swap/option instruments",
            limitations=["public endpoint exposes current open interest, not long historical series"],
            formal_historical_eligible=False,
            documentation_url=OKX_DOCS,
        ),
        _capability(
            "okx_liquidation_orders_recent",
            exchange="OKX",
            endpoint="GET /api/v5/public/liquidation-orders",
            data_type="liquidation",
            earliest=None,
            latest="recent",
            pagination="before/after timestamp",
            rate_limit="20 requests per 2 seconds per IP",
            historical_depth="recent_only",
            symbol_coverage="supported OKX derivatives instruments",
            limitations=["insufficient documented depth for multi-year formal validation"],
            formal_historical_eligible=False,
            documentation_url=OKX_DOCS,
        ),
        _capability(
            "okx_instruments_current",
            exchange="OKX",
            endpoint="GET /api/v5/public/instruments",
            data_type="instrument_lifecycle",
            earliest=None,
            latest="current",
            pagination="instrument type query",
            rate_limit="20 requests per 2 seconds per IP",
            historical_depth="current_snapshot",
            symbol_coverage="current OKX instruments",
            limitations=["does not reconstruct historical point-in-time tradable universe"],
            formal_historical_eligible=False,
            documentation_url=OKX_DOCS,
        ),
        _capability(
            "binance_continuous_klines",
            exchange="Binance",
            endpoint="GET /fapi/v1/continuousKlines",
            data_type="ohlcv",
            earliest=None,
            latest="current",
            pagination="startTime/endTime; maximum 1500 rows",
            rate_limit="IP request weight based on limit",
            historical_depth="exchange_retained_history",
            symbol_coverage="Binance USD-M continuous contracts",
            limitations=["earliest coverage varies by contract"],
            formal_historical_eligible=True,
            documentation_url=BINANCE_DOCS,
        ),
        _capability(
            "binance_funding_history",
            exchange="Binance",
            endpoint="GET /fapi/v1/fundingRate",
            data_type="funding",
            earliest=None,
            latest="current",
            pagination="startTime/endTime; maximum 1000 rows",
            rate_limit="shared 500 requests per 5 minutes per IP",
            historical_depth="exchange_retained_history",
            symbol_coverage="Binance USD-M perpetual instruments",
            limitations=["coverage begins at each instrument's own funding history"],
            formal_historical_eligible=True,
            documentation_url=BINANCE_DOCS,
        ),
        _capability(
            "binance_open_interest_history",
            exchange="Binance",
            endpoint="GET /futures/data/openInterestHist",
            data_type="open_interest",
            earliest="rolling_1_month",
            latest="current",
            pagination="startTime/endTime; maximum 500 rows",
            rate_limit="1000 requests per 5 minutes per IP",
            historical_depth="latest_1_month",
            symbol_coverage="Binance USD-M instruments with statistics",
            limitations=["official endpoint limits history to the latest one month"],
            formal_historical_eligible=False,
            documentation_url=BINANCE_DOCS,
        ),
        _capability(
            "binance_basis_history",
            exchange="Binance",
            endpoint="GET /futures/data/basis",
            data_type="basis",
            earliest="rolling_30_days",
            latest="current",
            pagination="startTime/endTime; maximum 500 rows",
            rate_limit="IP request weight 0, subject to general limits",
            historical_depth="latest_30_days",
            symbol_coverage="Binance USD-M pairs and contract types",
            limitations=["official endpoint limits history to the latest 30 days"],
            formal_historical_eligible=False,
            documentation_url=BINANCE_DOCS,
        ),
        _capability(
            "binance_exchange_info_current",
            exchange="Binance",
            endpoint="GET /fapi/v1/exchangeInfo",
            data_type="instrument_lifecycle",
            earliest=None,
            latest="current",
            pagination="none",
            rate_limit="IP weight 1",
            historical_depth="current_snapshot",
            symbol_coverage="current Binance USD-M instruments",
            limitations=["current rules do not reconstruct historical PIT membership or delist state"],
            formal_historical_eligible=False,
            documentation_url=BINANCE_DOCS,
        ),
    ]


def build_default_capability_audit(*, checked_at: str) -> dict[str, Any]:
    capabilities = _capabilities()
    core = {
        "schemaVersion": "derivatives_api_capability_audit_v2",
        "status": "completed",
        "checkedAt": checked_at,
        "publicDataOnly": True,
        "capabilities": capabilities,
        "exchangeDecision": {
            "preferredExchange": "OKX",
            "fallbackExchangeBeforePreregistration": "Binance",
            "sameExchangeCoreDataRequired": True,
            "crossExchangeCoreFieldSplicingAllowed": False,
            "okxFormalHistoricalCorePassed": False,
            "binanceFormalHistoricalCorePassed": False,
            "reason": (
                "OKX and Binance both expose useful public derivatives data, but neither documented "
                "public stack supplies the long historical OI, liquidation and PIT universe evidence "
                "needed by at least two V2 directions."
            ),
        },
    }
    return {**core, "auditHash": stable_hash(core, prefix="api_capability_audit")}
