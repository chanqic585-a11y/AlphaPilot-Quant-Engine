from __future__ import annotations

from typing import Any, Iterable, Sequence


def _summary(values: Sequence[float]) -> dict[str, Any]:
    positive = sum(value for value in values if value > 0)
    negative = abs(sum(value for value in values if value < 0))
    return {
        "tradeCount": len(values),
        "profitFactor": round(positive / negative, 12) if negative else None,
        "profitFactorUnbounded": bool(positive and not negative),
        "averageNetR": round(sum(values) / len(values), 12) if values else None,
        "totalNetR": round(sum(values), 12),
    }


def evaluate_cost_scenarios(
    trades: Iterable[dict[str, Any]], *, multipliers: Sequence[float]
) -> dict[str, Any]:
    rows = [dict(row) for row in trades]
    total_gross = sum(float(row.get("grossR") or 0) for row in rows)
    total_friction = sum(
        float(row.get("feeR") or 0) + float(row.get("slippageR") or 0)
        for row in rows
    )
    total_funding = sum(float(row.get("fundingR") or 0) for row in rows)
    scenarios: dict[str, dict[str, Any]] = {}
    for multiplier in multipliers:
        values = [
            float(row.get("grossR") or 0)
            - multiplier
            * (float(row.get("feeR") or 0) + float(row.get("slippageR") or 0))
            - float(row.get("fundingR") or 0)
            for row in rows
        ]
        scenario = _summary(values)
        scenario.update(
            {
                "multiplier": multiplier,
                "feeR": round(
                    sum(float(row.get("feeR") or 0) for row in rows) * multiplier,
                    12,
                ),
                "slippageR": round(
                    sum(float(row.get("slippageR") or 0) for row in rows)
                    * multiplier,
                    12,
                ),
                "fundingR": round(total_funding, 12),
                "costShareOfGrossProfit": (
                    (total_friction * multiplier + total_funding) / total_gross
                    if total_gross > 0
                    else None
                ),
            }
        )
        scenarios[str(multiplier)] = scenario
    break_even_raw = (
        (total_gross - total_funding) / total_friction
        if total_friction > 0
        else None
    )
    return {
        "scenarios": scenarios,
        "breakEvenCostMultiplier": (
            round(break_even_raw, 12) if break_even_raw is not None else None
        ),
        "fundingStatus": (
            "recorded_actual" if any(float(row.get("fundingR") or 0) for row in rows)
            else "recorded_zero_or_unavailable"
        ),
        "fundingLimitation": (
            None
            if any(float(row.get("fundingR") or 0) for row in rows)
            else "zero funding rows cannot prove complete historical funding coverage"
        ),
    }
