from __future__ import annotations

from datetime import datetime, timezone

import pytest

from alphapilot.research_screening.causal_asof_join import causal_asof_join
from alphapilot.research_screening.causal_clock import (
    is_available_at,
    next_tradable_bar,
)
from alphapilot.research_screening.data_availability import (
    funding_availability,
    oi_availability,
    pit_snapshot_availability,
)
from alphapilot.research_screening.split_leakage_guard import (
    SplitWindow,
    guard_split_events,
)


UTC = timezone.utc


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def test_funding_is_unavailable_until_settled_value_is_published() -> None:
    row = funding_availability(
        event_timestamp=_dt("2026-01-01T00:00:00Z"),
        observed_at=_dt("2026-01-01T00:01:00Z"),
        published_at=_dt("2026-01-01T00:02:00Z"),
        predicted=False,
    )

    assert row["availableAt"] == "2026-01-01T00:02:00Z"
    assert not is_available_at(row, _dt("2026-01-01T00:01:59Z"))
    assert is_available_at(row, _dt("2026-01-01T00:02:00Z"))


def test_predicted_funding_requires_contemporaneous_public_proof() -> None:
    with pytest.raises(ValueError, match="contemporaneous public availability"):
        funding_availability(
            event_timestamp=_dt("2026-01-01T00:00:00Z"),
            observed_at=_dt("2026-01-01T00:00:10Z"),
            predicted=True,
            contemporaneous_public_proof=False,
        )


def test_unproven_oi_latency_is_delayed_one_source_period() -> None:
    row = oi_availability(
        source_timestamp=_dt("2026-01-01T00:00:00Z"),
        observed_at=_dt("2026-01-01T00:01:00Z"),
        source_period_seconds=3600,
        publication_latency_proven=False,
    )

    assert row["availableAt"] == "2026-01-01T01:00:00Z"
    assert not is_available_at(row, _dt("2026-01-01T00:59:59Z"))


def test_pit_snapshot_waits_for_the_completed_source_bar() -> None:
    row = pit_snapshot_availability(
        source_timestamp=_dt("2026-01-01T00:00:00Z"),
        source_bar_close=_dt("2026-01-01T00:05:00Z"),
        observed_at=_dt("2026-01-01T00:04:00Z"),
    )

    assert row["availableAt"] == "2026-01-01T00:05:00Z"


def test_decision_executes_on_the_next_tradable_bar() -> None:
    bars = [
        {"openTime": "2026-01-01T00:00:00Z", "open": 100.0},
        {"openTime": "2026-01-01T00:05:00Z", "open": 101.0},
        {"openTime": "2026-01-01T00:10:00Z", "open": 102.0},
    ]

    selected = next_tradable_bar(bars, _dt("2026-01-01T00:05:00Z"))

    assert selected["openTime"] == "2026-01-01T00:10:00Z"


def test_causal_asof_join_never_uses_future_publication() -> None:
    decisions = [{"symbol": "BTC", "signalDecisionTime": "2026-01-01T00:05:00Z"}]
    features = [
        {"symbol": "BTC", "availableAt": "2026-01-01T00:04:00Z", "value": 1},
        {"symbol": "BTC", "availableAt": "2026-01-01T00:06:00Z", "value": 2},
    ]

    joined = causal_asof_join(decisions=decisions, observations=features)

    assert joined[0]["observation"]["value"] == 1


def test_boundary_crossing_purge_and_embargo_events_are_dropped() -> None:
    window = SplitWindow(
        split_id="fold_1",
        starts_at=_dt("2026-01-01T00:00:00Z"),
        ends_at=_dt("2026-01-02T00:00:00Z"),
    )
    events = [
        {
            "eventId": "valid",
            "splitId": "fold_1",
            "decisionTime": "2026-01-01T03:00:00Z",
            "entryTime": "2026-01-01T04:00:00Z",
            "exitTime": "2026-01-01T05:00:00Z",
        },
        {
            "eventId": "embargo",
            "splitId": "fold_1",
            "decisionTime": "2026-01-01T00:30:00Z",
            "entryTime": "2026-01-01T00:45:00Z",
            "exitTime": "2026-01-01T01:30:00Z",
        },
        {
            "eventId": "purge",
            "splitId": "fold_1",
            "decisionTime": "2026-01-01T22:30:00Z",
            "entryTime": "2026-01-01T23:00:00Z",
            "exitTime": "2026-01-01T23:30:00Z",
        },
        {
            "eventId": "crosses",
            "splitId": "fold_1",
            "decisionTime": "2026-01-01T23:00:00Z",
            "entryTime": "2026-01-01T23:30:00Z",
            "exitTime": "2026-01-02T00:30:00Z",
        },
    ]

    result = guard_split_events(
        events=events,
        windows=[window],
        purge_seconds=7200,
        embargo_seconds=7200,
        maximum_holding_seconds=3600,
    )

    assert [row["eventId"] for row in result["accepted"]] == ["valid"]
    assert {row["eventId"]: row["reason"] for row in result["dropped"]} == {
        "embargo": "embargo_window",
        "purge": "purge_window",
        "crosses": "holding_interval_crosses_split_boundary",
    }


def test_purge_must_cover_maximum_holding_horizon() -> None:
    with pytest.raises(ValueError, match="purge_seconds"):
        guard_split_events(
            events=[],
            windows=[],
            purge_seconds=3599,
            embargo_seconds=0,
            maximum_holding_seconds=3600,
        )
