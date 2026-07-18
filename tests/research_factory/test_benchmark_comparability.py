from __future__ import annotations

import pytest

from alphapilot.research_factory.benchmark_comparability import (
    build_benchmark_comparability_contract,
    evaluate_incremental_net_r,
)


def _contract(*, exit_hash: str = "exit-a", capital_hash: str = "capital-a") -> dict[str, str]:
    return {
        "signalUniverseId": "universe-1",
        "eligibilityWindowHash": "window-1",
        "directionPolicy": "long_short",
        "entryPolicyHash": "entry-1",
        "exitPolicyHash": exit_hash,
        "costPolicyHash": "cost-1",
        "positionCompetitionPolicyHash": "competition-1",
        "capitalPolicyHash": capital_hash,
        "concurrencyPolicyHash": "concurrency-1",
        "capacityPolicyHash": "capacity-1",
    }


def test_exit_only_benchmark_is_formal_comparable() -> None:
    contract = build_benchmark_comparability_contract(
        candidate_id="candidate-1",
        benchmark_id="fixed-exit-benchmark",
        candidate_contract=_contract(exit_hash="adaptive-exit"),
        benchmark_contract=_contract(exit_hash="fixed-exit"),
        difference_scope="exit_only",
    )

    assert contract["schemaVersion"] == "benchmark_comparability_contract_v1"
    assert contract["status"] == "formal_comparable"
    assert contract["formalGateEligible"] is True
    assert contract["allowedDifferences"] == ["exitPolicyHash"]
    assert contract["blockingMismatches"] == []


def test_capital_mismatch_is_diagnostic_only() -> None:
    contract = build_benchmark_comparability_contract(
        candidate_id="candidate-2",
        benchmark_id="unlimited-capital-benchmark",
        candidate_contract=_contract(capital_hash="limited"),
        benchmark_contract=_contract(capital_hash="unlimited"),
        difference_scope="full_mechanism",
    )

    assert contract["status"] == "diagnostic_only"
    assert contract["formalGateEligible"] is False
    assert "capitalPolicyHash" in contract["blockingMismatches"]


def test_incremental_net_r_reports_event_and_account_path_edges() -> None:
    comparability = build_benchmark_comparability_contract(
        candidate_id="candidate-3",
        benchmark_id="exit-benchmark",
        candidate_contract=_contract(exit_hash="adaptive"),
        benchmark_contract=_contract(exit_hash="fixed"),
        difference_scope="exit_only",
    )

    result = evaluate_incremental_net_r(
        candidate_id="candidate-3",
        benchmark_id="exit-benchmark",
        candidate_event_net_r=[0.4, -0.2, 0.8],
        benchmark_event_net_r=[0.2, -0.3, 0.5],
        candidate_account_path_net_r=[0.0, 0.4, 0.2, 1.0],
        benchmark_account_path_net_r=[0.0, 0.2, -0.1, 0.4],
        comparability_contract=comparability,
    )

    assert result["eventLevelIncrementalNetR"] == pytest.approx([0.2, 0.1, 0.3])
    assert result["meanEventIncrementalNetR"] == pytest.approx(0.2)
    assert result["accountPathIncrementalNetR"] == pytest.approx(0.6)
    assert result["formalGateEligible"] is True
    assert result["positiveIncrementalEdge"] is True


def test_diagnostic_benchmark_cannot_advance_formal() -> None:
    comparability = build_benchmark_comparability_contract(
        candidate_id="candidate-4",
        benchmark_id="bad-capital",
        candidate_contract=_contract(capital_hash="limited"),
        benchmark_contract=_contract(capital_hash="unlimited"),
        difference_scope="full_mechanism",
    )
    result = evaluate_incremental_net_r(
        candidate_id="candidate-4",
        benchmark_id="bad-capital",
        candidate_event_net_r=[1.0],
        benchmark_event_net_r=[0.0],
        candidate_account_path_net_r=[0.0, 1.0],
        benchmark_account_path_net_r=[0.0, 0.0],
        comparability_contract=comparability,
    )

    assert result["positiveIncrementalEdge"] is True
    assert result["formalGateEligible"] is False
    assert result["formalAdvancePermitted"] is False


def test_incremental_metric_rejects_unaligned_event_vectors() -> None:
    comparability = build_benchmark_comparability_contract(
        candidate_id="candidate-5",
        benchmark_id="benchmark-5",
        candidate_contract=_contract(),
        benchmark_contract=_contract(),
        difference_scope="full_mechanism",
    )
    with pytest.raises(ValueError, match="event_vector_length_mismatch"):
        evaluate_incremental_net_r(
            candidate_id="candidate-5",
            benchmark_id="benchmark-5",
            candidate_event_net_r=[1.0, 2.0],
            benchmark_event_net_r=[1.0],
            candidate_account_path_net_r=[0.0, 1.0],
            benchmark_account_path_net_r=[0.0, 0.5],
            comparability_contract=comparability,
        )

