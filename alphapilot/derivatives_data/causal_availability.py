"""Causal availability clocks for public derivatives observations."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any


def _parse(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("availability timestamps must include a timezone")
    return parsed.astimezone(timezone.utc)


def _format(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def normalize_availability(record: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    event = _parse(str(record["eventTimestamp"]))
    data_type = str(policy.get("dataType") or record.get("dataType") or "unknown")
    explicit_lag = int(policy.get("publicationLagSeconds") or 0)
    assumption = "explicit_publication_clock"
    candidates = [event + timedelta(seconds=max(0, explicit_lag))]

    for field in ("observedAt", "publishedAt"):
        if record.get(field):
            candidates.append(_parse(str(record[field])))

    if data_type == "open_interest" and not record.get("publishedAt"):
        sampling_interval = int(policy.get("samplingIntervalSeconds") or 0)
        if sampling_interval <= 0:
            raise ValueError("open_interest requires a positive samplingIntervalSeconds")
        candidates.append(event + timedelta(seconds=sampling_interval))
        assumption = "one_sampling_period_lag"
    elif data_type == "funding":
        assumption = "settlement_plus_publication_lag"

    available = max(candidates)
    publication_lag = int((available - event).total_seconds())
    return {
        **record,
        "eventTimestamp": _format(event),
        "observedAt": record.get("observedAt"),
        "publishedAt": record.get("publishedAt"),
        "availableAt": _format(available),
        "sourceTimestamp": record.get("sourceTimestamp") or _format(event),
        "publicationLagSeconds": publication_lag,
        "availabilityAssumption": assumption,
    }
