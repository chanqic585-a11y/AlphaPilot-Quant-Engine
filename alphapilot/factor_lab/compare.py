"""Deterministic factor comparison helpers."""

from __future__ import annotations

from typing import Any, Iterable


def rank_factor_bench(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    ranked = sorted(
        (dict(row) for row in rows),
        key=lambda row: (
            -(float(row.get("rankIc") or row.get("ic") or float("-inf"))),
            str(row.get("factorId") or ""),
        ),
    )
    return [dict(row, researchRank=index) for index, row in enumerate(ranked, 1)]
