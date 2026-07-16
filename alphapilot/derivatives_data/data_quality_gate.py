"""Deterministic file/record quality checks without missing-value imputation."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _parse(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("quality-gate timestamps must include a timezone")
    return parsed.astimezone(timezone.utc)


def evaluate_data_quality(
    records: list[dict[str, Any]],
    *,
    required_fields: list[str],
    expected_interval_seconds: int | None = None,
) -> dict[str, Any]:
    missing = sum(
        1 for row in records for field in required_fields if field not in row or row[field] is None
    )
    timestamps = [str(row["timestampUtc"]) for row in records if row.get("timestampUtc")]
    duplicate_count = len(timestamps) - len(set(timestamps))
    monotonic = timestamps == sorted(timestamps)
    future_leaks = sum(
        1
        for row in records
        if row.get("timestampUtc")
        and row.get("availableAt")
        and _parse(str(row["availableAt"])) < _parse(str(row["timestampUtc"]))
    )
    gap_count = 0
    if expected_interval_seconds and expected_interval_seconds > 0:
        ordered = sorted({_parse(timestamp) for timestamp in timestamps})
        gap_count = sum(
            1
            for previous, current in zip(ordered, ordered[1:])
            if (current - previous).total_seconds() > expected_interval_seconds
        )
    blockers = []
    if missing:
        blockers.append("missing_required_values")
    if duplicate_count:
        blockers.append("duplicate_timestamps")
    if not monotonic:
        blockers.append("non_monotonic_time")
    if future_leaks:
        blockers.append("future_data_leak")
    if gap_count:
        blockers.append("unexplained_time_gaps")
    return {
        "status": "passed" if not blockers else "failed",
        "recordCount": len(records),
        "requiredFields": required_fields,
        "missingValueCount": missing,
        "imputedZeroCount": 0,
        "duplicateTimestampCount": duplicate_count,
        "timeMonotonic": monotonic,
        "futureLeakCount": future_leaks,
        "unexplainedGapCount": gap_count,
        "blockers": blockers,
    }
