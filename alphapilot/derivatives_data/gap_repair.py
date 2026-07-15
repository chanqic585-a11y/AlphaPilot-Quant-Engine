"""Gap detection and non-destructive repair for canonical UTC market records."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from alphapilot.derivatives_data.resumable_collector import PRIMARY_KEY


def _parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include a timezone")
    return parsed.astimezone(timezone.utc)


def _format_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _key(record: dict[str, Any]) -> tuple[str, str, str, str]:
    return tuple(str(record[field]) for field in PRIMARY_KEY)  # type: ignore[return-value]


def detect_time_gaps(
    records: list[dict[str, Any]],
    *,
    interval_seconds: int,
    expected_start: str,
    expected_end: str,
) -> list[str]:
    if interval_seconds <= 0:
        raise ValueError("interval_seconds must be positive")
    available = {str(record["timestampUtc"]) for record in records}
    cursor = _parse_utc(expected_start)
    end = _parse_utc(expected_end)
    interval = timedelta(seconds=interval_seconds)
    missing: list[str] = []
    while cursor <= end:
        timestamp = _format_utc(cursor)
        if timestamp not in available:
            missing.append(timestamp)
        cursor += interval
    return missing


def repair_only_gaps(
    existing: list[dict[str, Any]],
    fetched: list[dict[str, Any]],
    *,
    requested_gap_timestamps: set[str],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    rows = {_key(record): dict(record) for record in existing}
    ignored_existing = 0
    ignored_outside = 0
    inserted = 0
    for record in fetched:
        key = _key(record)
        if key in rows:
            ignored_existing += 1
            continue
        if str(record["timestampUtc"]) not in requested_gap_timestamps:
            ignored_outside += 1
            continue
        rows[key] = dict(record)
        inserted += 1
    repaired = [rows[key] for key in sorted(rows)]
    return repaired, {
        "existingRecordCount": len(existing),
        "fetchedRecordCount": len(fetched),
        "insertedGapCount": inserted,
        "ignoredExistingCount": ignored_existing,
        "ignoredOutOfGapCount": ignored_outside,
        "finalRecordCount": len(repaired),
    }
