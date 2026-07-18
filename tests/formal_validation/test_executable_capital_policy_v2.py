from __future__ import annotations
from alphapilot.formal_validation.executable_capital_policy import (
    accept_signal_batch_v2,
    build_capital_policy_v2,
)


def _candidate(
    instrument: str,
    *,
    direction: str = "long",
    risk_amount: float = 100.0,
    notional: float = 1_000.0,
    beta: float = 1.0,
    cluster: str = "cluster_a",
    residual: float = -3.0,
) -> dict[str, object]:
    return {
        "signalId": instrument,
        "instrumentId": instrument,
        "symbol": instrument,
        "entryTimestamp": "2026-01-01T04:00:00Z",
        "direction": direction,
        "eventExtremeResidualZ": residual,
        "recoverySizeZ": 1.0,
        "liquidity30d": 10_000_000.0,
        "capacityPassed": True,
        "actualNotional": notional,
        "quantity": notional / 100.0,
        "riskAmount": risk_amount,
        "correlationCluster": cluster,
        "beta": beta,
    }


def test_acceptance_sequence_updates_portfolio_after_each_signal() -> None:
    policy = build_capital_policy_v2()
    result = accept_signal_batch_v2(
        [
            _candidate("BTC", cluster="cluster_a", residual=-4.0),
            _candidate("ETH", cluster="cluster_a", residual=-3.0),
            _candidate("SOL", cluster="cluster_a", residual=-2.0),
        ],
        open_positions=[],
        current_equity=10_000.0,
        policy=policy,
    )

    assert [row["instrumentId"] for row in result["accepted"]] == ["BTC", "ETH"]
    assert result["rejected"][0]["reason"] == "correlation_cluster_risk_limit"
    assert result["audit"]["acceptanceSequence"] == [
        "ranking_validation",
        "duplicate_symbol",
        "capacity_and_sizing",
        "single_symbol_risk",
        "same_direction_risk",
        "total_open_risk",
        "correlation_cluster_risk",
        "projected_portfolio_beta",
        "maximum_positions",
    ]


def test_signed_beta_allows_a_short_to_reduce_existing_long_beta() -> None:
    policy = build_capital_policy_v2()
    result = accept_signal_batch_v2(
        [_candidate("ETH", direction="short", beta=1.0, notional=5_000.0)],
        open_positions=[
            {
                "instrumentId": "BTC",
                "direction": "long",
                "riskAmount": 100.0,
                "markNotional": 10_000.0,
                "correlationCluster": "btc",
                "beta": 1.5,
            }
        ],
        current_equity=10_000.0,
        policy=policy,
    )

    assert len(result["accepted"]) == 1
    assert result["stateAfter"]["portfolioBeta"] == 1.0


def test_duplicate_symbol_is_rejected_before_capacity() -> None:
    candidate = _candidate("BTC")
    candidate["capacityPassed"] = False
    result = accept_signal_batch_v2(
        [candidate],
        open_positions=[
            {
                "instrumentId": "BTC",
                "direction": "long",
                "riskAmount": 100.0,
                "markNotional": 1_000.0,
                "correlationCluster": "btc",
                "beta": 1.0,
            }
        ],
        current_equity=10_000.0,
        policy=build_capital_policy_v2(),
    )

    assert result["rejected"][0]["reason"] == "duplicate_symbol_while_open"
