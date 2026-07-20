from __future__ import annotations

import pandas as pd
import pytest

from alphapilot.v37i_acquisition.prefilter import development_slice, summarize_trial


def test_development_slice_reserves_locked_oos_without_reading_it() -> None:
    frame = pd.DataFrame({"value": range(100)})

    development, audit = development_slice(frame, development_fraction=0.8)

    assert len(development) == 80
    assert audit == {
        "totalRowCount": 100,
        "developmentRowCount": 80,
        "reservedLockedOosRowCount": 20,
        "lockedOosReadCount": 0,
    }
    assert development.iloc[-1]["value"] == 79


def test_trial_summary_includes_cost_and_drawdown() -> None:
    summary = summarize_trial(
        trade_returns=[0.05, -0.02, 0.04],
        bar_returns=[0.05, -0.02, 0.04],
        transaction_cost=0.006,
    )

    assert summary["tradeCount"] == 3
    assert summary["netReturn"] == pytest.approx(0.07)
    assert summary["profitFactor"] == pytest.approx(4.5)
    assert summary["maximumDrawdown"] == pytest.approx(0.02)
    assert summary["transactionCost"] == 0.006
