"""Candidate-neutral end-to-end data dependency contracts."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from alphapilot.evolution.registry.hashing import stable_hash


def _fields(values: Iterable[object] | None) -> list[str]:
    return sorted({str(value) for value in (values or ()) if str(value)})


def _union(*groups: Iterable[object]) -> list[str]:
    return sorted({str(value) for group in groups for value in group if str(value)})


def build_end_to_end_data_contract(
    *,
    candidate_spec: Mapping[str, Any],
    ranking_required_fields: Iterable[str] = (),
    exit_required_fields: Iterable[str] = (),
    capital_required_fields: Iterable[str] = (),
    cost_required_fields: Iterable[str] = (),
    benchmark_required_fields: Iterable[str] = (),
    statistical_required_fields: Iterable[str] = (),
    demo_execution_required_fields: Iterable[str] = (),
    optional_diagnostic_fields: Iterable[str] = (),
) -> dict[str, Any]:
    """Freeze every field needed from signal generation through Demo execution."""

    signal = _fields(candidate_spec.get("requiredFields") or ())
    ranking = _fields(ranking_required_fields)
    exit_fields = _fields(exit_required_fields)
    capital = _fields(capital_required_fields)
    costs = _fields(cost_required_fields)
    benchmark = _fields(benchmark_required_fields)
    statistics = _fields(statistical_required_fields)
    demo_execution = _fields(demo_execution_required_fields)
    optional = _fields(optional_diagnostic_fields)
    formal = _union(signal, ranking, exit_fields, capital, costs, benchmark)
    demo = [*formal, *(field for field in demo_execution if field not in formal)]

    payload: dict[str, Any] = {
        "schemaVersion": "end_to_end_data_contract_v1",
        "candidateId": str(candidate_spec.get("candidateId") or ""),
        "signalRequiredFields": signal,
        "rankingRequiredFields": ranking,
        "exitRequiredFields": exit_fields,
        "capitalRequiredFields": capital,
        "costRequiredFields": costs,
        "benchmarkRequiredFields": benchmark,
        "statisticalRequiredFields": statistics,
        "demoExecutionRequiredFields": demo_execution,
        "optionalDiagnosticFields": optional,
        "formalRequiredFields": formal,
        "demoRequiredFields": demo,
        "readinessLevels": ["signal_ready", "formal_ready", "demo_ready"],
        "missingDataPolicy": "fail_closed_before_the_next_irreversible_stage",
    }
    payload["contractHash"] = stable_hash(payload, prefix="end_to_end_data_contract")
    return payload
