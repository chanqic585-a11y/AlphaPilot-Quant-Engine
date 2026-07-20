from __future__ import annotations

import pandas as pd

from alphapilot.data_foundation.funding_carry_data import FundingCarryDataPolicy
from alphapilot.data_foundation.funding_carry_readiness import (
    DualLegCostStressPolicy,
    evaluate_funding_carry_readiness,
)


def _panel(rows: int = 4, *, turnover: bool = True) -> pd.DataFrame:
    values = list(range(rows))
    return pd.DataFrame(
        {
            "asset": ["BTC"] * rows,
            "decisionTimestampMs": [value * 28_800_000 for value in values],
            "decisionAvailableAtMs": [value * 28_800_000 for value in values],
            "fundingRate": [0.0001] * rows,
            "basisPct": [0.1] * rows,
            "spotQuoteTurnover": [1_000_000.0 if turnover else None] * rows,
            "perpetualQuoteTurnover": [2_000_000.0 if turnover else None] * rows,
            "dualLegQuoteTurnoverProxy": [1_000_000.0 if turnover else None] * rows,
            "stale": [False] * rows,
        }
    )


def test_readiness_separates_historical_research_from_forward_execution() -> None:
    policy = FundingCarryDataPolicy.default(
        assets=("BTC",),
        minimum_aligned_rows=3,
        minimum_coverage_days=0,
    )
    cost_policy = DualLegCostStressPolicy.default()

    result = evaluate_funding_carry_readiness(
        policy=policy,
        cost_policy=cost_policy,
        panels={"BTC": _panel()},
        forward_order_book_evidence={"BTC": False},
    )

    assert result["historicalResearchReady"] is True
    assert result["formalResearchDataReady"] is True
    assert result["forwardExecutionEvidenceReady"] is False
    assert result["formalBlockers"] == []
    assert result["forwardBlockers"] == ["missing_forward_order_book:BTC"]
    assert result["costEvidence"]["classification"] == "preregistered_stress_assumption"
    assert result["costEvidence"]["notAccountFeeClaim"] is True
    assert result["sideEffects"] == {
        "candidateCount": 0,
        "formalRunCount": 0,
        "resultReadCount": 0,
        "releaseCount": 0,
        "demoArmCount": 0,
        "orderCount": 0,
    }


def test_missing_turnover_blocks_historical_and_formal_readiness() -> None:
    policy = FundingCarryDataPolicy.default(
        assets=("BTC",),
        minimum_aligned_rows=3,
        minimum_coverage_days=0,
    )

    result = evaluate_funding_carry_readiness(
        policy=policy,
        cost_policy=DualLegCostStressPolicy.default(),
        panels={"BTC": _panel(turnover=False)},
        forward_order_book_evidence={"BTC": True},
    )

    assert result["historicalResearchReady"] is False
    assert result["formalResearchDataReady"] is False
    assert "missing_dual_leg_quote_turnover:BTC" in result["historicalBlockers"]


def test_observed_zero_turnover_is_capacity_evidence_not_missing_data() -> None:
    policy = FundingCarryDataPolicy.default(
        assets=("BTC",),
        minimum_aligned_rows=3,
        minimum_coverage_days=0,
    )
    panel = _panel()
    panel.loc[0, "spotQuoteTurnover"] = 0.0
    panel.loc[0, "dualLegQuoteTurnoverProxy"] = 0.0

    result = evaluate_funding_carry_readiness(
        policy=policy,
        cost_policy=DualLegCostStressPolicy.default(),
        panels={"BTC": panel},
        forward_order_book_evidence={"BTC": False},
    )

    assert result["historicalResearchReady"] is True
    assert result["formalResearchDataReady"] is True
    assert result["perAsset"][0]["dualLegQuoteTurnoverAvailable"] is True
    assert result["perAsset"][0]["zeroTurnoverRowCount"] == 1
