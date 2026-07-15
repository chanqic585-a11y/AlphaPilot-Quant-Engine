import numpy as np
import pandas as pd

from alphapilot.research_screening.factor_evaluation import evaluate_factor_trial


def test_factor_evaluation_reports_costs_folds_and_concentration() -> None:
    rng = np.random.default_rng(7)
    dates = pd.date_range("2020-01-01", periods=240, freq="D", tz="UTC")
    columns = ["A", "B", "C", "D", "E", "F"]
    factor = pd.DataFrame(rng.normal(size=(240, 6)), index=dates, columns=columns)
    forward = factor * 0.02 + pd.DataFrame(
        rng.normal(scale=0.005, size=(240, 6)), index=dates, columns=columns
    )

    result = evaluate_factor_trial(
        trial_id="positive",
        factor=factor,
        forward_returns=forward,
        direction=1,
        base_cost_bps=5.0,
        folds=5,
        embargo_rows=2,
    )

    assert result["coverage"] > 0.99
    assert len(result["folds"]) == 5
    assert result["baseCostSpread"] > result["stress1_5xSpread"]
    assert 0 <= result["singleInstrumentPositiveContribution"] <= 1
    assert 0 <= result["singleMonthPositiveContribution"] <= 1
