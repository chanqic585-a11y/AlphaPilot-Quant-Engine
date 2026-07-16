from __future__ import annotations

from alphapilot.derivatives_data.data_quality_gate import evaluate_data_quality


def test_quality_gate_reports_missing_and_future_rows_without_imputation() -> None:
    records = [
        {"timestampUtc": "2026-01-01T00:00:00Z", "value": None, "availableAt": "2026-01-01T00:00:01Z"},
        {"timestampUtc": "2026-01-01T01:00:00Z", "value": 2, "availableAt": "2025-12-31T23:59:59Z"},
    ]

    report = evaluate_data_quality(
        records,
        required_fields=["timestampUtc", "value", "availableAt"],
        expected_interval_seconds=3600,
    )

    assert report["missingValueCount"] == 1
    assert report["imputedZeroCount"] == 0
    assert report["futureLeakCount"] == 1
    assert report["status"] == "failed"
