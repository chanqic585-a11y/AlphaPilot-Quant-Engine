from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from alphapilot.formal_validation.executable_capital_policy import (
    build_capital_policy_v2,
)
from alphapilot.formal_validation.portfolio_event_engine import (
    process_portfolio_timestamp_v2,
)


def _liquidity() -> list[dict[str, object]]:
    start = datetime(2025, 11, 1, tzinfo=timezone.utc)
    return [
        {
            "timestamp": (start + timedelta(days=offset)).isoformat(),
            "close": 100.0,
            "quoteVolume": 10_000_000.0,
        }
        for offset in range(30)
    ]


def test_exits_funding_and_marks_precede_capacity_sizing_and_entry() -> None:
    policy = build_capital_policy_v2()
    policy["maximum_concurrent_positions"] = 1
    result = process_portfolio_timestamp_v2(
        timestamp="2026-01-01T04:00:00Z",
        current_equity=10_000.0,
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
        exits=[{"instrumentId": "BTC", "netPnl": 100.0}],
        funding=[{"amount": -10.0}],
        marks=[{"equityDelta": 10.0}],
        entry_signals=[
            {
                "signalId": "ETH",
                "instrumentId": "ETH",
                "entryTimestamp": "2026-01-01T04:00:00Z",
                "direction": "long",
                "entryPrice": 100.0,
                "stopPrice": 95.0,
                "dailyLiquidity": _liquidity(),
                "instrumentMeta": {
                    "quantityStep": 0.1,
                    "minimumQuantity": 0.1,
                },
                "eventExtremeResidualZ": -3.0,
                "recoverySizeZ": 1.0,
                "liquidity30d": 10_000_000.0,
                "correlationCluster": "eth",
                "beta": 1.0,
            }
        ],
        policy=policy,
    )

    assert result["currentEquity"] == pytest.approx(10_100.0)
    assert [row["instrumentId"] for row in result["acceptedEntries"]] == ["ETH"]
    assert result["acceptedEntries"][0]["riskAmount"] == pytest.approx(101.0)
    assert result["eventOrder"] == ["exit", "funding", "mark_and_equity", "entry"]


def test_missing_capacity_inputs_are_rejected_without_fallback() -> None:
    result = process_portfolio_timestamp_v2(
        timestamp="2026-01-01T04:00:00Z",
        current_equity=10_000.0,
        open_positions=[],
        exits=[],
        funding=[],
        marks=[],
        entry_signals=[
            {
                "signalId": "BAD",
                "instrumentId": "BAD",
                "entryTimestamp": "2026-01-01T04:00:00Z",
                "direction": "long",
                "eventExtremeResidualZ": -3.0,
                "recoverySizeZ": 1.0,
                "liquidity30d": 1.0,
                "correlationCluster": "bad",
                "beta": 1.0,
            }
        ],
        policy=build_capital_policy_v2(),
    )

    assert result["acceptedEntries"] == []
    assert result["rejectedEntries"][0]["reason"] == "missing_capacity_input"


def test_verified_quote_turnover_does_not_require_exchange_lot_metadata() -> None:
    result = process_portfolio_timestamp_v2(
        timestamp="2026-01-01T04:00:00Z",
        current_equity=10_000.0,
        open_positions=[],
        exits=[],
        funding=[],
        marks=[],
        entry_signals=[
            {
                "signalId": "ETH",
                "instrumentId": "ETH",
                "entryTimestamp": "2026-01-01T04:00:00Z",
                "direction": "long",
                "entryPrice": 100.0,
                "stopPrice": 95.0,
                "dailyLiquidity": _liquidity(),
                "eventExtremeResidualZ": -3.0,
                "recoverySizeZ": 1.0,
                "liquidity30d": 10_000_000.0,
                "correlationCluster": "eth",
                "beta": 1.0,
            }
        ],
        policy=build_capital_policy_v2(),
    )

    assert [row["instrumentId"] for row in result["acceptedEntries"]] == ["ETH"]
    assert result["acceptedEntries"][0]["positionSizingMode"] == (
        "continuous_research_notional"
    )


def test_partial_exit_preserves_and_rescales_the_remaining_position() -> None:
    policy = build_capital_policy_v2()
    policy["maximum_concurrent_positions"] = 1
    result = process_portfolio_timestamp_v2(
        timestamp="2026-01-01T04:00:00Z",
        current_equity=10_000.0,
        open_positions=[
            {
                "instrumentId": "BTC",
                "direction": "long",
                "remainingFraction": 1.0,
                "riskAmount": 100.0,
                "markNotional": 1_000.0,
                "quantity": 10.0,
                "correlationCluster": "btc",
                "beta": 1.0,
            }
        ],
        exits=[
            {
                "instrumentId": "BTC",
                "legFraction": 0.4,
                "netPnl": 40.0,
            }
        ],
        funding=[],
        marks=[],
        entry_signals=[],
        policy=policy,
    )

    assert result["currentEquity"] == pytest.approx(10_040.0)
    assert len(result["openPositions"]) == 1
    remaining = result["openPositions"][0]
    assert remaining["remainingFraction"] == pytest.approx(0.6)
    assert remaining["riskAmount"] == pytest.approx(60.0)
    assert remaining["markNotional"] == pytest.approx(600.0)
    assert remaining["quantity"] == pytest.approx(6.0)
    assert result["closedPositions"][0]["positionClosed"] is False
    assert result["closedPositions"][0]["remainingFractionAfter"] == pytest.approx(0.6)


def test_exit_replaces_previously_marked_unrealized_pnl_without_double_counting() -> None:
    policy = build_capital_policy_v2()
    marked = process_portfolio_timestamp_v2(
        timestamp="2026-01-01T04:00:00Z",
        current_equity=10_000.0,
        open_positions=[
            {
                "instrumentId": "BTC",
                "direction": "long",
                "riskAmount": 100.0,
                "markNotional": 1_000.0,
                "quantity": 10.0,
                "unrealizedPnl": 0.0,
                "correlationCluster": "btc",
                "beta": 1.0,
            }
        ],
        exits=[],
        funding=[],
        marks=[
            {
                "instrumentId": "BTC",
                "markNotional": 1_050.0,
                "unrealizedPnl": 50.0,
            }
        ],
        entry_signals=[],
        policy=policy,
    )
    closed = process_portfolio_timestamp_v2(
        timestamp="2026-01-01T08:00:00Z",
        current_equity=marked["currentEquity"],
        open_positions=marked["openPositions"],
        exits=[{"instrumentId": "BTC", "netPnl": 40.0}],
        funding=[],
        marks=[],
        entry_signals=[],
        policy=policy,
    )

    assert marked["currentEquity"] == pytest.approx(10_050.0)
    assert closed["currentEquity"] == pytest.approx(10_040.0)
    assert closed["openPositions"] == []
