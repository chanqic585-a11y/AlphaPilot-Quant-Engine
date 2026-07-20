from __future__ import annotations

import pandas as pd

from alphapilot.demo_release_replay import adapters


def _frame(pair: str) -> pd.DataFrame:
    dates = pd.date_range("2025-01-01", periods=8, freq="h", tz="UTC")
    return pd.DataFrame(
        {
            "date": dates,
            "open": [100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0],
            "high": [101.0, 101.0, 103.0, 101.0, 101.0, 101.0, 101.0, 101.0],
            "low": [99.0, 99.0, 99.0, 99.0, 99.0, 99.0, 99.0, 99.0],
            "close": [100.0] * 8,
            "volume": [10.0] * 8,
            "pair": [pair] * 8,
            "atr14": [1.0] * 8,
            "ema20": [100.0] * 8,
            "btc_ret_3": [0.0] * 8,
        }
    )


def test_short_cycle_replay_uses_next_bar_and_cost_adjusted_r(monkeypatch) -> None:
    frame = _frame("AAA/USDT:USDT")

    def fake_signal(data: pd.DataFrame, family: str, params: dict[str, object]):
        signal = pd.Series(False, index=data.index)
        signal.iloc[0] = True
        return signal, "long"

    monkeypatch.setattr(adapters, "build_signal", fake_signal)
    candidate = {
        "candidateId": "short_1",
        "family": "test_family",
        "direction": "long",
        "timeframe": "1h",
        "targetR": 2.0,
        "params": {"stop_atr": 1.0, "max_hold": 3},
        "assetFilter": {"selectedPairs": ["AAA/USDT:USDT"]},
    }

    result = adapters.replay_short_cycle_candidate(
        candidate,
        {"AAA/USDT:USDT": frame},
        fee_rate=0.0005,
        slippage_rate=0.0005,
    )

    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade["entryDate"] == frame.iloc[1].date.isoformat()
    assert trade["entryPrice"] > frame.iloc[1].open
    assert trade["grossR"] > trade["netR"]
    assert trade["feeR"] > 0
    assert result.status == "research_replay_only"
    assert result.selected_pairs == ("AAA/USDT:USDT",)


def test_short_cycle_replay_preserves_train_selected_pairs(monkeypatch) -> None:
    def no_signals(data: pd.DataFrame, family: str, params: dict[str, object]):
        return pd.Series(False, index=data.index), "short"

    monkeypatch.setattr(adapters, "build_signal", no_signals)
    candidate = {
        "candidateId": "short_2",
        "family": "short_rejection",
        "direction": "short",
        "timeframe": "1h",
        "targetR": 2.0,
        "params": {"stop_atr": 1.0, "max_hold": 3},
        "assetFilter": {"selectedPairs": ["BBB/USDT:USDT", "AAA/USDT:USDT"]},
    }

    result = adapters.replay_short_cycle_candidate(
        candidate,
        {
            "AAA/USDT:USDT": _frame("AAA/USDT:USDT"),
            "BBB/USDT:USDT": _frame("BBB/USDT:USDT"),
            "CCC/USDT:USDT": _frame("CCC/USDT:USDT"),
        },
    )

    assert result.selected_pairs == ("AAA/USDT:USDT", "BBB/USDT:USDT")


def test_low_frequency_replay_keeps_frozen_spec_and_normalizes_ledger(monkeypatch) -> None:
    def fake_simulate(spec, prepared_frames):
        assert spec.candidate_id == "lf_research_candidate_089"
        assert tuple(prepared_frames) == ("ETH/USDT:USDT",)
        return [
            {
                "candidateId": spec.candidate_id,
                "pair": "ETH/USDT:USDT",
                "entryTimestamp": "2025-01-01T00:00:00Z",
                "exitTimestamp": "2025-01-02T00:00:00Z",
                "entryPrice": 100.0,
                "exitPrice": 102.0,
                "grossR": 2.0,
                "feeR": 0.1,
                "netR": 1.9,
                "exitReason": "target_2r",
                "holdBars": 1,
            }
        ]

    monkeypatch.setattr(adapters, "_simulate_candidate", fake_simulate)
    result = adapters.replay_low_frequency_candidate(
        "v13_7_20_lf_research_candidate_089",
        {"ETH/USDT:USDT": pd.DataFrame({"unused": [1]})},
    )

    assert result.family == "breakout"
    assert result.timeframe == "1d"
    assert result.trades[0]["candidateId"] == "v13_7_20_lf_research_candidate_089"
    assert result.trades[0]["entryDate"] == "2025-01-01T00:00:00Z"
    assert result.metrics["profitFactor"] is None
    assert result.metrics["expectancyR"] == 1.9


def test_replay_result_never_claims_release_or_approval() -> None:
    result = adapters.ReplayResult(
        candidate_id="candidate",
        family="family",
        timeframe="1h",
        direction="long",
        selected_pairs=(),
        trades=(),
        metrics={},
        split_metrics={},
    )
    payload = result.to_dict()

    assert payload["status"] == "research_replay_only"
    assert "release" not in payload
    assert "approvedForDemo" not in payload
    assert "liveTradingApproved" not in payload
