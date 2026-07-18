"""Capital- and event-comparable benchmark contracts for V28-V32."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from alphapilot.evolution.registry.hashing import stable_hash


_REQUIRED_COMPARABILITY_FIELDS = (
    "signalUniverseId",
    "eligibilityWindowHash",
    "directionPolicy",
    "entryPolicyHash",
    "costPolicyHash",
    "positionCompetitionPolicyHash",
    "capitalPolicyHash",
    "concurrencyPolicyHash",
    "capacityPolicyHash",
)


def build_benchmark_comparability_contract(
    *,
    candidate_id: str,
    benchmark_id: str,
    candidate_contract: Mapping[str, Any],
    benchmark_contract: Mapping[str, Any],
    difference_scope: str,
) -> dict[str, Any]:
    """Prove that candidate and benchmark share the same executable context."""

    if not candidate_id or not benchmark_id:
        raise ValueError("benchmark_identity_missing")
    if difference_scope not in {"exit_only", "full_mechanism"}:
        raise ValueError("unsupported_benchmark_difference_scope")
    allowed = ["exitPolicyHash"]
    if difference_scope == "full_mechanism":
        allowed.append("mechanismId")

    compared: dict[str, dict[str, Any]] = {}
    blockers: list[str] = []
    for field in _REQUIRED_COMPARABILITY_FIELDS:
        candidate_value = candidate_contract.get(field)
        benchmark_value = benchmark_contract.get(field)
        equal = candidate_value not in (None, "") and candidate_value == benchmark_value
        compared[field] = {
            "candidate": candidate_value,
            "benchmark": benchmark_value,
            "equal": equal,
        }
        if not equal:
            blockers.append(field)

    status = "formal_comparable" if not blockers else "diagnostic_only"
    payload: dict[str, Any] = {
        "schemaVersion": "benchmark_comparability_contract_v1",
        "candidateId": candidate_id,
        "benchmarkId": benchmark_id,
        "differenceScope": difference_scope,
        "allowedDifferences": allowed,
        "comparedFields": compared,
        "blockingMismatches": blockers,
        "status": status,
        "formalGateEligible": not blockers,
        "capitalComparable": "capitalPolicyHash" not in blockers,
        "candidateExitPolicyHash": candidate_contract.get("exitPolicyHash"),
        "benchmarkExitPolicyHash": benchmark_contract.get("exitPolicyHash"),
    }
    payload["contractHash"] = stable_hash(payload, prefix="benchmark_comparability")
    return payload


def evaluate_incremental_net_r(
    *,
    candidate_id: str,
    benchmark_id: str,
    candidate_event_net_r: Sequence[float],
    benchmark_event_net_r: Sequence[float],
    candidate_account_path_net_r: Sequence[float],
    benchmark_account_path_net_r: Sequence[float],
    comparability_contract: Mapping[str, Any],
) -> dict[str, Any]:
    """Report event-level and executable account-path incremental net R."""

    if len(candidate_event_net_r) != len(benchmark_event_net_r):
        raise ValueError("event_vector_length_mismatch")
    if not candidate_account_path_net_r or not benchmark_account_path_net_r:
        raise ValueError("account_path_missing")
    if len(candidate_account_path_net_r) != len(benchmark_account_path_net_r):
        raise ValueError("account_path_length_mismatch")

    event_edges = [
        float(candidate) - float(benchmark)
        for candidate, benchmark in zip(
            candidate_event_net_r, benchmark_event_net_r, strict=True
        )
    ]
    mean_event = sum(event_edges) / len(event_edges) if event_edges else 0.0
    account_edge = float(candidate_account_path_net_r[-1]) - float(
        benchmark_account_path_net_r[-1]
    )
    positive = mean_event > 0.0 and account_edge > 0.0
    formal_eligible = comparability_contract.get("formalGateEligible") is True
    payload: dict[str, Any] = {
        "schemaVersion": "benchmark_incremental_net_r_v1",
        "candidateId": candidate_id,
        "benchmarkId": benchmark_id,
        "comparabilityContractHash": comparability_contract.get("contractHash"),
        "eventLevelIncrementalNetR": event_edges,
        "meanEventIncrementalNetR": mean_event,
        "candidateAccountPathFinalNetR": float(candidate_account_path_net_r[-1]),
        "benchmarkAccountPathFinalNetR": float(benchmark_account_path_net_r[-1]),
        "accountPathIncrementalNetR": account_edge,
        "positiveIncrementalEdge": positive,
        "formalGateEligible": formal_eligible,
        "formalAdvancePermitted": positive and formal_eligible,
    }
    payload["evidenceHash"] = stable_hash(payload, prefix="benchmark_incremental_net_r")
    return payload

