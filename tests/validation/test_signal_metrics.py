from __future__ import annotations

from alphapilot.validation.signal_metrics import (
    block_bootstrap_metrics,
    summarize_trades,
)


def _trades() -> list[dict]:
    return [
        {
            "instrumentId": "BTC-USDT-SWAP",
            "entryTimestampMs": 1_700_000_000_000,
            "exitTimestampMs": 1_700_003_600_000,
            "netR": 2.0,
            "grossR": 2.1,
            "mfeR": 2.4,
            "maeR": -0.3,
            "split": "locked_oos",
            "fold": None,
            "regime": "bull",
            "direction": "long",
            "setupName": "breakout",
            "exitReason": "target",
        },
        {
            "instrumentId": "ETH-USDT-SWAP",
            "entryTimestampMs": 1_702_700_000_000,
            "exitTimestampMs": 1_702_703_600_000,
            "netR": -1.0,
            "grossR": -0.9,
            "mfeR": 0.2,
            "maeR": -1.1,
            "split": "locked_oos",
            "fold": None,
            "regime": "bear",
            "direction": "long",
            "setupName": "breakout",
            "exitReason": "stop",
        },
        {
            "instrumentId": "BTC-USDT-SWAP",
            "entryTimestampMs": 1_705_300_000_000,
            "exitTimestampMs": 1_705_303_600_000,
            "netR": 1.0,
            "grossR": 1.1,
            "mfeR": 1.2,
            "maeR": -0.2,
            "split": "walk_forward",
            "fold": 1,
            "regime": "range",
            "direction": "long",
            "setupName": "breakout",
            "exitReason": "runner",
        },
    ]


def test_signal_summary_is_complete_and_does_not_invent_path_order() -> None:
    summary = summarize_trades(_trades())

    assert summary["tradeCount"] == 3
    assert summary["profitFactor"] == 3.0
    assert summary["averageNetR"] == 2.0 / 3.0
    assert summary["medianNetR"] == 1.0
    assert summary["touchRates"]["plusTwoR"] == 1.0 / 3.0
    assert summary["firstHitRates"]["plusOneRFirst"] is None
    assert summary["breakdowns"]["instrument"]["BTC-USDT-SWAP"]["tradeCount"] == 2
    assert summary["maximumConsecutiveLosses"] == 1


def test_block_bootstrap_is_deterministic_and_reports_probabilities() -> None:
    first = block_bootstrap_metrics(_trades(), draws=200, seed=17)
    second = block_bootstrap_metrics(_trades(), draws=200, seed=17)

    assert first == second
    assert first["draws"] == 200
    assert 0.0 <= first["probabilityAverageNetRPositive"] <= 1.0
    assert 0.0 <= first["probabilityProfitFactorAboveOne"] <= 1.0
    assert set(first["averageNetRIntervals"]) == {"80", "90", "95"}
