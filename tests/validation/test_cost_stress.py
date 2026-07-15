from __future__ import annotations

from alphapilot.validation.cost_stress import evaluate_cost_scenarios


def test_cost_stress_reproduces_base_and_degrades_with_multiplier() -> None:
    trades = [
        {"grossR": 1.2, "netR": 1.0, "feeR": 0.1, "slippageR": 0.1, "fundingR": 0.0},
        {"grossR": -0.8, "netR": -1.0, "feeR": 0.1, "slippageR": 0.1, "fundingR": 0.0},
    ]

    report = evaluate_cost_scenarios(trades, multipliers=(1.0, 1.5, 2.0))

    assert report["scenarios"]["1.0"]["averageNetR"] == 0.0
    assert report["scenarios"]["1.5"]["averageNetR"] == -0.1
    assert report["scenarios"]["2.0"]["averageNetR"] == -0.2
    assert report["fundingStatus"] == "recorded_zero_or_unavailable"
    assert report["breakEvenCostMultiplier"] == 1.0
