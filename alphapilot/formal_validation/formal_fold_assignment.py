"""Point-in-time fold assignment based only on the signal timestamp."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from alphapilot.evolution.registry.hashing import stable_hash


FORMAL_EVENT_DISPOSITIONS = (
    "assigned_validation_fold",
    "excluded_initial_history_prefix",
    "excluded_after_final_validation_tail",
    "excluded_outside_common_window",
    "excluded_cross_fold_holding_path",
    "excluded_invalid_timestamp",
    "excluded_duplicate_event_identity",
)


def formal_event_disposition_contract() -> dict[str, Any]:
    """Return the immutable V18.3 event-disposition evidence contract."""

    contract: dict[str, Any] = {
        "schemaVersion": "formal_event_disposition_contract_v1",
        "assignmentTimestampField": "signalTimestamp",
        "timestampStandard": "UTC",
        "timeframeGridRequired": True,
        "validationIntervalOwnership": "unique_containing_validation_interval",
        "eventMayCrossFoldBoundary": False,
        "dispositions": list(FORMAL_EVENT_DISPOSITIONS),
        "requiredFields": [
            "eventId",
            "canonicalSignalId",
            "candidateId",
            "instrumentId",
            "signalTimestamp",
            "expectedEntryTimestamp",
            "splitPolicyHash",
            "disposition",
            "foldId",
            "dispositionReasonCode",
            "dispositionContractHash",
            "sourceEventHash",
            "assignmentEvidenceHash",
        ],
        "conservationLaw": (
            "rawEventCount=assignedValidationEventCount+explicitlyExcludedEventCount"
        ),
        "forbiddenOutcomes": [
            "unclassified_event",
            "multiple_validation_fold_assignment",
            "unknown_disposition",
            "cross_boundary_leakage",
        ],
    }
    contract["contractHash"] = stable_hash(
        contract, prefix="formal_event_disposition_contract"
    )
    return contract


def _utc(value: object) -> datetime:
    text = str(value or "").replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _first(mapping: Mapping[str, Any], *keys: str) -> object:
    for key in keys:
        value = mapping.get(key)
        if value not in (None, ""):
            return value
    raise ValueError(f"missing fold timestamp: {'|'.join(keys)}")


def _fold_identity(fold: Mapping[str, Any]) -> dict[str, str]:
    return {
        "foldId": str(fold.get("foldId") or ""),
        "historyPrefixStart": str(
            _first(fold, "historyPrefixStart", "trainStartTimestamp")
        ),
        "historyPrefixEnd": str(
            _first(fold, "historyPrefixEnd", "trainEndExclusiveTimestamp")
        ),
        "validationStart": str(
            _first(fold, "validationStart", "testStartTimestamp")
        ),
        "validationEnd": str(
            _first(fold, "validationEnd", "testEndExclusiveTimestamp")
        ),
        "purgeStart": str(_first(fold, "purgeStart", "purgeStartTimestamp")),
        "purgeEnd": str(
            _first(fold, "purgeEnd", "purgeEndExclusiveTimestamp")
        ),
        "embargoStart": str(
            _first(fold, "embargoStart", "embargoStartTimestamp")
        ),
        "embargoEnd": str(
            _first(fold, "embargoEnd", "embargoEndExclusiveTimestamp")
        ),
    }


def _event_exit_timestamp(event: Mapping[str, Any]) -> object:
    explicit = event.get("exitTimestamp")
    if explicit not in (None, ""):
        return explicit
    for key in ("exitLegs", "legs"):
        legs = event.get(key)
        if isinstance(legs, Sequence) and legs:
            final_leg = legs[-1]
            if isinstance(final_leg, Mapping):
                timestamp = final_leg.get("executionTimestamp")
                if timestamp not in (None, ""):
                    return timestamp
    raise ValueError("formal event is missing an exit timestamp")


def _event_identity(event: Mapping[str, Any], index: int) -> str:
    return str(
        event.get("eventId")
        or event.get("canonicalSignalId")
        or event.get("signalId")
        or f"raw-event-{index:08d}"
    )


def _is_on_timeframe_grid(timestamp: datetime, timeframe: str | None) -> bool:
    normalized = str(timeframe or "").strip().lower()
    if not normalized:
        return True
    if timestamp.minute or timestamp.second or timestamp.microsecond:
        return False
    if normalized.endswith("h"):
        hours = int(normalized[:-1])
        return hours > 0 and timestamp.hour % hours == 0
    if normalized.endswith("d"):
        days = int(normalized[:-1])
        return days > 0 and timestamp.hour == 0
    if normalized.endswith("m"):
        minutes = int(normalized[:-1])
        total_minutes = timestamp.hour * 60 + timestamp.minute
        return minutes > 0 and total_minutes % minutes == 0
    raise ValueError(f"unsupported timeframe grid: {timeframe}")


def _disposition_record(
    event: Mapping[str, Any],
    *,
    index: int,
    candidate_id: str,
    split_policy_hash: str,
    disposition_contract_hash: str,
    disposition: str,
    reason: str,
    fold_id: str | None = None,
) -> dict[str, Any]:
    event_id = _event_identity(event, index)
    source_event_hash = stable_hash(dict(event), prefix="formal_source_event")
    record = {
        "eventId": event_id,
        "canonicalSignalId": str(
            event.get("canonicalSignalId") or event.get("signalId") or event_id
        ),
        "candidateId": str(event.get("candidateId") or candidate_id),
        "instrumentId": str(event.get("instrumentId") or event.get("symbol") or ""),
        "signalTimestamp": event.get("signalTimestamp"),
        "expectedEntryTimestamp": event.get("expectedEntryTimestamp")
        or event.get("entryTimestamp"),
        "splitPolicyHash": str(split_policy_hash),
        "disposition": disposition,
        "foldId": fold_id,
        "dispositionReasonCode": reason,
        "dispositionContractHash": str(disposition_contract_hash),
        "sourceEventHash": source_event_hash,
    }
    record["assignmentEvidenceHash"] = stable_hash(
        record, prefix="formal_event_disposition"
    )
    return record


def build_formal_event_dispositions(
    events: Sequence[Mapping[str, Any]],
    folds: Sequence[Mapping[str, Any]],
    *,
    candidate_id: str,
    split_policy_hash: str,
    disposition_contract_hash: str,
    timeframe: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Classify every raw event exactly once without reading economic results."""

    normalized_folds = [_fold_identity(fold) for fold in folds]
    if not normalized_folds:
        raise ValueError("formal event disposition requires at least one fold")
    first_history_start = min(
        _utc(fold["historyPrefixStart"]) for fold in normalized_folds
    )
    first_validation_start = min(
        _utc(fold["validationStart"]) for fold in normalized_folds
    )
    final_validation_end = max(
        _utc(fold["validationEnd"]) for fold in normalized_folds
    )
    records: list[dict[str, Any]] = []
    seen_event_ids: set[str] = set()
    duplicate_event_identity_count = 0

    for index, source in enumerate(events):
        event = dict(source)
        event_id = _event_identity(event, index)
        if event_id in seen_event_ids:
            duplicate_event_identity_count += 1
            records.append(
                _disposition_record(
                    event,
                    index=index,
                    candidate_id=candidate_id,
                    split_policy_hash=split_policy_hash,
                    disposition_contract_hash=disposition_contract_hash,
                    disposition="excluded_duplicate_event_identity",
                    reason="duplicate_event_identity",
                )
            )
            continue
        seen_event_ids.add(event_id)

        try:
            signal_time = _utc(event.get("signalTimestamp"))
        except (TypeError, ValueError):
            records.append(
                _disposition_record(
                    event,
                    index=index,
                    candidate_id=candidate_id,
                    split_policy_hash=split_policy_hash,
                    disposition_contract_hash=disposition_contract_hash,
                    disposition="excluded_invalid_timestamp",
                    reason="invalid_signal_timestamp",
                )
            )
            continue
        if not _is_on_timeframe_grid(signal_time, timeframe):
            records.append(
                _disposition_record(
                    event,
                    index=index,
                    candidate_id=candidate_id,
                    split_policy_hash=split_policy_hash,
                    disposition_contract_hash=disposition_contract_hash,
                    disposition="excluded_invalid_timestamp",
                    reason="signal_timestamp_off_timeframe_grid",
                )
            )
            continue

        matching = [
            fold
            for fold in normalized_folds
            if _utc(fold["validationStart"])
            <= signal_time
            < _utc(fold["validationEnd"])
        ]
        if len(matching) > 1:
            raise RuntimeError("multiple_validation_intervals_for_signal_timestamp")
        if len(matching) == 1:
            fold = matching[0]
            try:
                entry_time = _utc(
                    event.get("expectedEntryTimestamp") or event.get("entryTimestamp")
                )
                exit_time = _utc(_event_exit_timestamp(event))
            except (TypeError, ValueError):
                records.append(
                    _disposition_record(
                        event,
                        index=index,
                        candidate_id=candidate_id,
                        split_policy_hash=split_policy_hash,
                        disposition_contract_hash=disposition_contract_hash,
                        disposition="excluded_invalid_timestamp",
                        reason="invalid_entry_or_exit_timestamp",
                        fold_id=fold["foldId"],
                    )
                )
                continue
            validation_start = _utc(fold["validationStart"])
            validation_end = _utc(fold["validationEnd"])
            if not (
                validation_start <= entry_time < validation_end
                and validation_start <= exit_time < validation_end
            ):
                disposition = "excluded_cross_fold_holding_path"
                reason = "holding_path_crosses_validation_fold"
            else:
                disposition = "assigned_validation_fold"
                reason = "signal_timestamp_owned_by_validation_fold"
            records.append(
                _disposition_record(
                    event,
                    index=index,
                    candidate_id=candidate_id,
                    split_policy_hash=split_policy_hash,
                    disposition_contract_hash=disposition_contract_hash,
                    disposition=disposition,
                    reason=reason,
                    fold_id=fold["foldId"],
                )
            )
            continue

        if first_history_start <= signal_time < first_validation_start:
            disposition = "excluded_initial_history_prefix"
            reason = "signal_in_initial_history_prefix"
        elif signal_time >= final_validation_end:
            disposition = "excluded_after_final_validation_tail"
            reason = "signal_after_final_validation_window"
        elif first_validation_start <= signal_time < final_validation_end:
            raise RuntimeError("no_validation_interval_for_signal_timestamp")
        else:
            disposition = "excluded_outside_common_window"
            reason = "signal_outside_common_validation_window"
        records.append(
            _disposition_record(
                event,
                index=index,
                candidate_id=candidate_id,
                split_policy_hash=split_policy_hash,
                disposition_contract_hash=disposition_contract_hash,
                disposition=disposition,
                reason=reason,
            )
        )

    assigned_count = sum(
        row["disposition"] == "assigned_validation_fold" for row in records
    )
    excluded_count = len(records) - assigned_count
    unknown_count = sum(
        row["disposition"] not in FORMAL_EVENT_DISPOSITIONS for row in records
    )
    audit = {
        "schemaVersion": "formal_event_disposition_audit_v1",
        "rawEventCount": len(events),
        "dispositionRecordCount": len(records),
        "assignedEventCount": assigned_count,
        "excludedEventCount": excluded_count,
        "assignedValidationEventCount": assigned_count,
        "explicitlyExcludedEventCount": excluded_count,
        "rawEqualsAssignedPlusExcluded": len(events)
        == assigned_count + excluded_count,
        "recordCoveragePct": round(100.0 * len(records) / len(events), 6)
        if events
        else 100.0,
        "unclassifiedCount": max(0, len(events) - len(records)),
        "multiAssignedCount": 0,
        "unclassifiedEventCount": max(0, len(events) - len(records)),
        "multiAssignedEventCount": 0,
        "duplicateDispositionCount": 0,
        "duplicateEventIdentityCount": duplicate_event_identity_count,
        "unknownDispositionCount": unknown_count,
        "crossBoundaryLeakageCount": 0,
        "dispositionCounts": {
            disposition: sum(row["disposition"] == disposition for row in records)
            for disposition in FORMAL_EVENT_DISPOSITIONS
        },
    }
    audit["auditHash"] = stable_hash(audit, prefix="formal_event_disposition_audit")
    return records, audit


def assign_formal_events_by_signal_timestamp(
    events: Sequence[Mapping[str, Any]], folds: Sequence[Mapping[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    normalized_folds = [(_fold_identity(fold), fold) for fold in folds]
    assigned: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for source in events:
        event = dict(source)
        signal_time = _utc(event.get("signalTimestamp"))
        matching = [
            identity
            for identity, _ in normalized_folds
            if _utc(identity["validationStart"])
            <= signal_time
            < _utc(identity["validationEnd"])
        ]
        if len(matching) != 1:
            rejected.append({**event, "assignmentReason": "reject_unassigned_signal"})
            continue
        fold = matching[0]
        start = _utc(fold["validationStart"])
        end = _utc(fold["validationEnd"])
        entry_time = _utc(event.get("entryTimestamp"))
        exit_time = _utc(_event_exit_timestamp(event))
        if not (start <= entry_time < end and start <= exit_time < end):
            rejected.append(
                {
                    **event,
                    **fold,
                    "assignmentReason": "reject_cross_fold_event",
                }
            )
            continue
        assigned.append(
            {
                **event,
                **fold,
                "assignmentReason": "assigned_by_signal_timestamp",
            }
        )
    total = len(events)
    audit = {
        "schemaVersion": "formal_fold_assignment_audit_v2",
        "assignmentCompletenessPct": round(
            100.0 * (len(assigned) + len(rejected)) / total, 6
        )
        if total
        else 100.0,
        "assignedEventCount": len(assigned),
        "explicitlyRejectedEventCount": len(rejected),
        "unassignedEventCount": sum(
            row["assignmentReason"] == "reject_unassigned_signal" for row in rejected
        ),
        "crossBoundaryLeakageCount": 0,
    }
    return assigned, rejected, audit
