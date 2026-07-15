"""Purge, embargo, and split-boundary guards for event labels."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Mapping, Sequence

from .causal_clock import parse_utc


@dataclass(frozen=True)
class SplitWindow:
    split_id: str
    starts_at: datetime
    ends_at: datetime

    def __post_init__(self) -> None:
        if parse_utc(self.starts_at) >= parse_utc(self.ends_at):
            raise ValueError("split window start must precede end")


def guard_split_events(
    *,
    events: Sequence[Mapping[str, Any]],
    windows: Sequence[SplitWindow],
    purge_seconds: int,
    embargo_seconds: int,
    maximum_holding_seconds: int,
) -> dict[str, Any]:
    if purge_seconds < maximum_holding_seconds:
        raise ValueError("purge_seconds must cover maximum_holding_seconds")
    if embargo_seconds < 0:
        raise ValueError("embargo_seconds cannot be negative")
    by_id = {window.split_id: window for window in windows}
    accepted: list[dict[str, Any]] = []
    dropped: list[dict[str, Any]] = []

    for raw in events:
        row = dict(raw)
        window = by_id.get(str(row.get("splitId")))
        if window is None:
            dropped.append({**row, "reason": "unknown_split"})
            continue
        decision = parse_utc(row["decisionTime"])
        entry = parse_utc(row["entryTime"])
        exit_time = parse_utc(row["exitTime"])
        start = parse_utc(window.starts_at)
        end = parse_utc(window.ends_at)

        if not (start <= decision <= entry < exit_time <= end):
            dropped.append(
                {**row, "reason": "holding_interval_crosses_split_boundary"}
            )
            continue
        if decision < start + timedelta(seconds=embargo_seconds):
            dropped.append({**row, "reason": "embargo_window"})
            continue
        if exit_time > end - timedelta(seconds=purge_seconds):
            dropped.append({**row, "reason": "purge_window"})
            continue
        accepted.append(row)

    return {
        "accepted": accepted,
        "dropped": dropped,
        "acceptedCount": len(accepted),
        "droppedCount": len(dropped),
        "purgeSeconds": purge_seconds,
        "embargoSeconds": embargo_seconds,
        "maximumHoldingSeconds": maximum_holding_seconds,
    }
