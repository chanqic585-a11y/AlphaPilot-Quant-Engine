from __future__ import annotations

from alphapilot.research_screening.capital_competition import (
    CapitalCompetitionPolicy,
    allocate_competing_signals,
)
from alphapilot.research_screening.capacity_model import evaluate_capacity


def _signal(candidate: str, symbol: str, strength: float) -> dict[str, object]:
    return {
        "candidateId": candidate,
        "symbol": symbol,
        "direction": "long",
        "correlationCluster": "stress_reversal",
        "riskAmount": 100.0,
        "portfolioBeta": 0.2,
        "dataFreshness": 1.0,
        "liquidityScore": 1.0,
        "mechanismStrength": strength,
        "capacityPassed": True,
    }


def test_competing_signals_are_ranked_deterministically_and_share_cluster_risk() -> None:
    policy = CapitalCompetitionPolicy(
        initial_capital=10_000,
        risk_per_trade=0.01,
        maximum_concurrent_positions=3,
        maximum_open_risk=0.03,
        maximum_same_direction_risk=0.03,
        maximum_correlation_cluster_risk=0.02,
        maximum_single_symbol_risk=0.01,
        maximum_portfolio_beta=1.0,
    )
    result = allocate_competing_signals(
        [_signal("B1", "ETH", 0.8), _signal("A1", "BTC", 0.9), _signal("A2", "SOL", 0.7)],
        policy,
    )

    assert [row["candidateId"] for row in result["accepted"]] == ["A1", "B1"]
    assert result["rejected"][0]["reason"] == "correlation_cluster_risk_limit"
    assert result["capitalCompetitionPassed"] is True


def test_capacity_failure_is_rejected_before_allocation() -> None:
    signal = _signal("A1", "BTC", 0.9)
    signal["capacityPassed"] = False
    result = allocate_competing_signals([signal], CapitalCompetitionPolicy())

    assert result["accepted"] == []
    assert result["rejected"][0]["reason"] == "capacity_rejected"


def test_capacity_model_reports_notional_ratios_and_slippage() -> None:
    result = evaluate_capacity(
        order_notional=10_000,
        quote_volume_24h=10_000_000,
        bar_quote_volume=1_000_000,
        depth_proxy=500_000,
        maximum_24h_ratio=0.01,
        maximum_bar_ratio=0.02,
        maximum_depth_ratio=0.01,
    )

    assert result["orderNotionalTo24hQuoteVolume"] == 0.001
    assert result["orderNotionalToBarQuoteVolume"] == 0.01
    assert result["orderNotionalToDepthProxy"] == 0.02
    assert result["capacityPassed"] is False
    assert result["estimatedSlippageBps"] > 0
