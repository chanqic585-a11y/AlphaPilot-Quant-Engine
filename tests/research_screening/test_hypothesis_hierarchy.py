from __future__ import annotations

from alphapilot.research_screening.hypothesis_hierarchy import (
    apply_hierarchical_fdr,
    evaluate_stress_reversal_overlap,
    select_correlated_subfamily_winner,
)


def test_hierarchical_fdr_preserves_raw_family_subfamily_and_global_values() -> None:
    result = apply_hierarchical_fdr(
        families={"stress_reversal": 0.01, "cross_sectional_momentum": 0.04},
        subfamilies={
            "A": {"familyId": "stress_reversal", "pValue": 0.01},
            "B": {"familyId": "stress_reversal", "pValue": 0.03},
            "C": {"familyId": "cross_sectional_momentum", "pValue": 0.04},
        },
        alpha=0.05,
    )

    assert set(result["families"]) == {"stress_reversal", "cross_sectional_momentum"}
    assert result["subfamilies"]["A"]["rawPValue"] == 0.01
    assert "familyAdjustedPValue" in result["subfamilies"]["A"]
    assert "globalFdrAdjustedPValue" in result["subfamilies"]["A"]


def test_highly_overlapping_a_b_share_one_risk_cluster_and_one_winner() -> None:
    overlap = evaluate_stress_reversal_overlap(
        event_ids_a={"1", "2", "3"},
        event_ids_b={"2", "3", "4"},
        event_returns_a=[1.0, -0.5, 2.0],
        event_returns_b=[0.9, -0.45, 1.8],
    )
    winner = select_correlated_subfamily_winner(
        [
            {"candidateId": "A1", "adjustedPValue": 0.02, "benchmarkIncrement": 0.20},
            {"candidateId": "B1", "adjustedPValue": 0.03, "benchmarkIncrement": 0.30},
        ],
        overlap=overlap,
    )

    assert overlap["sharedRiskCluster"] is True
    assert overlap["maximumFormalEvidenceCount"] == 1
    assert winner["selectedCandidateId"] == "A1"
    assert winner["suppressedCandidateIds"] == ["B1"]

