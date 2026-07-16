from __future__ import annotations

from alphapilot.derivatives_data.causal_availability import normalize_availability


def test_funding_is_not_available_before_settlement_and_publication_lag() -> None:
    result = normalize_availability(
        {"eventTimestamp": "2026-01-01T00:00:00Z", "sourceTimestamp": "2026-01-01T00:00:00Z"},
        {"dataType": "funding", "publicationLagSeconds": 60},
    )

    assert result["availableAt"] == "2026-01-01T00:01:00Z"
    assert result["publicationLagSeconds"] == 60


def test_open_interest_without_proven_publication_is_lagged_one_sampling_period() -> None:
    result = normalize_availability(
        {"eventTimestamp": "2026-01-01T00:00:00Z"},
        {"dataType": "open_interest", "samplingIntervalSeconds": 300},
    )

    assert result["availableAt"] == "2026-01-01T00:05:00Z"
    assert result["availabilityAssumption"] == "one_sampling_period_lag"
