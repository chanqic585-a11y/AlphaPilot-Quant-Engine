"""Frozen, bounded event prefilter for the automatic research program."""

from __future__ import annotations

from collections import Counter
from typing import Any, Mapping, Sequence

from alphapilot.evolution.registry.hashing import stable_hash
from alphapilot.research_screening.campaign_metrics import summarize_events


PREFILTER_GATE_POLICY: dict[str, Any] = {
    "schemaVersion": "automatic_prefilter_gate_policy_v1",
    "policyId": "automatic_directional_event_prefilter_v1",
    "minimumEvents": 30,
    "minimumProfitFactor": 1.03,
    "minimumAverageNetR": 0.0,
    "minimumTotalNetR": 0.0,
    "minimumStressProfitFactor": 1.0,
    "minimumStressAverageNetR": 0.0,
    "minimumBenchmarkIncrementNetR": 0.0,
    "maximumSingleInstrumentPositiveContribution": 0.45,
    "maximumSingleMonthPositiveContribution": 0.35,
    "minimumPositiveMonthRatio": 0.50,
    "targetRGateMode": "advisory",
    "universalTwoRHardGate": False,
    "resultDrivenRelaxationForbidden": True,
}
PREFILTER_GATE_POLICY_HASH = stable_hash(
    PREFILTER_GATE_POLICY, prefix="automatic_prefilter_gate_policy"
)


def _gate(observed: float | int, operator: str, required: float | int) -> dict[str, Any]:
    comparisons = {
        ">=": observed >= required,
        ">": observed > required,
        "<=": observed <= required,
    }
    core = {"observed": observed, "operator": operator, "required": required}
    return {
        **core,
        "passed": comparisons[operator],
        "evidenceHash": stable_hash(core, prefix="automatic_prefilter_gate_evidence"),
    }


def _diagnostics(events: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    rows = [dict(row) for row in events]
    denominator = len(rows) or 1
    exits = Counter(str(row.get("exitReason") or "unknown") for row in rows)
    return {
        "averageMfeR": sum(float(row.get("mfeR") or 0.0) for row in rows) / denominator,
        "averageMaeR": sum(float(row.get("maeR") or 0.0) for row in rows) / denominator,
        "exitReasons": dict(sorted(exits.items())),
    }


def evaluate_prefilter_events(
    *,
    candidate_id: str,
    family_id: str,
    base_events: Sequence[Mapping[str, Any]],
    stress_events: Sequence[Mapping[str, Any]],
    benchmark_events: Sequence[Mapping[str, Any]],
    policy: Mapping[str, Any] = PREFILTER_GATE_POLICY,
) -> dict[str, Any]:
    base = summarize_events(base_events)
    stress = summarize_events(stress_events)
    benchmark = summarize_events(benchmark_events)
    benchmark_increment = float(base["totalNetR"]) - float(benchmark["totalNetR"])
    observed = {
        "minimumEvents": base["eventCount"],
        "minimumProfitFactor": base["profitFactor"],
        "minimumAverageNetR": base["averageNetR"],
        "minimumTotalNetR": base["totalNetR"],
        "minimumStressProfitFactor": stress["profitFactor"],
        "minimumStressAverageNetR": stress["averageNetR"],
        "minimumBenchmarkIncrementNetR": benchmark_increment,
        "maximumSingleInstrumentPositiveContribution": base[
            "singleInstrumentPositiveContribution"
        ],
        "maximumSingleMonthPositiveContribution": base[
            "singleMonthPositiveContribution"
        ],
        "minimumPositiveMonthRatio": base["positiveMonthRatio"],
    }
    operators = {
        "minimumEvents": ">=",
        "minimumProfitFactor": ">",
        "minimumAverageNetR": ">",
        "minimumTotalNetR": ">",
        "minimumStressProfitFactor": ">=",
        "minimumStressAverageNetR": ">",
        "minimumBenchmarkIncrementNetR": ">",
        "maximumSingleInstrumentPositiveContribution": "<=",
        "maximumSingleMonthPositiveContribution": "<=",
        "minimumPositiveMonthRatio": ">=",
    }
    gates = {
        name: _gate(observed[name], operators[name], policy[name]) for name in operators
    }
    failed = sorted(name for name, row in gates.items() if not row["passed"])
    return {
        "schemaVersion": "automatic_prefilter_candidate_result_v1",
        "candidateId": candidate_id,
        "familyId": family_id,
        "passed": not failed,
        "targetRGateMode": "advisory",
        "universalTwoRHardGate": False,
        "gatePolicyHash": PREFILTER_GATE_POLICY_HASH,
        "metrics": {
            **base,
            **_diagnostics(base_events),
            "stressProfitFactor": stress["profitFactor"],
            "stressAverageNetR": stress["averageNetR"],
            "stressTotalNetR": stress["totalNetR"],
            "benchmarkTotalNetR": benchmark["totalNetR"],
            "benchmarkIncrementNetR": benchmark_increment,
        },
        "gates": gates,
        "failedGates": failed,
        "formalPassClaimCount": 0,
        "lockedOosAccessCount": 0,
    }


def build_prefilter_route(results: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    eligible = [dict(row) for row in results if bool(row.get("passed"))]
    eligible.sort(
        key=lambda row: (
            -float(row.get("metrics", {}).get("stressProfitFactor") or 0.0),
            -float(row.get("metrics", {}).get("benchmarkIncrementNetR") or 0.0),
            float(row.get("metrics", {}).get("maximumDrawdownPct") or 999.0),
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
        if len(selected) == 6:
            break
    read_trials = sorted(
        str(row["candidateId"])
        for row in eligible
        if str(row["candidateId"]) not in selected
    )
    failed = sorted(str(row["candidateId"]) for row in results if not row.get("passed"))
    return {
        "schemaVersion": "automatic_prefilter_route_v1",
        "formalCandidateIds": selected,
        "readTrialCandidateIds": read_trials,
        "prefilterFailedCandidateIds": failed,
        "maximumFormalCandidates": 6,
        "maximumPerFamily": 1,
        "formalRunCount": 0,
        "resultReadCount": 0,
        "formalPassClaimCount": 0,
        "releaseCount": 0,
        "demoArm": False,
        "orderCount": 0,
        "terminalRoute": None if selected else "completed_zero_prefilter_survivors",
    }


__all__ = [
    "PREFILTER_GATE_POLICY",
    "PREFILTER_GATE_POLICY_HASH",
    "build_prefilter_route",
    "evaluate_prefilter_events",
]
