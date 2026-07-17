"""Stable event identity retained by the S01 candidate adapter."""

from __future__ import annotations

from typing import Any, Mapping


def with_s01_signal_id(event: Mapping[str, Any]) -> dict[str, Any]:
    """Return an S01 event with its historical evidence identity preserved."""

    row = dict(event)
    row.setdefault(
        "signalId",
        "s01_formal::"
        f"{row['symbol']}::{row['signalTimestamp']}",
    )
    return row
