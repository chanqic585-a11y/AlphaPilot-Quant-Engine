from __future__ import annotations

import pandas as pd
import pytest

from alphapilot.formal_validation.formal_stress import (
    build_cost_stress,
    build_funding_stress,
    build_s01_benchmark,
    build_utc_daily_returns,
)


def _event(
    symbol: str,
    entry: str,
    exit_: str,
    gross_r: float,
    *,
    signal_id: str,
    fold_id: str = "fold_001",
) -> dict[str, object]:
    return {
        "signalId": signal_id,
        "candidateId": "s01",
        "variantId": "S01",
        "symbol": symbol,
        "side": "long",
        "direction": "long",
        "entryTimestamp": entry,
        "exitTimestamp": exit_,
        "entryIndex": 1,
        "exitIndex": 3,
        "entryPrice": 100.0,
        "riskDistance": 10.0,
        "realizedGrossR": gross_r,
        "realizedNetR": gross_r - 0.2,
        "feesR": 0.1,
        "slippageR": 0.05,
        "spreadProxyR": 0.05,
        "costR": 0.2,
        "fundingR": None,
        "capacityPassed": True,
        "correlationCluster": symbol,
        "portfolioBeta": 0.1,
        "residualZ": -2.5,
        "recoveryConfirmation": 0.5,
        "liquidityScore": 1_000_000.0,
        "foldId": fold_id,
    }


def _policy() -> dict[str, object]:
    return {
        "initial_capital": 10_000.0,
        "risk_per_trade": 0.01,
        "maximum_concurrent_positions": 6,
        "maximum_open_risk": 0.06,
        "maximum_same_direction_risk": 0.04,
        "maximum_correlation_cluster_risk": 0.02,
        "maximum_single_symbol_risk": 0.01,
        "maximum_portfolio_beta": 1.5,
    }


def _cost_model() -> dict[str, object]:
    return {
        "baseRoundTripCostRate": 0.002,
        "scenarios": [
            {"scenarioId": "base", "multiplier": 1.0},
            {"scenarioId": "cost_1_5x", "multiplier": 1.5},
            {"scenarioId": "cost_2_0x", "multiplier": 2.0},
        ],
    }


def test_cost_stress_freezes_base_selected_event_identities() -> None:
    events = [
        _event(
            "BTC-USDT-SWAP",
            "2025-01-01T00:00:00+00:00",
            "2025-01-01T12:00:00+00:00",
            1.0,
            signal_id="btc-1",
        ),
        _event(
            "ETH-USDT-SWAP",
            "2025-01-01T04:00:00+00:00",
            "2025-01-01T16:00:00+00:00",
            0.4,
            signal_id="eth-1",
        ),
    ]

    result = build_cost_stress(events, _policy(), _cost_model())

    identities = [scenario["acceptedEventIds"] for scenario in result["scenarios"]]
    assert identities[0] == identities[1] == identities[2]
    assert result["scenarios"][0]["metrics"]["averageNetR"] == pytest.approx(0.5)
    assert result["scenarios"][2]["metrics"]["averageNetR"] == pytest.approx(0.3)
    assert all(row["fundingR"] is None for row in result["baseAcceptedEvents"])


def test_funding_stress_keeps_raw_missing_values_null() -> None:
    events = [
        _event(
            "BTC-USDT-SWAP",
            "2025-01-01T00:00:00+00:00",
            "2025-01-02T00:00:00+00:00",
            1.0,
            signal_id="btc-1",
        )
    ]

    unavailable = build_funding_stress(events, adverse_rate_per_settlement=None)
    stressed = build_funding_stress(events, adverse_rate_per_settlement=0.0005)

    assert unavailable["fundingEvidenceStatus"] == "partial_or_proxy"
    assert unavailable["gateEvaluable"] is False
    assert unavailable["events"][0]["fundingR"] is None
    assert stressed["events"][0]["fundingR"] is None
    assert stressed["events"][0]["conservativeFundingStressR"] == pytest.approx(0.015)
    assert stressed["events"][0]["conservativeFundingNetR"] == pytest.approx(0.785)


def test_s01_benchmark_and_daily_returns_use_exit_dates() -> None:
    frame = pd.DataFrame(
        {
            "date": pd.date_range("2025-01-01", periods=16, freq="4h", tz="UTC"),
            "open": [100.0 + value for value in range(16)],
            "high": [101.0 + value for value in range(16)],
            "low": [99.0 + value for value in range(16)],
            "close": [100.5 + value for value in range(16)],
            "volume": [1_000.0] * 16,
        }
    )
    event = _event(
        "BTC-USDT-SWAP",
        "2025-01-01T04:00:00+00:00",
        "2025-01-01T12:00:00+00:00",
        1.0,
        signal_id="btc-1",
    )

    benchmark = build_s01_benchmark([event], {"BTC-USDT-SWAP": frame})
    daily = build_utc_daily_returns(
        [{**event, "netPnl": 80.0, "equityAtEntry": 10_000.0}],
        start="2025-01-01T00:00:00+00:00",
        cutoff_exclusive="2025-01-03T00:00:00+00:00",
    )

    assert benchmark["events"][0]["benchmarkExitIndex"] == 13
    assert benchmark["events"][0]["benchmarkNetR"] == pytest.approx(1.1)
    assert list(daily["date"].dt.strftime("%Y-%m-%d")) == ["2025-01-01", "2025-01-02"]
    assert daily.iloc[0]["netReturn"] == pytest.approx(0.008)
    assert daily.iloc[1]["netReturn"] == 0.0
