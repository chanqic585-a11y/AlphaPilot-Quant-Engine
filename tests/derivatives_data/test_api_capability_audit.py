from __future__ import annotations

from alphapilot.derivatives_data.api_capability_audit import (
    REQUIRED_CAPABILITY_FIELDS,
    build_default_capability_audit,
)


def test_default_audit_is_public_only_and_explicit_about_history_limits() -> None:
    report = build_default_capability_audit(checked_at="2026-07-16T00:00:00Z")

    assert report["schemaVersion"] == "derivatives_api_capability_audit_v13_27_1_12"
    assert report["status"] == "completed"
    assert report["capabilities"]
    for row in report["capabilities"]:
        assert REQUIRED_CAPABILITY_FIELDS <= row.keys()
        assert row["publicOnly"] is True
        assert row["requiresAuth"] is False

    by_id = {row["capabilityId"]: row for row in report["capabilities"]}
    assert by_id["okx_open_interest_current"]["formalHistoricalEligible"] is False
    assert by_id["binance_open_interest_history"]["historicalDepth"] == "latest_1_month"
    assert by_id["binance_basis_history"]["historicalDepth"] == "latest_30_days"
    assert by_id["okx_historical_download_funding"]["earliestAvailable"] == "2022-03"


def test_audit_records_same_exchange_decision_without_splicing() -> None:
    report = build_default_capability_audit(checked_at="2026-07-16T00:00:00Z")

    decision = report["exchangeDecision"]
    assert decision["preferredExchange"] == "OKX"
    assert decision["sameExchangeCoreDataRequired"] is True
    assert decision["crossExchangeCoreFieldSplicingAllowed"] is False
    assert decision["okxFormalHistoricalCorePassed"] is False
    assert decision["binanceFormalHistoricalCorePassed"] is False


def test_v13_27_1_12_capabilities_record_formal_history_semantics() -> None:
    report = build_default_capability_audit(checked_at="2026-07-16T00:00:00Z")

    assert report["schemaVersion"] == "derivatives_api_capability_audit_v13_27_1_12"
    required = {
        "provider",
        "exchange",
        "endpointOrArchive",
        "dataType",
        "marketType",
        "requiresAuth",
        "publicOnly",
        "licenseOrUsageTerms",
        "earliestAvailable",
        "latestAvailable",
        "symbolCoverage",
        "granularity",
        "pagination",
        "rateLimit",
        "maximumLookback",
        "historicalCompleteness",
        "pointInTimeSemantics",
        "knownLimitations",
        "probeStatus",
    }
    assert report["capabilities"]
    assert all(required <= row.keys() for row in report["capabilities"])
    by_id = {row["capabilityId"]: row for row in report["capabilities"]}
    assert by_id["okx_open_interest_current"]["historicalCompleteness"] == "current_only"
    assert by_id["okx_instruments_current"]["pointInTimeSemantics"] == "current_snapshot_only"


def test_audit_covers_every_required_public_market_data_class() -> None:
    report = build_default_capability_audit(checked_at="2026-07-16T00:00:00Z")

    data_types = {row["dataType"] for row in report["capabilities"]}
    assert {
        "perpetual_ohlcv",
        "spot_ohlcv",
        "funding",
        "open_interest",
        "liquidation",
        "instrument_history",
        "listing_delisting",
        "trading_state",
        "volume_24h_history",
        "orderbook_snapshots",
    } <= data_types
