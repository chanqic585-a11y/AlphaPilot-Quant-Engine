from __future__ import annotations

from alphapilot.derivatives_data.gap_repair import detect_time_gaps, repair_only_gaps


def _record(timestamp: str, value: int) -> dict[str, object]:
    return {
        "exchange": "OKX",
        "instrumentId": "BTC-USDT-SWAP",
        "dataType": "open_interest",
        "timestampUtc": timestamp,
        "value": value,
    }

def test_gap_detection_lists_missing_timestamps_explicitly() -> None:
    records = [
        _record("2026-01-01T00:00:00Z", 1),
        _record("2026-01-01T02:00:00Z", 3),
    ]

    gaps = detect_time_gaps(
        records,
        interval_seconds=3600,
        expected_start="2026-01-01T00:00:00Z",
        expected_end="2026-01-01T02:00:00Z",
    )

    assert gaps == ["2026-01-01T01:00:00Z"]


def test_repair_only_inserts_requested_gaps_and_preserves_existing_rows() -> None:
    existing = [
        _record("2026-01-01T00:00:00Z", 1),
        _record("2026-01-01T02:00:00Z", 3),
    ]
    fetched = [
        _record("2026-01-01T00:00:00Z", 999),
        _record("2026-01-01T01:00:00Z", 2),
        _record("2026-01-01T03:00:00Z", 4),
    ]

    repaired, report = repair_only_gaps(
        existing,
        fetched,
        requested_gap_timestamps={"2026-01-01T01:00:00Z"},
    )

    assert [row["value"] for row in repaired] == [1, 2, 3]
    assert report == {
        "existingRecordCount": 2,
        "fetchedRecordCount": 3,
        "insertedGapCount": 1,
        "ignoredExistingCount": 1,
        "ignoredOutOfGapCount": 1,
        "finalRecordCount": 3,
    }
