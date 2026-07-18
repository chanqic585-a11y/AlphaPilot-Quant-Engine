from __future__ import annotations

import pytest

from alphapilot.formal_validation.formal_fold_assignment import (
    build_formal_event_dispositions,
    formal_event_disposition_contract,
)


def _fold(fold_id: str, start: str, end: str) -> dict[str, str]:
    return {
        "foldId": fold_id,
        "historyPrefixStart": "2025-12-01T00:00:00Z",
        "historyPrefixEnd": start,
        "validationStart": start,
        "validationEnd": end,
        "purgeStart": start,
        "purgeEnd": start,
        "embargoStart": start,
        "embargoEnd": start,
    }


FOLDS = [
    _fold("fold_1", "2026-01-01T00:00:00Z", "2026-02-01T00:00:00Z"),
    _fold("fold_2", "2026-02-01T00:00:00Z", "2026-03-01T00:00:00Z"),
]


def _event(
    signal_id: str,
    signal_timestamp: str,
    *,
    entry_timestamp: str | None = None,
    exit_timestamp: str | None = None,
) -> dict[str, object]:
    entry = entry_timestamp or signal_timestamp
    exit_value = exit_timestamp or entry
    return {
        "signalId": signal_id,
        "instrumentId": "BTC-USDT-SWAP",
        "signalTimestamp": signal_timestamp,
        "entryTimestamp": entry,
        "exitTimestamp": exit_value,
    }


def test_every_raw_event_receives_exactly_one_explicit_disposition() -> None:
    rows, audit = build_formal_event_dispositions(
        [
            _event("prefix", "2025-12-15T00:00:00Z"),
            _event("fold-1", "2026-01-10T00:00:00Z"),
            _event("cross", "2026-01-20T00:00:00Z", exit_timestamp="2026-02-02T00:00:00Z"),
            _event("fold-2", "2026-02-10T00:00:00Z"),
            _event("tail", "2026-03-10T00:00:00Z"),
            _event("outside", "2025-11-01T00:00:00Z"),
            _event("invalid", "not-a-timestamp"),
        ],
        FOLDS,
        candidate_id="candidate-s01",
        split_policy_hash="split-hash",
        disposition_contract_hash="disposition-contract",
    )

    assert [row["disposition"] for row in rows] == [
        "excluded_initial_history_prefix",
        "assigned_validation_fold",
        "excluded_cross_fold_holding_path",
        "assigned_validation_fold",
        "excluded_after_final_validation_tail",
        "excluded_outside_common_window",
        "excluded_invalid_timestamp",
    ]
    assert [row["foldId"] for row in rows if row["foldId"]] == [
        "fold_1",
        "fold_1",
        "fold_2",
    ]
    assert all(row["assignmentEvidenceHash"] for row in rows)
    assert audit["rawEventCount"] == 7
    assert audit["assignedEventCount"] == 2
    assert audit["excludedEventCount"] == 5
    assert audit["rawEqualsAssignedPlusExcluded"] is True
    assert audit["recordCoveragePct"] == 100.0
    assert audit["unclassifiedCount"] == 0
    assert audit["multiAssignedCount"] == 0
    assert audit["duplicateDispositionCount"] == 0
    assert audit["unknownDispositionCount"] == 0
    assert audit["crossBoundaryLeakageCount"] == 0


def test_duplicate_event_identity_is_explicit_and_hashes_are_deterministic() -> None:
    events = [
        _event("duplicate", "2026-01-10T00:00:00Z"),
        _event("duplicate", "2026-01-10T00:00:00Z"),
    ]
    first, first_audit = build_formal_event_dispositions(
        events,
        FOLDS,
        candidate_id="candidate-s01",
        split_policy_hash="split-hash",
        disposition_contract_hash="disposition-contract",
    )
    second, second_audit = build_formal_event_dispositions(
        events,
        FOLDS,
        candidate_id="candidate-s01",
        split_policy_hash="split-hash",
        disposition_contract_hash="disposition-contract",
    )

    assert first[0]["disposition"] == "assigned_validation_fold"
    assert first[1]["disposition"] == "excluded_duplicate_event_identity"
    assert first_audit["rawEqualsAssignedPlusExcluded"] is True
    assert first_audit["duplicateEventIdentityCount"] == 1
    assert [row["assignmentEvidenceHash"] for row in first] == [
        row["assignmentEvidenceHash"] for row in second
    ]
    assert first_audit == second_audit


def test_off_grid_signal_is_explicitly_invalid() -> None:
    rows, audit = build_formal_event_dispositions(
        [_event("off-grid", "2026-01-10T01:00:00Z")],
        FOLDS,
        candidate_id="candidate-s01",
        split_policy_hash="split-hash",
        disposition_contract_hash="disposition-contract",
        timeframe="4h",
    )

    assert rows[0]["disposition"] == "excluded_invalid_timestamp"
    assert rows[0]["dispositionReasonCode"] == "signal_timestamp_off_timeframe_grid"
    assert audit["unclassifiedCount"] == 0


def test_overlapping_validation_intervals_fail_closed() -> None:
    overlapping = [
        _fold("fold-1", "2026-01-01T00:00:00Z", "2026-02-01T00:00:00Z"),
        _fold("fold-2", "2026-01-15T00:00:00Z", "2026-03-01T00:00:00Z"),
    ]
    with pytest.raises(RuntimeError, match="multiple_validation_intervals"):
        build_formal_event_dispositions(
            [_event("ambiguous", "2026-01-20T00:00:00Z")],
            overlapping,
            candidate_id="candidate-s01",
            split_policy_hash="split-hash",
            disposition_contract_hash="disposition-contract",
            timeframe="4h",
        )


def test_disposition_contract_is_frozen_and_deterministic() -> None:
    first = formal_event_disposition_contract()
    second = formal_event_disposition_contract()

    assert first == second
    assert first["schemaVersion"] == "formal_event_disposition_contract_v1"
    assert first["eventMayCrossFoldBoundary"] is False
    assert first["assignmentTimestampField"] == "signalTimestamp"
    assert first["contractHash"].startswith("formal_event_disposition_contract_")
