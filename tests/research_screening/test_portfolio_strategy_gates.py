from __future__ import annotations

import pytest

from alphapilot.research_screening.portfolio_strategy_gates import evaluate_portfolio_strategy_gates


def _portfolio_metrics(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "metricType": "portfolio",
        "netReturn": 0.12,
        "relativeBenchmarkExcessReturn": 0.04,
        "maximumDrawdownPct": 12.0,
        "positiveFoldCount": 4,
        "foldCount": 5,
        "positiveRebalanceRatio": 0.65,
        "betaPassed": True,
        "turnoverPassed": True,
        "capacityPassed": True,
        "singleSymbolContributionPassed": True,
        "singleMonthContributionPassed": True,
    }
    payload.update(overrides)
    return payload


def test_portfolio_formal_gate_never_requires_per_trade_r_or_profit_factor() -> None:
    result = evaluate_portfolio_strategy_gates(
        development_metrics=_portfolio_metrics(),
        walk_forward_metrics=_portfolio_metrics(),
        holdout_metrics=_portfolio_metrics(),
        stress_1_5x_metrics=_portfolio_metrics(netReturn=0.02),
        uncertainty={"benchmarkExcessReturnLower90": 0.01},
        simple_benchmark_passed=True,
        capital_competition_passed=True,
        implementation_parity_passed=True,
        formal_data_provenance_passed=True,
    )

    assert result["overallFormalPassed"] is True
    assert "profitFactor" not in result["walkForwardMetrics"]
    assert "averageNetR" not in result["walkForwardMetrics"]


def test_portfolio_gate_rejects_event_metric_contract() -> None:
    with pytest.raises(TypeError, match="portfolio metrics"):
        evaluate_portfolio_strategy_gates(
            development_metrics={"metricType": "event"},
            walk_forward_metrics=_portfolio_metrics(),
            holdout_metrics=_portfolio_metrics(),
            stress_1_5x_metrics=_portfolio_metrics(),
            uncertainty={"benchmarkExcessReturnLower90": 0.01},
            simple_benchmark_passed=True,
            capital_competition_passed=True,
            implementation_parity_passed=True,
            formal_data_provenance_passed=True,
        )
