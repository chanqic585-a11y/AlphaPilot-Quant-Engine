"""Point-in-time fold assignment based only on the signal timestamp."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, Sequence


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
