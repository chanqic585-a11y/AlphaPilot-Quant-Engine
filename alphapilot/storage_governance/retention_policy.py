"""Conservative authority and retention rules for duplicate data assets."""

from __future__ import annotations

from typing import Any, Iterable, Mapping


SAFE_DUPLICATE_CLASSES = {
    "byte_identical",
    "content_equivalent",
    "rolling_snapshot_superseded",
}


def choose_authoritative_record(records: Iterable[Mapping[str, Any]]) -> Mapping[str, Any]:
    materialized = list(records)
    if not materialized:
        raise ValueError("at least one record is required")
    return sorted(
        materialized,
        key=lambda row: (
            -int(bool(row.get("immutableEvidence"))),
            -int(row.get("referenceCount") or 0),
            -int(row.get("coverageEnd") or 0),
            -int(row.get("rowCount") or 0),
            -int(row.get("sizeBytes") or 0),
            str(row.get("path") or ""),
        ),
    )[0]


def duplicate_class_is_safe(value: str) -> bool:
    return value in SAFE_DUPLICATE_CLASSES


def must_retain(record: Mapping[str, Any]) -> bool:
    return bool(
        record.get("immutableEvidence")
        or int(record.get("referenceCount") or 0) > 0
        or record.get("provenanceStatus") in {"unknown", "conflicting"}
    )
