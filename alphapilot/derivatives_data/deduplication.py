"""Stable-key deduplication for normalized public market records."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


PRIMARY_KEY = ("exchange", "instrumentId", "dataType", "timestampUtc")


def record_key(record: Mapping[str, Any]) -> tuple[str, str, str, str]:
    missing = [field for field in PRIMARY_KEY if not record.get(field)]
    if missing:
        raise ValueError(f"record missing primary key fields: {', '.join(missing)}")
    return tuple(str(record[field]) for field in PRIMARY_KEY)  # type: ignore[return-value]


def deduplicate_records(
    records: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    unique: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    duplicates = 0
    for record in records:
        key = record_key(record)
        if key in unique:
            duplicates += 1
            continue
        unique[key] = dict(record)
    rows = [unique[key] for key in sorted(unique)]
    return rows, {
        "primaryKey": list(PRIMARY_KEY),
        "inputRecordCount": len(records),
        "outputRecordCount": len(rows),
        "duplicateRecordCount": duplicates,
    }
