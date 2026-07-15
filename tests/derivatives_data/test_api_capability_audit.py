from __future__ import annotations

from alphapilot.derivatives_data.api_capability_audit import (
    REQUIRED_CAPABILITY_FIELDS,
    build_default_capability_audit,
)


def test_default_audit_is_public_only_and_explicit_about_history_limits() -> None:
    report = build_default_capability_audit(checked_at="2026-07-16T00:00:00Z")

    assert report["schemaVersion"] == "derivatives_api_capability_audit_v2"
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
