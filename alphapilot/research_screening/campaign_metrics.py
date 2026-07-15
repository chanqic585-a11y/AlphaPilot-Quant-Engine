"""Cost-aware campaign summaries and explicit evidence-bound gate rows."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from alphapilot.evolution.registry.hashing import stable_hash


def selection_events(events: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [dict(event) for event in events if event.get("split") in {"development", "walk_forward"}]


def _positive_concentration(rows: Sequence[Mapping[str, Any]], key: str) -> float:
    totals: dict[str, float] = {}
    for row in rows:
        value = float(row.get("netR") or 0.0)
        if value > 0:
            identity = str(row.get(key) or "unknown")
            totals[identity] = totals.get(identity, 0.0) + value
    total = sum(totals.values())
    return max(totals.values()) / total if total else 0.0


def _month(row: Mapping[str, Any]) -> str:
    return str(row.get("entryTimestamp") or row.get("timestamp") or "unknown")[:7]


def summarize_events(events: Sequence[Mapping[str, Any]], *, risk_fraction: float = 0.01) -> dict[str, Any]:
    rows = [dict(event) for event in events]
    values = [float(row.get("netR") or 0.0) for row in rows]
    wins = sum(value for value in values if value > 0)
    losses = abs(sum(value for value in values if value < 0))
    profit_factor = wins / losses if losses else (999.0 if wins else 0.0)
    cumulative = 0.0
    peak = 0.0
    maximum_drawdown_r = 0.0
    for value in values:
        cumulative += value
        peak = max(peak, cumulative)
        maximum_drawdown_r = max(maximum_drawdown_r, peak - cumulative)
    month_totals: dict[str, float] = {}
    for row, value in zip(rows, values):
        month_totals[_month(row)] = month_totals.get(_month(row), 0.0) + value
    fold_rows: dict[str, list[float]] = {}
    for row, value in zip(rows, values):
        fold = str(row.get("foldId") or "")
        if row.get("split") == "walk_forward" and fold:
            fold_rows.setdefault(fold, []).append(value)
    fold_metrics = {
        fold: {
            "eventCount": len(fold_values),
            "averageNetR": sum(fold_values) / len(fold_values),
            "positive": sum(fold_values) / len(fold_values) > 0,
        }
        for fold, fold_values in sorted(fold_rows.items())
    }
    return {
        "eventCount": len(rows),
        "profitFactor": profit_factor,
        "averageNetR": sum(values) / len(values) if values else 0.0,
        "totalNetR": sum(values),
        "maximumDrawdownR": maximum_drawdown_r,
        "maximumDrawdownPct": maximum_drawdown_r * risk_fraction * 100,
        "positiveMonthRatio": (
            sum(value > 0 for value in month_totals.values()) / len(month_totals)
            if month_totals
            else 0.0
        ),
        "observedMonthCount": len(month_totals),
        "singleInstrumentPositiveContribution": _positive_concentration(rows, "symbol"),
        "singleMonthPositiveContribution": _positive_concentration(
            [{**row, "month": _month(row)} for row in rows], "month"
        ),
        "folds": fold_metrics,
        "positiveFoldCount": sum(bool(row["positive"]) for row in fold_metrics.values()),
    }


def _with_cost_multiplier(event: Mapping[str, Any], multiplier: float) -> dict[str, Any]:
    costs = sum(
        float(event.get(key) or 0.0)
        for key in ("feesR", "slippageR", "fundingR", "spreadProxyR")
    )
    return {**event, "netR": float(event.get("grossR") or 0.0) - costs * multiplier}


def _comparison(observed: float | int, operator: str, required: float | int) -> bool:
    if operator == ">=":
        return observed >= required
    if operator == ">":
        return observed > required
    if operator == "<=":
        return observed <= required
    if operator == "==":
        return observed == required
    raise ValueError(f"unsupported gate operator: {operator}")


def _gate_row(name: str, observed: float | int, rule: Mapping[str, Any]) -> dict[str, Any]:
    required = rule["required"]
    operator = str(rule["operator"])
    passed = _comparison(observed, operator, required)
    core = {"name": name, "observed": observed, "operator": operator, "required": required}
    return {
        "passed": passed,
        "observed": observed,
        "required": f"{operator} {required}",
        "evidenceHash": stable_hash(core, prefix="gate_evidence"),
        "reasonZh": "达到预注册门槛。" if passed else "未达到预注册门槛。",
    }


def _gate_group(observed: Mapping[str, float | int], rules: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    return {name: _gate_row(name, observed[name], rule) for name, rule in rules.items()}


def evaluate_candidate_gates(
    *,
    events: Sequence[Mapping[str, Any]],
    timeframe: str,
    preregistration: Mapping[str, Any],
    holdout_access_before_final_evaluation: int,
) -> dict[str, Any]:
    development = [dict(row) for row in events if row.get("split") == "development"]
    walk_forward = [dict(row) for row in events if row.get("split") == "walk_forward"]
    holdout = [dict(row) for row in events if row.get("split") == "holdout"]
    development_summary = summarize_events(development)
    oos_rows = walk_forward + holdout
    oos_summary = summarize_events(oos_rows)
    stress_summary = summarize_events([_with_cost_multiplier(row, 1.5) for row in oos_rows])
    stress_2x_summary = summarize_events([_with_cost_multiplier(row, 2.0) for row in oos_rows])
    sample_rule = preregistration["sampleGates"][timeframe]
    sample_observed = {
        "minimumEvents": development_summary["eventCount"],
        "minimumMonths": development_summary["observedMonthCount"],
    }
    sample_gates = {
        name: _gate_row(name, sample_observed[name], {"operator": ">=", "required": required})
        for name, required in sample_rule.items()
    }
    prescreen_observed = {
        "developmentProfitFactor": development_summary["profitFactor"],
        "developmentAverageNetR": development_summary["averageNetR"],
        "positiveDevelopmentMonthRatio": development_summary["positiveMonthRatio"],
    }
    prescreen_gates = _gate_group(prescreen_observed, preregistration["prescreenGates"])
    base_observed = {
        "oosProfitFactor": oos_summary["profitFactor"],
        "oosAverageNetR": oos_summary["averageNetR"],
        "oosTotalNetR": oos_summary["totalNetR"],
        "maximumDrawdownPct": oos_summary["maximumDrawdownPct"],
        "positiveFoldCount": oos_summary["positiveFoldCount"],
    }
    base_gates = _gate_group(base_observed, preregistration["baseGates"])
    formal_observed = {
        **base_observed,
        "stress1_5xProfitFactor": stress_summary["profitFactor"],
        "stress1_5xAverageNetR": stress_summary["averageNetR"],
        "singleInstrumentPositiveContribution": oos_summary["singleInstrumentPositiveContribution"],
        "singleMonthPositiveContribution": oos_summary["singleMonthPositiveContribution"],
        "holdoutAccessBeforeFinalEvaluation": holdout_access_before_final_evaluation,
    }
    formal_gates = _gate_group(formal_observed, preregistration["formalGates"])
    sample_passed = all(row["passed"] for row in sample_gates.values())
    prescreen_passed = sample_passed and all(row["passed"] for row in prescreen_gates.values())
    base_passed = prescreen_passed and all(row["passed"] for row in base_gates.values())
    formal_passed = base_passed and all(row["passed"] for row in formal_gates.values())
    return {
        "sampleGates": sample_gates,
        "prescreenGates": prescreen_gates,
        "baseGates": base_gates,
        "formalGates": formal_gates,
        "samplePassed": sample_passed,
        "prescreenPassed": prescreen_passed,
        "basePassed": base_passed,
        "formalPassed": formal_passed,
        "developmentMetrics": development_summary,
        "walkForwardMetrics": summarize_events(walk_forward),
        "holdoutMetrics": summarize_events(holdout),
        "oosMetrics": oos_summary,
        "stress1_5xMetrics": stress_summary,
        "stress2xMetrics": stress_2x_summary,
    }
