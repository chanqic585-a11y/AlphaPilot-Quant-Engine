from __future__ import annotations

import pytest

from alphapilot.derivatives_data.pit_universe import build_pit_snapshot


def _instrument(**overrides) -> dict[str, object]:
    row: dict[str, object] = {
        "instrumentId": "BTC-USDT-SWAP",
        "listedAt": "2025-01-01T00:00:00Z",
        "delistedAt": None,
        "tradingState": "live",
        "quoteVolume24h": 1_000_000,
        "openInterestQuote": 500_000,
        "spreadBpsOrFormalProxy": 2.0,
        "dataQualityStatus": "passed",
        "availableAt": "2026-01-01T00:00:00Z",
        "sourceHashes": ["sha256:abc"],
        "quoteCurrency": "USDT",
        "instrumentType": "perpetual",
        "ohlcvComplete": True,
    }
    row.update(overrides)
    return row


def test_pit_snapshot_uses_only_information_available_at_snapshot_time() -> None:
    result = build_pit_snapshot(
        [_instrument(), _instrument(instrumentId="FUTURE-USDT-SWAP", availableAt="2026-01-03T00:00:00Z")],
        {
            "snapshotTimeUtc": "2026-01-02T00:00:00Z",
            "minimumListingAgeDays": 90,
            "minimumQuoteVolume24h": 100_000,
            "minimumOpenInterestQuote": 100_000,
            "maximumSpreadBps": 10,
            "sourceMode": "historical_event_log",
        },
    )

    by_id = {row["instrumentId"]: row for row in result["rows"]}
    assert by_id["BTC-USDT-SWAP"]["included"] is True
    assert by_id["FUTURE-USDT-SWAP"]["included"] is False
    assert by_id["FUTURE-USDT-SWAP"]["reasonZh"] == "快照时点尚不可得"


def test_current_topn_cannot_backfill_historical_pit_membership() -> None:
    with pytest.raises(ValueError, match="current TopN"):
        build_pit_snapshot(
            [_instrument()],
            {"snapshotTimeUtc": "2026-01-02T00:00:00Z", "sourceMode": "current_topn_backfill"},
        )


def test_zero_spread_is_a_valid_observed_value() -> None:
    result = build_pit_snapshot(
        [_instrument(spreadBpsOrFormalProxy=0.0)],
        {
            "snapshotTimeUtc": "2026-01-02T00:00:00Z",
            "minimumListingAgeDays": 90,
            "minimumQuoteVolume24h": 100_000,
            "minimumOpenInterestQuote": 100_000,
            "maximumSpreadBps": 10,
            "sourceMode": "historical_event_log",
        },
    )

    assert result["rows"][0]["included"] is True
