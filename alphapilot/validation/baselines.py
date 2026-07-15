from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable


def build_baseline_report(
    trades: Iterable[dict[str, Any]], *, direction: str
) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in trades:
        groups[str(row.get("instrumentId") or "unknown")].append(dict(row))
    returns: dict[str, float] = {}
    for instrument, rows in groups.items():
        ordered = sorted(rows, key=lambda row: int(row.get("entryTimestampMs") or 0))
        entry = float(ordered[0].get("entryReferencePrice") or 0)
        exit_price = float(ordered[-1].get("exitReferencePrice") or 0)
        if entry <= 0 or exit_price <= 0:
            continue
        raw = (exit_price / entry - 1) * 100
        returns[instrument] = raw if direction == "long" else -raw
    equal_weight = sum(returns.values()) / len(returns) if returns else None
    return {
        "noTrade": {
            "returnPct": 0.0,
            "maximumDrawdownPct": 0.0,
            "purpose": "capital preservation reference",
        },
        "simpleDirectional": {
            "direction": direction,
            "instrumentCount": len(returns),
            "equalWeightReturnPct": round(equal_weight, 10)
            if equal_weight is not None
            else None,
            "instrumentReturnsPct": returns,
            "basis": "first-entry to last-exit reference prices in formal evidence span",
            "diagnosticOnly": True,
            "limitation": "not a point-in-time investable universe benchmark",
        },
    }
