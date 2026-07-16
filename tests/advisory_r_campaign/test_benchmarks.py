from __future__ import annotations

import pandas as pd

from alphapilot.advisory_r_campaign.benchmarks import (
    BENCHMARK_BY_VARIANT,
    build_benchmark_comparison,
)


def test_all_frozen_simple_benchmarks_are_registered() -> None:
    assert set(BENCHMARK_BY_VARIANT) == {f"S{index:02d}" for index in range(1, 11)}
    assert BENCHMARK_BY_VARIANT["S01"] == "same_event_fixed_12_bar_exit"
    assert BENCHMARK_BY_VARIANT["S10"] == "equal_weight_component_signals"


def test_fixed_hold_benchmark_uses_same_signal_direction_cost_and_risk() -> None:
    dates = pd.date_range("2026-01-01", periods=20, freq="1h", tz="UTC")
    close = [100.0 + index for index in range(20)]
    frame = pd.DataFrame(
        {
            "date": dates,
            "open": close,
            "high": [value + 0.5 for value in close],
            "low": [value - 0.5 for value in close],
            "close": close,
            "volume": [1_000.0] * 20,
        }
    )
    candidate = {
        "candidateId": "candidate-1",
        "variantId": "S01",
        "simpleBenchmark": "same_event_fixed_12_bar_exit",
    }
    event = {
        "candidateId": "candidate-1",
        "symbol": "BTC-USDT-SWAP",
        "side": "long",
        "signalIndex": 1,
        "entryIndex": 2,
        "entryPrice": 102.0,
        "riskDistance": 2.0,
        "netR": 0.5,
        "feesR": 0.01,
        "slippageR": 0.01,
        "spreadProxyR": 0.01,
    }

    comparison = build_benchmark_comparison(
        [candidate],
        {"candidate-1": [event]},
        {"1h": {"BTC-USDT-SWAP": frame}},
    )[0]

    assert comparison["benchmarkName"] == "same_event_fixed_12_bar_exit"
    assert comparison["candidateNetR"] == 0.5
    assert comparison["benchmarkNetR"] == 5.97
    assert comparison["incrementalNetR"] == -5.47
    assert "candidatePF" in comparison
    assert "benchmarkPF" in comparison


def test_portfolio_benchmark_uses_same_event_window_not_full_sample_return() -> None:
    dates = pd.date_range("2026-01-01", periods=8, freq="4h", tz="UTC")
    frames = {}
    for symbol, scale in (("BTC-USDT-SWAP", 1.0), ("ETH-USDT-SWAP", 2.0)):
        close = [(100.0 + index) * scale for index in range(8)]
        frames[symbol] = pd.DataFrame(
            {
                "date": dates,
                "open": close,
                "high": [value + 0.5 for value in close],
                "low": [value - 0.5 for value in close],
                "close": close,
                "volume": [1_000.0] * 8,
            }
        )
    candidate = {
        "candidateId": "candidate-9",
        "variantId": "S09",
        "timeframe": "4h",
        "simpleBenchmark": "equal_weight_representative_universe",
    }
    event = {
        "candidateId": "candidate-9",
        "symbol": "PORTFOLIO",
        "side": "long",
        "entryIndex": 1,
        "exitIndex": 4,
        "entryPrice": 100.0,
        "riskDistance": 2.0,
        "netR": 0.25,
        "feesR": 0.01,
        "slippageR": 0.01,
        "spreadProxyR": 0.01,
    }

    comparison = build_benchmark_comparison(
        [candidate],
        {"candidate-9": [event]},
        {"4h": frames},
    )[0]

    assert comparison["benchmarkObservationCount"] == 1
    assert "same entry/exit window" in comparison["method"]
    assert comparison["addedAsHardGate"] is False


def test_pair_benchmark_uses_independent_pair_exit_result() -> None:
    candidate = {
        "candidateId": "candidate-4",
        "variantId": "S04",
        "timeframe": "1h",
        "simpleBenchmark": "pair_residual_zero_cross",
    }
    event = {
        "candidateId": "candidate-4",
        "symbol": "ETH-USDT-SWAP|BTC-USDT-SWAP",
        "netR": 0.75,
        "simpleBenchmarkNetR": 0.25,
        "simpleBenchmarkExitReason": "residual_zero_cross",
    }

    comparison = build_benchmark_comparison(
        [candidate],
        {"candidate-4": [event]},
        {"1h": {}},
    )[0]

    assert comparison["candidateNetR"] == 0.75
    assert comparison["benchmarkNetR"] == 0.25
    assert comparison["incrementalNetR"] == 0.5
    assert "zero-cross" in comparison["method"]


def test_s10_benchmark_equal_weights_frozen_component_signals() -> None:
    dates = pd.date_range("2026-01-01", periods=80, freq="4h", tz="UTC")
    closes = [100.0 + index * 0.2 for index in range(80)]
    volumes = [1_000.0] * 80
    volumes[60] = 2_000.0
    frame = pd.DataFrame(
        {
            "date": dates,
            "open": closes,
            "high": [value + 0.5 for value in closes],
            "low": [value - 0.5 for value in closes],
            "close": closes,
            "volume": volumes,
        }
    )
    candidate = {
        "candidateId": "candidate-10",
        "variantId": "S10",
        "timeframe": "4h",
        "simpleBenchmark": "equal_weight_component_signals",
        "featureDefinition": {
            "signals": ["residual_turn", "volume_surprise", "trend_slope"],
            "minimumVotes": 2,
        },
    }
    event = {
        "candidateId": "candidate-10",
        "symbol": "ETH-USDT-SWAP",
        "side": "long",
        "signalIndex": 60,
        "entryIndex": 61,
        "exitIndex": 64,
        "entryPrice": closes[61],
        "riskDistance": 2.0,
        "netR": 0.75,
        "feesR": 0.01,
        "slippageR": 0.01,
        "spreadProxyR": 0.01,
    }

    comparison = build_benchmark_comparison(
        [candidate],
        {"candidate-10": [event]},
        {"4h": {"ETH-USDT-SWAP": frame}},
    )[0]

    assert comparison["benchmarkObservationCount"] == 1
    assert "three frozen component signals" in comparison["method"]
    assert comparison["benchmarkNetR"] != comparison["candidateNetR"]
