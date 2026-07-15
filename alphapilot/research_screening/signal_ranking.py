"""Deterministic ranking using only contemporaneously available signal fields."""

from __future__ import annotations

from typing import Any, Mapping, Sequence


def rank_signals(signals: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        (dict(row) for row in signals),
        key=lambda row: (
            -float(row.get("dataFreshness", 0.0)),
            -float(row.get("liquidityScore", 0.0)),
            -float(row.get("mechanismStrength", 0.0)),
            -float(row.get("residualExtremeness", 0.0)),
            -float(row.get("fundingExtremeness", 0.0)),
            -float(row.get("OIChangeStrength", 0.0)),
            str(row.get("candidateId", "")),
            str(row.get("symbol", "")),
        ),
    )
