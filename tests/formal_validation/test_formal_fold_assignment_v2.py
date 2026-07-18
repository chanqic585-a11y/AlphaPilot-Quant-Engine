from __future__ import annotations

from alphapilot.formal_validation.formal_fold_assignment import (
    assign_formal_events_by_signal_timestamp,
)


def _fold(number: int) -> dict[str, str]:
    start = f"2026-01-{number * 2 + 1:02d}T00:00:00Z"
    end = f"2026-01-{number * 2 + 3:02d}T00:00:00Z"
    return {
        "foldId": f"fold_{number + 1}",
        "historyPrefixStart": "2025-01-01T00:00:00Z",
        "historyPrefixEnd": start,
        "validationStart": start,
        "validationEnd": end,
        "purgeStart": start,
        "purgeEnd": start,
        "embargoStart": start,
        "embargoEnd": start,
    }


def _event(number: int, *, exit_day: int | None = None) -> dict[str, object]:
    day = number * 2 + 1
    return {
        "signalId": f"signal-{number}",
        "signalTimestamp": f"2026-01-{day:02d}T04:00:00Z",
        "entryTimestamp": f"2026-01-{day:02d}T08:00:00Z",
        "exitTimestamp": f"2026-01-{exit_day or day:02d}T12:00:00Z",
    }


def test_all_five_folds_are_assigned_by_signal_timestamp() -> None:
    assigned, rejected, audit = assign_formal_events_by_signal_timestamp(
        [_event(index) for index in range(5)], [_fold(index) for index in range(5)]
    )

    assert [row["foldId"] for row in assigned] == [f"fold_{n}" for n in range(1, 6)]
    assert rejected == []
    assert audit["assignmentCompletenessPct"] == 100.0
    assert audit["unassignedEventCount"] == 0


def test_cross_boundary_event_is_explicitly_rejected() -> None:
    assigned, rejected, audit = assign_formal_events_by_signal_timestamp(
        [_event(0, exit_day=3)], [_fold(index) for index in range(5)]
    )

    assert assigned == []
    assert rejected[0]["assignmentReason"] == "reject_cross_fold_event"
    assert audit["crossBoundaryLeakageCount"] == 0
    assert audit["explicitlyRejectedEventCount"] == 1


def test_frozen_v18_split_fields_are_supported_and_preserved() -> None:
    fold = {
        "foldId": "fold_001",
        "trainStartTimestamp": "2025-01-01T00:00:00Z",
        "trainEndExclusiveTimestamp": "2025-12-20T00:00:00Z",
        "purgeStartTimestamp": "2025-12-20T00:00:00Z",
        "purgeEndExclusiveTimestamp": "2025-12-24T00:00:00Z",
        "embargoStartTimestamp": "2025-12-24T00:00:00Z",
        "embargoEndExclusiveTimestamp": "2026-01-01T00:00:00Z",
        "testStartTimestamp": "2026-01-01T00:00:00Z",
        "testEndExclusiveTimestamp": "2026-02-01T00:00:00Z",
    }
    event = {
        "signalId": "signal-v18",
        "signalTimestamp": "2026-01-02T00:00:00Z",
        "entryTimestamp": "2026-01-02T04:00:00Z",
        "exitTimestamp": "2026-01-03T04:00:00Z",
    }

    assigned, rejected, audit = assign_formal_events_by_signal_timestamp(
        [event], [fold]
    )

    assert rejected == []
    assert audit["assignmentCompletenessPct"] == 100.0
    assert assigned[0]["validationStart"] == fold["testStartTimestamp"]
    assert assigned[0]["validationEnd"] == fold["testEndExclusiveTimestamp"]
    assert assigned[0]["historyPrefixStart"] == fold["trainStartTimestamp"]
    assert assigned[0]["historyPrefixEnd"] == fold["trainEndExclusiveTimestamp"]
    assert assigned[0]["purgeStart"] == fold["purgeStartTimestamp"]
    assert assigned[0]["embargoEnd"] == fold["embargoEndExclusiveTimestamp"]


def test_raw_replay_legs_supply_the_formal_exit_timestamp() -> None:
    event = _event(0)
    event.pop("exitTimestamp")
    event["legs"] = [
        {
            "legIndex": 0,
            "executionTimestamp": "2026-01-01T12:00:00Z",
        }
    ]

    assigned, rejected, audit = assign_formal_events_by_signal_timestamp(
        [event], [_fold(index) for index in range(5)]
    )

    assert rejected == []
    assert len(assigned) == 1
    assert audit["assignmentCompletenessPct"] == 100.0
