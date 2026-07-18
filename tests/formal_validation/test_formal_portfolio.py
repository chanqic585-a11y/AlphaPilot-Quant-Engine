from __future__ import annotations

import pytest

from alphapilot.formal_validation.formal_portfolio import (
    replay_shared_capital,
    summarize_portfolio,
)


def _event(
    symbol: str,
    entry_hour: int,
    exit_hour: int,
    net_r: float,
    *,
    direction: str = "long",
    cluster: str = "large_cap",
    beta: float = 0.2,
    score: float = 1.0,
) -> dict[str, object]:
    return {
        "signalId": f"{symbol}-{entry_hour}",
        "candidateId": "s01",
        "symbol": symbol,
        "direction": direction,
        "side": direction,
        "entryTimestamp": f"2026-01-01T{entry_hour:02d}:00:00+00:00",
        "exitTimestamp": f"2026-01-01T{exit_hour:02d}:00:00+00:00",
        "realizedGrossR": net_r + 0.2,
        "realizedNetR": net_r,
        "costR": 0.2,
        "capacityPassed": True,
        "correlationCluster": cluster,
        "portfolioBeta": beta,
        "residualZ": -score,
        "recoveryConfirmation": score,
        "liquidityScore": 1_000_000.0,
        "foldId": "wf_1",
        "split": "test",
    }


def _policy(**overrides: object) -> dict[str, object]:
    policy: dict[str, object] = {
        "initial_capital": 10_000.0,
        "risk_per_trade": 0.01,
        "maximum_concurrent_positions": 6,
        "maximum_open_risk": 0.06,
        "maximum_same_direction_risk": 0.04,
        "maximum_correlation_cluster_risk": 0.02,
        "maximum_single_symbol_risk": 0.01,
        "maximum_portfolio_beta": 1.5,
        "duplicateSymbolPolicy": "reject_while_open",
        "capacityRequirement": "capacityPassed_true",
    }
    policy.update(overrides)
    return policy


def test_shared_capital_releases_risk_and_compounds_after_exit() -> None:
    events = [
        _event("BTC-USDT-SWAP", 1, 3, 1.0),
        _event("ETH-USDT-SWAP", 1, 4, -0.5),
        _event("SOL-USDT-SWAP", 2, 5, 2.0),
        _event("SOL-USDT-SWAP", 5, 6, 1.0),
    ]

    result = replay_shared_capital(events, _policy())

    assert [row["symbol"] for row in result["accepted"]] == [
        "BTC-USDT-SWAP",
        "ETH-USDT-SWAP",
        "SOL-USDT-SWAP",
    ]
    assert result["rejected"][0]["reason"] == "correlation_cluster_risk_limit"
    assert result["accepted"][-1]["riskAmount"] == pytest.approx(100.5)
    assert result["finalEquity"] == pytest.approx(10_150.5)


def test_shared_capital_rejects_duplicate_symbol_and_same_direction_limit() -> None:
    events = [
        _event("BTC-USDT-SWAP", 1, 5, 1.0, cluster="btc"),
        _event("BTC-USDT-SWAP", 2, 4, 1.0, cluster="btc"),
        _event("ETH-USDT-SWAP", 2, 5, 1.0, cluster="eth"),
        _event("SOL-USDT-SWAP", 2, 5, 1.0, cluster="sol"),
    ]
    policy = _policy(maximum_same_direction_risk=0.02)

    result = replay_shared_capital(events, policy)

    reasons = [row["reason"] for row in result["rejected"]]
    assert "duplicate_symbol_while_open" in reasons
    assert "same_direction_risk_limit" in reasons
    assert result["audit"]["lookaheadReadCount"] == 0


def test_portfolio_summary_reports_profit_factor_drawdown_and_concentration() -> None:
    result = replay_shared_capital(
        [
            _event("BTC-USDT-SWAP", 1, 2, 1.0),
            _event("ETH-USDT-SWAP", 2, 3, -0.5),
            _event("SOL-USDT-SWAP", 3, 4, 2.0),
        ],
        _policy(),
    )

    metrics = summarize_portfolio(result)

    assert metrics["tradeCount"] == 3
    assert metrics["profitFactor"] == pytest.approx(5.96, abs=0.01)
    assert metrics["averageNetR"] == pytest.approx((1.0 - 0.5 + 2.0) / 3)
    assert metrics["maximumDrawdownPercent"] > 0
    assert metrics["maximumSingleSymbolPositiveContribution"] < 0.68
    assert metrics["metricType"] == "event_shared_capital"
