"""Frozen point-in-time ranking evidence with no missing-value substitution."""

from __future__ import annotations

from datetime import datetime, timezone
import math
from typing import Any, Mapping, Sequence

from alphapilot.evolution.registry.hashing import stable_hash


REQUIRED_RANKING_FIELDS = (
    "signalId",
    "signalTimestamp",
    "eventExtremeResidualZ",
    "recoverySizeZ",
    "liquidity30d",
    "instrumentId",
    "sourceTimestamp",
    "availableAt",
)

RANKING_VALUE_FIELDS = (
    "eventExtremeResidualZ",
    "recoverySizeZ",
    "liquidity30d",
)

RANKING_VALUE_STATUSES = (
    "available",
    "unavailable_insufficient_history",
    "unavailable_volume_semantics",
    "unavailable_nonfinite_feature",
    "invalid_timestamp",
)


def _utc(value: object) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _available(value: object) -> bool:
    if value is None or value == "":
        return False
    return not isinstance(value, float) or math.isfinite(value)


def freeze_ranking_evidence(
    rows: Sequence[Mapping[str, Any]], *, ranking_policy_hash: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    frozen: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for source in rows:
        row = dict(source)
        if any(not _available(row.get(field)) for field in REQUIRED_RANKING_FIELDS):
            rejected.append({**row, "reason": "reject_ranking_field_unavailable"})
            continue
        if _utc(row["availableAt"]) > _utc(row["signalTimestamp"]):
            rejected.append({**row, "reason": "reject_post_entry_ranking_data"})
            continue
        evidence = {
            field: row[field] for field in REQUIRED_RANKING_FIELDS
        } | {"rankingPolicyHash": str(ranking_policy_hash)}
        evidence["rankingEvidenceHash"] = stable_hash(
            evidence, prefix="ranking_evidence"
        )
        frozen.append(evidence)
    return frozen, rejected


def audit_ranking_evidence_parity(
    core_rows: Sequence[Mapping[str, Any]], adapter_rows: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    core = {str(row.get("signalId")): dict(row) for row in core_rows}
    adapter = {str(row.get("signalId")): dict(row) for row in adapter_rows}
    shared = sorted(set(core) & set(adapter))
    comparable_fields = (*REQUIRED_RANKING_FIELDS, "rankingPolicyHash")
    field_total = len(shared) * len(comparable_fields)
    field_matches = sum(
        core[key].get(field) == adapter[key].get(field)
        for key in shared
        for field in comparable_fields
    )
    hash_matches = sum(
        core[key].get("rankingEvidenceHash")
        == adapter[key].get("rankingEvidenceHash")
        for key in shared
    )
    return {
        "schemaVersion": "ranking_evidence_parity_v1",
        "fieldParityPct": round(100.0 * field_matches / field_total, 6)
        if field_total
        else 100.0,
        "hashParityPct": round(100.0 * hash_matches / len(shared), 6)
        if shared
        else 100.0,
        "postEntryDataUseCount": sum(
            _utc(row["availableAt"]) > _utc(row["signalTimestamp"])
            for row in [*core_rows, *adapter_rows]
        ),
        "unmappedCount": len(set(core) ^ set(adapter)),
    }


def _canonical_signal_id(row: Mapping[str, Any]) -> str:
    return str(row.get("canonicalSignalId") or row.get("signalId") or "")


def _value_status(field: str, value: object, explicit_status: object) -> str:
    if explicit_status in RANKING_VALUE_STATUSES:
        return str(explicit_status)
    if isinstance(value, float) and not math.isfinite(value):
        return "unavailable_nonfinite_feature"
    if value not in (None, ""):
        return "available"
    if field == "liquidity30d":
        return "unavailable_volume_semantics"
    return "unavailable_insufficient_history"


def materialize_ranking_evidence_records(
    assigned_events: Sequence[Mapping[str, Any]],
    feature_rows: Sequence[Mapping[str, Any]],
    *,
    ranking_policy_hash: str,
    capacity_semantics_hash: str | Mapping[str, str],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Create one immutable ranking record for every assigned formal event."""

    features = {_canonical_signal_id(row): dict(row) for row in feature_rows}
    records: list[dict[str, Any]] = []
    post_entry_data_use_count = 0
    for assigned_source in assigned_events:
        assigned = dict(assigned_source)
        canonical_signal_id = _canonical_signal_id(assigned)
        feature = features.get(canonical_signal_id, {})
        statuses = {
            field: _value_status(
                field, feature.get(field), feature.get(f"{field}Status")
            )
            for field in RANKING_VALUE_FIELDS
        }
        available_at = (
            feature.get("availableAt")
            or feature.get("sourceTimestamp")
            or assigned.get("signalTimestamp")
        )
        expected_entry = assigned.get("expectedEntryTimestamp") or assigned.get(
            "entryTimestamp"
        )
        invalid_timestamp = False
        post_entry = False
        try:
            if available_at in (None, "") or expected_entry in (None, ""):
                invalid_timestamp = True
            else:
                post_entry = _utc(available_at) > _utc(expected_entry)
        except (TypeError, ValueError):
            invalid_timestamp = True
        if invalid_timestamp:
            ranking_status = "invalid_timestamp"
            unavailable_reason = "invalid_timestamp"
        else:
            unavailable_parts = [
                f"{field}:{statuses[field]}"
                for field in RANKING_VALUE_FIELDS
                if statuses[field] != "available"
            ]
            if post_entry:
                post_entry_data_use_count += 1
                unavailable_parts.append("availableAt:post_entry_data")
            ranking_status = (
                "available"
                if not unavailable_parts
                else next(
                    statuses[field]
                    for field in RANKING_VALUE_FIELDS
                    if statuses[field] != "available"
                )
            )
            if post_entry:
                ranking_status = "invalid_timestamp"
            unavailable_reason = ";".join(unavailable_parts) or None
        instrument_id = str(
            assigned.get("instrumentId") or feature.get("instrumentId") or ""
        )
        bound_capacity_hash = (
            str(capacity_semantics_hash.get(instrument_id) or "")
            if isinstance(capacity_semantics_hash, Mapping)
            else str(capacity_semantics_hash)
        )
        record = {
            "canonicalSignalId": canonical_signal_id,
            "candidateId": str(
                assigned.get("candidateId") or feature.get("candidateId") or ""
            ),
            "instrumentId": instrument_id,
            "signalTimestamp": assigned.get("signalTimestamp"),
            "expectedEntryTimestamp": expected_entry,
            "foldId": assigned.get("foldId"),
            "eventExtremeResidualZ": feature.get("eventExtremeResidualZ"),
            "eventExtremeResidualZStatus": statuses["eventExtremeResidualZ"],
            "recoverySizeZ": feature.get("recoverySizeZ"),
            "recoverySizeZStatus": statuses["recoverySizeZ"],
            "liquidity30d": feature.get("liquidity30d"),
            "liquidity30dStatus": statuses["liquidity30d"],
            "rankingEvidenceStatus": ranking_status,
            "rankingUnavailableReason": unavailable_reason,
            "availableAt": available_at,
            "sourceBarHashes": list(feature.get("sourceBarHashes") or []),
            "capacitySemanticsHash": bound_capacity_hash,
            "rankingPolicyHash": str(ranking_policy_hash),
        }
        record["rankingEvidenceHash"] = stable_hash(
            record, prefix="ranking_evidence_record"
        )
        records.append(record)

    status_field_count = len(records) * (len(RANKING_VALUE_FIELDS) + 1)
    populated_status_count = sum(
        bool(row.get(f"{field}Status"))
        for row in records
        for field in RANKING_VALUE_FIELDS
    ) + sum(bool(row.get("rankingEvidenceStatus")) for row in records)
    audit = {
        "schemaVersion": "ranking_evidence_record_audit_v1",
        "assignedEventCount": len(assigned_events),
        "recordCount": len(records),
        "recordCoveragePct": round(
            100.0 * len(records) / len(assigned_events), 6
        )
        if assigned_events
        else 100.0,
        "statusCoveragePct": round(
            100.0 * populated_status_count / status_field_count, 6
        )
        if status_field_count
        else 100.0,
        "availableRecordCount": sum(
            row["rankingEvidenceStatus"] == "available" for row in records
        ),
        "unavailableRecordCount": sum(
            row["rankingEvidenceStatus"] != "available" for row in records
        ),
        "postEntryDataUseCount": post_entry_data_use_count,
    }
    audit["auditHash"] = stable_hash(audit, prefix="ranking_evidence_record_audit")
    return records, audit


def audit_ranking_evidence_record_parity(
    core_rows: Sequence[Mapping[str, Any]],
    adapter_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    core = {_canonical_signal_id(row): dict(row) for row in core_rows}
    adapter = {_canonical_signal_id(row): dict(row) for row in adapter_rows}
    all_ids = set(core) | set(adapter)
    shared = sorted(set(core) & set(adapter))
    status_fields = tuple(f"{field}Status" for field in RANKING_VALUE_FIELDS) + (
        "rankingEvidenceStatus",
    )
    comparable_fields = (
        "candidateId",
        "instrumentId",
        "signalTimestamp",
        "expectedEntryTimestamp",
        "foldId",
        *RANKING_VALUE_FIELDS,
        *status_fields,
        "availableAt",
        "sourceBarHashes",
        "capacitySemanticsHash",
        "rankingPolicyHash",
        "rankingUnavailableReason",
    )
    field_total = len(shared) * len(comparable_fields)
    field_matches = sum(
        core[key].get(field) == adapter[key].get(field)
        for key in shared
        for field in comparable_fields
    )
    status_total = len(shared) * len(status_fields)
    status_matches = sum(
        core[key].get(field) == adapter[key].get(field)
        for key in shared
        for field in status_fields
    )
    hash_matches = sum(
        core[key].get("rankingEvidenceHash")
        == adapter[key].get("rankingEvidenceHash")
        for key in shared
    )
    reason_matches = sum(
        core[key].get("rankingUnavailableReason")
        == adapter[key].get("rankingUnavailableReason")
        for key in shared
    )
    post_entry_data_use_count = 0
    for row in [*core_rows, *adapter_rows]:
        try:
            available_at = row.get("availableAt")
            expected_entry = row.get("expectedEntryTimestamp")
            if available_at not in (None, "") and expected_entry not in (None, ""):
                post_entry_data_use_count += _utc(available_at) > _utc(expected_entry)
        except (TypeError, ValueError):
            continue
    return {
        "schemaVersion": "ranking_evidence_record_parity_v1",
        "recordCoveragePct": round(100.0 * len(shared) / len(all_ids), 6)
        if all_ids
        else 100.0,
        "statusCoveragePct": round(100.0 * status_matches / status_total, 6)
        if status_total
        else 100.0,
        "fieldParityPct": round(100.0 * field_matches / field_total, 6)
        if field_total
        else 100.0,
        "hashParityPct": round(100.0 * hash_matches / len(shared), 6)
        if shared
        else 100.0,
        "rejectionReasonParityPct": round(
            100.0 * reason_matches / len(shared), 6
        )
        if shared
        else 100.0,
        "postEntryDataUseCount": int(post_entry_data_use_count),
        "unmappedCount": len(all_ids) - len(shared),
    }
