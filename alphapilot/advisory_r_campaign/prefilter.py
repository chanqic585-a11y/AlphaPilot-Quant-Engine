"""Advisory-R economic prefilter and bounded family routing."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Mapping, Sequence

from alphapilot.research_screening.campaign_metrics import summarize_events


def _gate(observed: float | int, operator: str, required: float | int) -> dict[str, Any]:
    comparisons = {
        ">=": observed >= required,
        ">": observed > required,
        "<=": observed <= required,
    }
    return {
        "observed": observed,
        "operator": operator,
        "required": required,
        "passed": comparisons[operator],
    }


def _exit_diagnostics(events: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    rows = [dict(row) for row in events]
    gross = [float(row.get("realizedGrossR") or row.get("grossR") or 0.0) for row in rows]
    net = [float(row.get("realizedNetR") or row.get("netR") or 0.0) for row in rows]
    wins = [value for value in net if value > 0]
    losses = [value for value in net if value < 0]
    average_win = sum(wins) / len(wins) if wins else 0.0
    average_loss = sum(losses) / len(losses) if losses else 0.0
    payoff = average_win / abs(average_loss) if average_loss else (999.0 if average_win else 0.0)
    counts = defaultdict(int)
    for row in rows:
        counts[str(row.get("exitReason") or "unknown")] += 1
    denominator = len(rows) or 1
    return {
        "averageRealizedGrossR": sum(gross) / len(gross) if gross else 0.0,
        "averageRealizedNetR": sum(net) / len(net) if net else 0.0,
        "averageWinR": average_win,
        "averageLossR": average_loss,
        "payoffRatio": payoff,
        "breakEvenWinRate": 1.0 / (1.0 + payoff) if payoff > 0 else 1.0,
        "partialExitRatio": sum(bool(row.get("partialExit")) for row in rows) / denominator,
        "trailingExitRatio": counts["trailing"] / denominator,
        "structureExitRatio": counts["structure"] / denominator,
        "timeExitRatio": counts["time"] / denominator,
        "stopRatio": counts["stop"] / denominator,
        "averageMfeR": sum(float(row.get("mfeR") or 0.0) for row in rows) / denominator,
        "averageMaeR": sum(float(row.get("maeR") or 0.0) for row in rows) / denominator,
        "averageProfitGivebackR": sum(float(row.get("profitGivebackR") or 0.0) for row in rows) / denominator,
        "stopThenRecoverCount": sum(bool(row.get("stopThenRecover")) for row in rows),
    }


def evaluate_candidate(
    candidate: Mapping[str, Any],
    events: Sequence[Mapping[str, Any]],
    *,
    gates: Mapping[str, float | int],
) -> dict[str, Any]:
    rows = [dict(row) for row in events]
    metrics = summarize_events(rows)
    observed_months = int(metrics["observedMonthCount"])
    history_gate = _gate(observed_months, ">=", int(gates.get("minimumHistoryMonths", 0)))
    average_required = float(
        gates.get("minimumAverageRealizedNetR", gates.get("minimumAverageNetR", 0.0))
    )
    total_required = float(
        gates.get("minimumTotalRealizedNetR", gates.get("minimumTotalNetR", 0.0))
    )
    if "maximumDrawdownPct" in gates:
        drawdown_observed = float(metrics["maximumDrawdownPct"])
        drawdown_required = float(gates["maximumDrawdownPct"])
    else:
        drawdown_observed = float(metrics["maximumDrawdownPct"]) / 100.0
        drawdown_required = float(gates.get("maximumDrawdown", 1.0))
    gate_rows = {
        "minimumEvents": _gate(metrics["eventCount"], ">=", int(gates["minimumEvents"])),
        "minimumProfitFactor": _gate(metrics["profitFactor"], ">=", float(gates["minimumProfitFactor"])),
        "minimumAverageRealizedNetR": _gate(metrics["averageNetR"], ">", average_required),
        "minimumTotalRealizedNetR": _gate(metrics["totalNetR"], ">", total_required),
        "minimumPositiveMonthRatio": _gate(metrics["positiveMonthRatio"], ">=", float(gates["minimumPositiveMonthRatio"])),
        "maximumDrawdownPct": _gate(drawdown_observed, "<=", drawdown_required),
        "minimumHistoryMonths": history_gate,
    }
    failed = sorted(name for name, row in gate_rows.items() if not row["passed"])
    parameters = dict(candidate.get("exitPolicy", {}).get("parameters") or {})
    result = {
        "candidateId": candidate["candidateId"],
        "familyId": candidate["familyId"],
        "variantId": candidate.get("variantId"),
        "diagnosticOnly": bool(candidate.get("diagnosticOnly")),
        "strategyType": candidate["strategyType"],
        "eventCount": metrics["eventCount"],
        "metrics": metrics,
        "exitPolicyMode": candidate["exitPolicy"]["mode"],
        "exitPolicyHash": candidate.get("exitPolicyHash"),
        "exitDiagnostics": _exit_diagnostics(rows),
        "targetRAdvisory": parameters.get("targetR"),
        "targetRGateMode": "advisory",
        "gates": gate_rows,
        "failedGates": failed,
        "passed": not failed and not bool(candidate.get("diagnosticOnly")),
        "maximumDrawdown": metrics["maximumDrawdownPct"] / 100.0,
        "turnover": float(metrics["eventCount"]),
        "simpleBenchmarkIncrement": metrics["totalNetR"],
        "complexityScore": int(candidate.get("complexityScore") or 0),
    }
    return result


def evaluate_portfolio_candidate(
    candidate: Mapping[str, Any],
    events: Sequence[Mapping[str, Any]],
    *,
    gates: Mapping[str, float | int],
) -> dict[str, Any]:
    rows = [dict(row) for row in events]
    metrics = summarize_events(rows)
    gate_rows = {
        "minimumNetReturn": _gate(
            metrics["totalNetR"], ">", float(gates["minimumNetReturn"])
        ),
        "minimumPositiveMonthRatio": _gate(
            metrics["positiveMonthRatio"],
            ">=",
            float(gates["minimumPositiveMonthRatio"]),
        ),
        "maximumDrawdownPct": _gate(
            metrics["maximumDrawdownPct"],
            "<=",
            float(gates["maximumDrawdownPct"]),
        ),
        "minimumHistoryMonths": _gate(
            metrics["observedMonthCount"],
            ">=",
            int(gates["minimumHistoryMonths"]),
        ),
    }
    failed = sorted(name for name, row in gate_rows.items() if not row["passed"])
    return {
        "candidateId": candidate["candidateId"],
        "familyId": candidate["familyId"],
        "variantId": candidate["variantId"],
        "diagnosticOnly": bool(candidate.get("diagnosticOnly")),
        "strategyType": "portfolio",
        "eventCount": metrics["eventCount"],
        "metrics": metrics,
        "exitPolicyMode": candidate["exitPolicy"]["mode"],
        "exitPolicyHash": candidate["exitPolicyHash"],
        "exitDiagnostics": _exit_diagnostics(rows),
        "targetRAdvisory": None,
        "targetRGateMode": "advisory",
        "gates": gate_rows,
        "failedGates": failed,
        "passed": not failed and not bool(candidate.get("diagnosticOnly")),
        "maximumDrawdown": metrics["maximumDrawdownPct"] / 100.0,
        "turnover": float(metrics["eventCount"]),
        "simpleBenchmarkIncrement": metrics["totalNetR"],
        "complexityScore": int(candidate["complexityScore"]),
    }


def route_prefilter_survivors(
    results: Sequence[Mapping[str, Any]], *, maximum_survivors: int
) -> dict[str, Any]:
    diagnostics = sorted(
        str(row["candidateId"]) for row in results if bool(row.get("diagnosticOnly"))
    )
    eligible = [
        dict(row)
        for row in results
        if bool(row.get("passed")) and not bool(row.get("diagnosticOnly"))
    ]
    eligible.sort(
        key=lambda row: (
            int(row.get("complexityScore") or 0),
            float(row.get("turnover") or 0.0),
            float(row.get("maximumDrawdown") or 0.0),
            -float(row.get("simpleBenchmarkIncrement") or 0.0),
            str(row["candidateId"]),
        )
    )
    selected: list[str] = []
    selected_families: set[str] = set()
    for row in eligible:
        family = str(row["familyId"])
        if family in selected_families:
            continue
        selected.append(str(row["candidateId"]))
        selected_families.add(family)
        if len(selected) >= maximum_survivors:
            break
    failed = sorted(
        str(row["candidateId"])
        for row in results
        if not bool(row.get("passed")) and not bool(row.get("diagnosticOnly"))
    )
    family_duplicates = sorted(
        str(row["candidateId"])
        for row in eligible
        if str(row["candidateId"]) not in selected
    )
    return {
        "formalCandidateIds": selected,
        "archivedCandidateIds": failed + family_duplicates,
        "diagnosticCandidateIds": diagnostics,
        "formalStageAllowed": bool(selected),
        "hardStopReason": None if selected else "zero_prefilter_survivors",
        "maximumSurvivors": maximum_survivors,
        "maximumPerFamily": 1,
        "demoReleaseCount": 0,
        "demoArm": False,
        "orderCount": 0,
    }
