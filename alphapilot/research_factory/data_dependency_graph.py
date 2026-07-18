"""Dependency graph and readiness evaluation for end-to-end data contracts."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from alphapilot.evolution.registry.hashing import stable_hash


_LAYERS = {
    "signal": "signalRequiredFields",
    "ranking": "rankingRequiredFields",
    "exit": "exitRequiredFields",
    "capital": "capitalRequiredFields",
    "cost": "costRequiredFields",
    "benchmark": "benchmarkRequiredFields",
    "statistical": "statisticalRequiredFields",
    "demo_execution": "demoExecutionRequiredFields",
    "optional_diagnostic": "optionalDiagnosticFields",
}


def build_data_dependency_graph(contract: Mapping[str, Any]) -> dict[str, Any]:
    edges = [
        {"layer": layer, "field": str(field)}
        for layer, key in _LAYERS.items()
        for field in contract.get(key, ())
    ]
    payload: dict[str, Any] = {
        "schemaVersion": "data_dependency_graph_v1",
        "candidateId": str(contract.get("candidateId") or ""),
        "contractHash": str(contract.get("contractHash") or ""),
        "layers": list(_LAYERS),
        "edges": edges,
    }
    payload["graphHash"] = stable_hash(payload, prefix="data_dependency_graph")
    return payload


def _missing(
    required: list[str],
    field_evidence: Mapping[str, Mapping[str, Any]],
    *,
    minimum_coverage_pct: float,
) -> list[str]:
    missing: list[str] = []
    for field in required:
        evidence = field_evidence.get(field) or {}
        if evidence.get("semanticallyVerified") is not True:
            missing.append(field)
            continue
        if float(evidence.get("coveragePct") or 0.0) < float(minimum_coverage_pct):
            missing.append(field)
    return missing


def evaluate_contract_readiness(
    contract: Mapping[str, Any],
    *,
    field_evidence: Mapping[str, Mapping[str, Any]],
    formal_profile_status: str,
    demo_profile_status: str,
    minimum_coverage_pct: float = 95.0,
) -> dict[str, Any]:
    signal_missing = _missing(
        list(contract.get("signalRequiredFields") or ()),
        field_evidence,
        minimum_coverage_pct=minimum_coverage_pct,
    )
    formal_missing = _missing(
        list(contract.get("formalRequiredFields") or ()),
        field_evidence,
        minimum_coverage_pct=minimum_coverage_pct,
    )
    demo_missing = _missing(
        list(contract.get("demoRequiredFields") or ()),
        field_evidence,
        minimum_coverage_pct=minimum_coverage_pct,
    )
    signal_ready = not signal_missing
    formal_ready = signal_ready and not formal_missing and formal_profile_status == "ready"
    demo_ready = formal_ready and not demo_missing and demo_profile_status == "ready"
    payload: dict[str, Any] = {
        "schemaVersion": "data_contract_readiness_v1",
        "candidateId": str(contract.get("candidateId") or ""),
        "contractHash": str(contract.get("contractHash") or ""),
        "minimumCoveragePct": float(minimum_coverage_pct),
        "signalReady": signal_ready,
        "formalReady": formal_ready,
        "demoReady": demo_ready,
        "signalStatus": "signal_ready" if signal_ready else "signal_data_blocked",
        "formalStatus": "formal_ready" if formal_ready else "formal_data_blocked",
        "demoStatus": "demo_ready" if demo_ready else "demo_data_blocked",
        "missingSignalFields": signal_missing,
        "missingFormalFields": formal_missing,
        "missingDemoFields": demo_missing,
        "formalDataProfileStatus": str(formal_profile_status),
        "demoDataProfileStatus": str(demo_profile_status),
    }
    payload["readinessHash"] = stable_hash(payload, prefix="data_contract_readiness")
    return payload


def build_capital_policy_data_dependencies(
    capital_policy: Mapping[str, Any],
) -> dict[str, Any]:
    capacity_model_hash = str(capital_policy.get("definitionHash") or "")
    payload: dict[str, Any] = {
        "schemaVersion": "capital_policy_data_dependencies_v1",
        "policyHash": str(
            capital_policy.get("capitalHash")
            or capital_policy.get("capitalPolicyHash")
            or capital_policy.get("policyHash")
            or capacity_model_hash
        ),
        "capacityModelHash": capacity_model_hash,
        "requiredFields": [
            "current_equity",
            "entry_price",
            "stop_price",
            "quote_turnover",
            "signal_timestamp",
        ],
        "fieldSemantics": {
            "quote_turnover": [
                "exact_quote_turnover",
                "conservative_quote_turnover_lower_bound",
            ],
            "signal_timestamp": "closed_candle_available_at",
        },
        "minimumLookback": int(capital_policy.get("lookbackCompletedUtcDays") or 0),
        "minimumValidObservations": int(
            capital_policy.get("minimumCompletedUtcDays") or 0
        ),
        "availableAtRules": {
            "quote_turnover": "completed_candle_close_timestamp",
            "capacity_window": "strictly_prior_completed_utc_days_only",
        },
        "missingDataPolicy": str(capital_policy.get("missingDataPolicy") or "reject"),
        "policyComponents": [
            "capacity_model",
            "correlation_cluster",
            "portfolio_beta",
            "ranking",
            "position_sizing",
            "acceptance_sequence",
        ],
    }
    payload["dependencyHash"] = stable_hash(
        payload, prefix="capital_policy_data_dependencies"
    )
    return payload
