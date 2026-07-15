"""Causal clock helpers shared by event and portfolio research engines."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, Sequence


UTC = timezone.utc


def parse_utc(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("causal timestamps must be timezone-aware")
    return parsed.astimezone(UTC)


def is_available_at(observation: Mapping[str, Any], decision_time: str | datetime) -> bool:
    available_at = observation.get("availableAt")
    if available_at is None:
        return False
    return parse_utc(available_at) <= parse_utc(decision_time)


def next_tradable_bar(
    bars: Sequence[Mapping[str, Any]],
    decision_time: str | datetime,
) -> dict[str, Any]:
    decision = parse_utc(decision_time)
    candidates = [
        dict(bar)
        for bar in bars
        if bar.get("openTime") is not None and parse_utc(bar["openTime"]) > decision
    ]
    if not candidates:
        raise LookupError("no tradable bar exists after the decision timestamp")
    return min(candidates, key=lambda bar: parse_utc(bar["openTime"]))
