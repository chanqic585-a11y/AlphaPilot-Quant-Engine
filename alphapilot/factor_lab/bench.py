"""Research-only factor bench summaries."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable


def summarize_factor_bench(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["factorId"])].append(dict(row))
    result: list[dict[str, Any]] = []
    for factor_id in sorted(grouped):
        samples = grouped[factor_id]
        values = [float(row["ic"]) for row in samples if row.get("ic") is not None]
        result.append(
            {
                "factorId": factor_id,
                "sampleCount": len(samples),
                "meanIc": sum(values) / len(values) if values else None,
                "qualificationScope": "research_only",
                "strategyFormalPass": False,
            }
        )
    return result
