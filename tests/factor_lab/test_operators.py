from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from alphapilot.factor_lab import operators


def test_safe_div_returns_nan_for_zero_denominator_and_never_inf() -> None:
    numerator = pd.Series([1.0, 2.0, np.inf])
    denominator = pd.Series([1.0, 0.0, 2.0])

    result = operators.safe_div(numerator, denominator)

    assert result.iloc[0] == 1.0
    assert np.isnan(result.iloc[1])
    assert np.isnan(result.iloc[2])
    assert not np.isinf(result.to_numpy()).any()


def test_delay_and_delta_cannot_access_future_rows() -> None:
    values = pd.Series([10.0, 11.0, 15.0])

    assert operators.delay(values, 1).tolist()[1:] == [10.0, 11.0]
    assert operators.delta(values, 1).tolist()[1:] == [1.0, 4.0]
    with pytest.raises(ValueError, match="non-negative"):
        operators.delay(values, -1)


def test_rolling_operator_requires_explicit_valid_min_periods() -> None:
    values = pd.Series([1.0, 2.0, 3.0])

    with pytest.raises(TypeError):
        operators.ts_mean(values, 2)  # type: ignore[call-arg]
    with pytest.raises(ValueError, match="min_periods"):
        operators.ts_mean(values, 2, 3)
    assert operators.ts_mean(values, 2, 2).tolist()[1:] == [1.5, 2.5]


def test_cross_sectional_rank_applies_point_in_time_mask() -> None:
    values = pd.DataFrame([[1.0, 3.0, 2.0]], columns=["A", "B", "C"])
    mask = pd.DataFrame([[True, False, True]], columns=values.columns)

    result = operators.rank(values, pit_mask=mask)

    assert result.loc[0, "A"] == 0.5
    assert np.isnan(result.loc[0, "B"])
    assert result.loc[0, "C"] == 1.0
