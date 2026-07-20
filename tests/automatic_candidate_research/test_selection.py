from __future__ import annotations

import pytest

from alphapilot.automatic_candidate_research.contracts import V36ContractError
from alphapilot.automatic_candidate_research.selection import (
    project_development_evidence,
    select_stable_neighborhood,
)


@pytest.mark.parametrize(
    ("strategy_type", "metrics", "expected_score"),
    [
        (
            "directional",
            {
                "eventCount": 40,
                "profitFactor": 1.25,
                "averageNetR": 0.08,
                "totalNetR": 3.2,
                "mfe": 0.9,
                "mae": -0.45,
                "totalCostR": 0.4,
                "benchmarkIncrementNetR": 1.1,
                "maxDrawdownR": 1.2,
                "concentration": 0.24,
            },
            0.08,
        ),
        (
            "pair",
            {
                "spreadReturn": 0.14,
                "dualLegCostR": 0.03,
                "residualStability": 0.8,
                "halfLife": 18.0,
                "structuralBreakDetected": False,
                "grossExposure": 1.0,
                "netExposure": 0.02,
                "dualLegCapacity": 50000.0,
                "pairBenchmarkIncrement": 0.07,
                "maxDrawdownR": 0.8,
            },
            0.11,
        ),
        (
            "portfolio",
            {
                "portfolioNetReturn": 0.12,
                "maxDrawdownR": 1.1,
                "turnover": 0.6,
                "totalCostR": 0.03,
                "beta": 0.15,
                "grossExposure": 1.0,
                "netExposure": 0.9,
                "capacity": 250000.0,
                "positivePeriodRatio": 0.62,
                "benchmarkIncrement": 0.04,
            },
            0.12,
        ),
        (
            "event",
            {
                "abnormalReturn": 0.09,
                "matchedBenchmarkReturn": 0.02,
                "eventClusterCount": 8,
                "causalTimingValid": True,
                "eventCount": 35,
                "maxDrawdownR": 0.9,
            },
            0.07,
        ),
    ],
)
def test_type_specific_development_projection(
    strategy_type: str,
    metrics: dict[str, object],
    expected_score: float,
) -> None:
    projection = project_development_evidence(
        {
            "candidateId": "candidate-a",
            "trialId": "trial-a",
            "strategyType": strategy_type,
            "split": "development",
            "metrics": metrics,
        }
    )

    assert projection["selectionNetR"] == pytest.approx(expected_score)
    assert projection["split"] == "development"
    assert projection["lockedOosReadCount"] == 0


def test_projection_rejects_locked_oos_and_missing_type_metric() -> None:
    with pytest.raises(V36ContractError, match="development_only_selection"):
        project_development_evidence(
            {
                "candidateId": "candidate-a",
                "trialId": "trial-a",
                "strategyType": "directional",
                "split": "locked_oos",
                "metrics": {},
            }
        )

    with pytest.raises(V36ContractError, match="missing_metric:eventCount"):
        project_development_evidence(
            {
                "candidateId": "candidate-a",
                "trialId": "trial-a",
                "strategyType": "directional",
                "split": "development",
                "metrics": {"profitFactor": 1.2},
            }
        )


def test_stable_neighborhood_selects_center_platform() -> None:
    result = select_stable_neighborhood(
        candidate_id="candidate-a",
        projections=[
            _projection("trial-low", 0, 0.07, 1.20, 1.10),
            _projection("trial-center", 1, 0.09, 1.27, 1.20),
            _projection("trial-high", 2, 0.08, 1.24, 1.15),
        ],
    )

    assert result["eligible"] is True
    assert result["selectedTrialId"] == "trial-center"
    assert result["gate"]["sameDirectionMajority"] is True
    assert result["gate"]["isolatedSpike"] is False
    assert result["lockedOosReadCount"] == 0


def test_unstable_isolated_spike_does_not_select_trial() -> None:
    result = select_stable_neighborhood(
        candidate_id="candidate-a",
        projections=[
            _projection("trial-low", 0, -0.02, 0.94, 1.00),
            _projection("trial-center", 1, 0.45, 2.40, 1.10),
            _projection("trial-high", 2, -0.01, 0.97, 3.80),
        ],
    )

    assert result["eligible"] is False
    assert result["selectedTrialId"] is None
    assert result["reason"] == "unstable_parameter_neighborhood"


def _projection(
    trial_id: str,
    trial_index: int,
    net_r: float,
    profit_factor: float,
    drawdown_r: float,
) -> dict[str, object]:
    return {
        "candidateId": "candidate-a",
        "trialId": trial_id,
        "trialIndex": trial_index,
        "strategyType": "directional",
        "split": "development",
        "selectionNetR": net_r,
        "profitFactor": profit_factor,
        "maxDrawdownR": drawdown_r,
        "lockedOosReadCount": 0,
    }
