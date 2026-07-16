from __future__ import annotations

from alphapilot.derivatives_data.deduplication import deduplicate_records


def test_deduplication_uses_stable_market_data_primary_key() -> None:
    first = {
        "exchange": "OKX",
        "instrumentId": "BTC-USDT-SWAP",
        "dataType": "funding",
        "timestampUtc": "2026-01-01T00:00:00Z",
        "value": 1,
    }
    duplicate = {**first, "value": 99}

    rows, report = deduplicate_records([first, duplicate])

    assert rows == [first]
    assert report["duplicateRecordCount"] == 1
    assert report["primaryKey"] == [
        "exchange",
        "instrumentId",
        "dataType",
        "timestampUtc",
    ]
