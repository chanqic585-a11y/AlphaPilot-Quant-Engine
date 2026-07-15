"""Point-in-time availability records for public research observations."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any


UTC = timezone.utc


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("availability timestamps must be timezone-aware")
    return value.astimezone(UTC)


def _iso(value: datetime) -> str:
    return _utc(value).isoformat().replace("+00:00", "Z")


def _record(
    *,
    event_timestamp: datetime,
    observed_at: datetime,
    published_at: datetime,
    available_at: datetime,
    source_timestamp: datetime,
    data_type: str,
    policy: str,
) -> dict[str, Any]:
    event = _utc(event_timestamp)
    observed = _utc(observed_at)
    published = _utc(published_at)
    available = _utc(available_at)
    source = _utc(source_timestamp)
    return {
        "dataType": data_type,
        "availabilityPolicy": policy,
        "eventTimestamp": _iso(event),
        "observedAt": _iso(observed),
        "publishedAt": _iso(published),
        "availableAt": _iso(available),
        "sourceTimestamp": _iso(source),
        "ageSeconds": max(0.0, (observed - event).total_seconds()),
        "publicationLagSeconds": max(0.0, (published - event).total_seconds()),
    }


def funding_availability(
    *,
    event_timestamp: datetime,
    observed_at: datetime,
    published_at: datetime | None = None,
    predicted: bool,
    contemporaneous_public_proof: bool = False,
) -> dict[str, Any]:
    """Record settled or predicted funding without granting premature availability."""

    if predicted and not contemporaneous_public_proof:
        raise ValueError("predicted funding requires contemporaneous public availability proof")
    published = published_at or observed_at
    available = max(_utc(event_timestamp), _utc(observed_at), _utc(published))
    return _record(
        event_timestamp=event_timestamp,
        observed_at=observed_at,
        published_at=published,
        available_at=available,
        source_timestamp=event_timestamp,
        data_type="predicted_funding" if predicted else "settled_funding",
        policy=(
            "contemporaneous_public_prediction"
            if predicted
            else "settlement_then_publication"
        ),
    )


def oi_availability(
    *,
    source_timestamp: datetime,
    observed_at: datetime,
    source_period_seconds: int,
    publication_latency_proven: bool,
    published_at: datetime | None = None,
) -> dict[str, Any]:
    if source_period_seconds <= 0:
        raise ValueError("source_period_seconds must be positive")
    published = published_at or observed_at
    if publication_latency_proven:
        available = max(_utc(source_timestamp), _utc(observed_at), _utc(published))
        policy = "proven_publication_timestamp"
    else:
        available = max(
            _utc(observed_at),
            _utc(source_timestamp) + timedelta(seconds=source_period_seconds),
        )
        policy = "one_source_period_conservative_delay"
    return _record(
        event_timestamp=source_timestamp,
        observed_at=observed_at,
        published_at=published,
        available_at=available,
        source_timestamp=source_timestamp,
        data_type="open_interest",
        policy=policy,
    )


def pit_snapshot_availability(
    *,
    source_timestamp: datetime,
    source_bar_close: datetime,
    observed_at: datetime,
) -> dict[str, Any]:
    available = max(_utc(source_bar_close), _utc(observed_at))
    return _record(
        event_timestamp=source_timestamp,
        observed_at=observed_at,
        published_at=available,
        available_at=available,
        source_timestamp=source_timestamp,
        data_type="pit_universe_snapshot",
        policy="completed_source_bar_only",
    )
