"""Cost-aware representative-universe prefilter evaluation."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Mapping, Sequence

from alphapilot.research_screening.campaign_metrics import summarize_events


def _comparison(observed: float | int, key: str, required: float | int) -> bool:
    if key in {
        "minimumEvents",
        "minimumProfitFactor",
        "minimumPositiveMonthRatio",
    }:
        return observed >= required
    return observed > required


def _regime_breakdown(
    events: Sequence[Mapping[str, Any]], key: str
) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        grouped[str(event.get(key) or "unknown")].append(dict(event))
    return {
        name: summarize_events(rows)
        for name, rows in sorted(grouped.items())
    }


def evaluate_event_prefilter(
    events: Sequence[Mapping[str, Any]], *, gates: Mapping[str, float | int]
) -> dict[str, Any]:
    rows = [dict(event) for event in events]
    metrics = summarize_events(rows)
    observed = {
        "minimumEvents": metrics["eventCount"],
        "minimumProfitFactor": metrics["profitFactor"],
        "minimumAverageNetR": metrics["averageNetR"],
        "minimumTotalNetR": metrics["totalNetR"],
        "minimumPositiveMonthRatio": metrics["positiveMonthRatio"],
    }
    gate_rows = {
        name: {
            "observed": observed[name],
            "required": required,
            "operator": ">="
            if name
            in {
                "minimumEvents",
                "minimumProfitFactor",
                "minimumPositiveMonthRatio",
            }
            else ">",
            "passed": _comparison(observed[name], name, required),
        }
        for name, required in gates.items()
    }
    failed = sorted(name for name, row in gate_rows.items() if not row["passed"])
    return {
        "passed": not failed,
        "eventCount": metrics["eventCount"],
        "metrics": metrics,
        "gates": gate_rows,
        "failedGates": failed,
        "regimeBreakdown": {
            "marketState": _regime_breakdown(rows, "marketState"),
            "volatilityState": _regime_breakdown(rows, "volatilityState"),
        },
    }


def finalize_prefilter_route(
    results: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    formal = sorted(
        str(row["strategyId"])
        for row in results
        if not bool(row.get("diagnosticOnly"))
        and bool(row.get("prefilter", {}).get("passed"))
    )
    archived = sorted(
        str(row["strategyId"])
        for row in results
        if not bool(row.get("diagnosticOnly"))
        and not bool(row.get("prefilter", {}).get("passed"))
    )
    diagnostics = sorted(
        str(row["strategyId"])
        for row in results
        if bool(row.get("diagnosticOnly"))
    )
    return {
        "formalStrategyIds": formal,
        "archivedStrategyIds": archived,
        "diagnosticStrategyIds": diagnostics,
        "formalStageAllowed": bool(formal),
        "demoReleaseCount": 0,
        "demoArm": False,
        "orderCount": 0,
    }

