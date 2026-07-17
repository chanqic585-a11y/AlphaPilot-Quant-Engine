from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from alphapilot.formal_validation.executable_capital_policy import (
    build_capital_policy_v2,
)
from alphapilot.formal_validation.v18_formal_execution import (
    attach_point_in_time_context,
    build_locked_cost_stress,
    build_daily_market_evidence,
    build_signal_feature_evidence,
    compare_capital_replays,
    replay_v18_capital_policy,
    summarize_capital_replay,
)


def _frame(symbol_offset: float = 0.0, *, periods: int = 80) -> pd.DataFrame:
    dates = pd.date_range("2025-01-01", periods=periods, freq="12h", tz="UTC")
    close = [100.0 + symbol_offset + index * 0.1 for index in range(periods)]
    return pd.DataFrame(
        {
            "date": dates,
            "open": close,
            "high": [value + 1.0 for value in close],
            "low": [value - 1.0 for value in close],
            "close": close,
            "volume": [1_000_000.0 + symbol_offset for _ in close],
        }
    )


def test_daily_market_evidence_uses_registered_okx_quote_turnover_semantics() -> None:
    daily, returns, audit = build_daily_market_evidence(
        {
            "BTC-USDT-SWAP": _frame(),
            "ETH-USDT-SWAP": _frame(10.0),
        }
    )

    first = daily["BTC-USDT-SWAP"][0]
    assert first["quoteVolume"] == pytest.approx(2_000_000.0)
    assert first["timestamp"] == "2025-01-01T00:00:00Z"
    assert len(returns["BTC-USDT-SWAP"]) == 39
    assert audit["status"] == "passed"
    assert audit["sourceField"] == "volume"
    assert audit["registeredMeaning"] == "okx_vol_ccy_quote"


def test_signal_feature_evidence_reconstructs_frozen_s01_ranking_fields() -> None:
    btc = _frame(periods=80)
    eth = _frame(10.0, periods=80)
    eth.loc[65:67, "close"] = [96.0, 97.0, 99.0]
    eth.loc[65:67, "open"] = eth.loc[65:67, "close"]
    signal_timestamp = pd.Timestamp(eth.iloc[67]["date"]).isoformat()
    entry_timestamp = pd.Timestamp(eth.iloc[68]["date"]).isoformat()
    candidate = {
        "featureDefinition": {"residualWindow": 10, "recoveryBars": 2},
    }
    events = [
        {
            "signalId": "signal-1",
            "symbol": "ETH-USDT-SWAP",
            "signalTimestamp": signal_timestamp,
            "entryTimestamp": entry_timestamp,
        }
    ]

    enriched, audit = build_signal_feature_evidence(
        events,
        {"BTC-USDT-SWAP": btc, "ETH-USDT-SWAP": eth},
        candidate,
    )

    assert audit["missingRankingFieldCount"] == 0
    assert enriched[0]["eventExtremeResidualZ"] < 0.0
    assert enriched[0]["recoverySizeZ"] > 0.0
    assert enriched[0]["liquidity30d"] > 0.0
    assert enriched[0]["lookaheadReadCount"] == 0


def _return_rows(scale: float = 1.0) -> list[dict[str, object]]:
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    return [
        {
            "timestamp": (start + timedelta(days=offset)).isoformat(),
            "return": scale * (0.001 + (offset % 7) * 0.0002),
        }
        for offset in range(80)
    ]


def test_point_in_time_context_ignores_returns_on_or_after_entry_day() -> None:
    entry = datetime(2025, 3, 12, 4, tzinfo=timezone.utc).isoformat()
    events = [
        {
            "signalId": "signal-1",
            "instrumentId": "ETH-USDT-SWAP",
            "entryTimestamp": entry,
        }
    ]
    panel = {
        "BTC-USDT-SWAP": _return_rows(),
        "ETH-USDT-SWAP": _return_rows(1.5),
    }
    mutated = {symbol: [dict(row) for row in rows] for symbol, rows in panel.items()}
    mutated["ETH-USDT-SWAP"][-10:] = [
        {**row, "return": 99.0} for row in mutated["ETH-USDT-SWAP"][-10:]
    ]

    original, original_audit = attach_point_in_time_context(events, panel)
    changed, changed_audit = attach_point_in_time_context(events, mutated)

    assert original == changed
    assert original[0]["beta"] == pytest.approx(1.5)
    assert original[0]["correlationCluster"] != "shared_unknown_cluster"
    assert original_audit["lookaheadReadCount"] == 0
    assert changed_audit["lookaheadReadCount"] == 0


def _liquidity() -> list[dict[str, object]]:
    start = datetime(2025, 10, 1, tzinfo=timezone.utc)
    return [
        {
            "timestamp": (start + timedelta(days=offset)).isoformat(),
            "quoteVolume": 20_000_000.0,
            "close": 100.0,
        }
        for offset in range(30)
    ]


def test_capital_replay_handles_partial_exits_without_double_counting_marks() -> None:
    dates = pd.date_range("2026-01-01", periods=3, freq="4h", tz="UTC")
    frame = pd.DataFrame(
        {
            "date": dates,
            "open": [100.0, 101.0, 102.0],
            "high": [101.0, 102.0, 103.0],
            "low": [99.0, 100.0, 101.0],
            "close": [100.0, 101.0, 102.0],
            "volume": [1_000_000.0] * 3,
        }
    )
    event = {
        "candidateId": "S01",
        "signalId": "signal-1",
        "symbol": "ETH-USDT-SWAP",
        "instrumentId": "ETH-USDT-SWAP",
        "direction": "long",
        "signalTimestamp": dates[0].isoformat(),
        "entryTimestamp": dates[0].isoformat(),
        "entryPrice": 100.0,
        "initialStop": 95.0,
        "eventExtremeResidualZ": -3.0,
        "recoverySizeZ": 1.0,
        "liquidity30d": 20_000_000.0,
        "dailyLiquidity": _liquidity(),
        "correlationCluster": "cluster-eth",
        "beta": 1.0,
        "foldId": "fold_001",
        "exitLegs": [
            {
                "legIndex": 0,
                "legFraction": 0.4,
                "executionTimestamp": dates[1].isoformat(),
                "netR": 0.2,
                "grossR": 0.22,
            },
            {
                "legIndex": 1,
                "legFraction": 0.6,
                "executionTimestamp": dates[2].isoformat(),
                "netR": 0.3,
                "grossR": 0.32,
            },
        ],
    }

    replay = replay_v18_capital_policy(
        [event],
        {"ETH-USDT-SWAP": frame},
        policy=build_capital_policy_v2(),
    )

    assert replay["acceptedSignalCount"] == 1
    assert replay["finalEquity"] == pytest.approx(10_050.0)
    assert replay["openPositions"] == []
    assert len(replay["closedLegs"]) == 2
    assert replay["trades"][0]["netPnl"] == pytest.approx(50.0)
    assert replay["maximumAbsoluteProjectedBeta"] > 0.0

    metrics = summarize_capital_replay(replay)
    assert metrics["tradeCount"] == 1
    assert metrics["averageNetR"] == pytest.approx(0.5)
    assert metrics["totalNetR"] == pytest.approx(0.5)

    stress = build_locked_cost_stress(
        replay,
        [event],
        {
            "scenarios": [
                {"scenarioId": "base", "multiplier": 1.0},
                {"scenarioId": "cost_1_5x", "multiplier": 1.5},
                {"scenarioId": "cost_2_0x", "multiplier": 2.0},
            ]
        },
    )
    scenarios = {row["scenarioId"]: row for row in stress["scenarios"]}
    assert stress["selectionIdentityStable"] is True
    assert scenarios["cost_2_0x"]["metrics"]["averageNetR"] < metrics["averageNetR"]


def test_capital_replay_ignores_exit_legs_for_rejected_entries() -> None:
    dates = pd.date_range("2026-01-01", periods=3, freq="4h", tz="UTC")
    frame = pd.DataFrame(
        {
            "date": dates,
            "open": [100.0, 101.0, 102.0],
            "high": [101.0, 102.0, 103.0],
            "low": [99.0, 100.0, 101.0],
            "close": [100.0, 101.0, 102.0],
            "volume": [1_000_000.0] * 3,
        }
    )
    event = {
        "candidateId": "S01",
        "signalId": "rejected-signal",
        "symbol": "ETH-USDT-SWAP",
        "instrumentId": "ETH-USDT-SWAP",
        "direction": "long",
        "signalTimestamp": dates[0].isoformat(),
        "entryTimestamp": dates[0].isoformat(),
        "entryPrice": 100.0,
        "initialStop": 95.0,
        # Missing frozen ranking fields deliberately rejects this entry.
        "liquidity30d": 20_000_000.0,
        "dailyLiquidity": _liquidity(),
        "correlationCluster": "cluster-eth",
        "beta": 1.0,
        "foldId": "fold_001",
        "exitLegs": [
            {
                "legIndex": 0,
                "legFraction": 1.0,
                "executionTimestamp": dates[2].isoformat(),
                "netR": 0.5,
                "grossR": 0.55,
            }
        ],
    }

    replay = replay_v18_capital_policy(
        [event],
        {"ETH-USDT-SWAP": frame},
        policy=build_capital_policy_v2(),
    )

    assert replay["acceptedSignalCount"] == 0
    assert replay["rejectedSignalCount"] == 1
    assert replay["closedLegs"] == []
    assert replay["ignoredExitLegs"] == [
        {
            "signalId": "rejected-signal",
            "executionTimestamp": "2026-01-01T08:00:00Z",
            "reason": "entry_not_accepted",
        }
    ]


def test_capital_parity_fails_on_changed_acceptance_reason() -> None:
    reference = {
        "decisions": [
            {
                "signalId": "signal-1",
                "accepted": False,
                "reason": "capacity_or_sizing_rejected",
                "actualNotional": None,
            }
        ]
    }
    implementation = {
        "decisions": [
            {
                "signalId": "signal-1",
                "accepted": False,
                "reason": "portfolio_beta_limit",
                "actualNotional": None,
            }
        ]
    }

    report = compare_capital_replays(reference, implementation)

    assert report["status"] == "failed"
    assert report["capitalAcceptanceParityPct"] == 0.0
    assert "capital_acceptance_mismatch" in report["blockers"]
