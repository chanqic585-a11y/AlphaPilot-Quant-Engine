"""Deterministic as-of join constrained by public availability timestamps."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from .causal_clock import is_available_at, parse_utc


def causal_asof_join(
    *,
    decisions: Sequence[Mapping[str, Any]],
    observations: Sequence[Mapping[str, Any]],
    identity_field: str = "symbol",
    decision_time_field: str = "signalDecisionTime",
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for decision in decisions:
        decision_time = decision.get(decision_time_field)
        if decision_time is None:
            raise ValueError(f"decision is missing {decision_time_field}")
        matches = [
            row
            for row in observations
            if row.get(identity_field) == decision.get(identity_field)
            and is_available_at(row, decision_time)
        ]
        selected = (
            max(matches, key=lambda row: parse_utc(row["availableAt"])) if matches else None
        )
        rows.append({**dict(decision), "observation": dict(selected) if selected else None})
    return rows
