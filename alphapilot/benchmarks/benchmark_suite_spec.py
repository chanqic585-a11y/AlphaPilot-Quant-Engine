"""Benchmark Strategy Suite spec for V13.4.20+ and V13.4.23 implementation."""

from __future__ import annotations

from typing import Any

from alphapilot.benchmarks.benchmark_strategy_schema import BenchmarkStrategySpec

COMPARISON_METRICS = [
    "total_return",
    "slippage_adjusted_return",
    "max_drawdown",
    "profit_factor",
    "win_rate",
    "trade_count",
    "max_loss_streak",
    "monthly_stability",
    "pair_stability",
]


def _benchmark(benchmark_id: str, name: str, purpose: str, hypothesis: str, required_fields: list[str]) -> BenchmarkStrategySpec:
    return BenchmarkStrategySpec(
        benchmarkId=benchmark_id,
        name=name,
        purpose=purpose,
        hypothesis=hypothesis,
        requiredFields=required_fields,
        comparisonMetrics=COMPARISON_METRICS,
        riskNotes=[
            "Benchmark is research-only.",
            "Benchmark result does not approve Dry-run or live trading.",
            "Benchmark should be compared after fees, slippage, liquidity, and drawdown are considered.",
        ],
    )


BENCHMARK_SUITE_V01 = [
    _benchmark("benchmark_ema_trend", "Benchmark EMA Trend", "Simple trend-following baseline.", "Complex AlphaPilot strategies should beat a simple EMA trend reference.", ["close"]),
    _benchmark("benchmark_rsi_mean_reversion", "Benchmark RSI Mean Reversion", "Simple RSI mean-reversion baseline.", "Mean reversion candidates should beat a transparent RSI baseline.", ["close"]),
    _benchmark("benchmark_macd_volume", "Benchmark MACD Volume", "MACD direction with volume confirmation baseline.", "Momentum candidates should justify complexity versus MACD plus volume.", ["close", "volume"]),
    _benchmark("benchmark_bollinger_rebound", "Benchmark Bollinger Rebound", "Bollinger band rebound baseline.", "Rebound candidates should beat simple band-position logic.", ["close"]),
    _benchmark("benchmark_td9_exhaustion", "Benchmark TD9 Exhaustion", "Exhaustion-pattern comparison baseline.", "Exhaustion logic should be measured as a benchmark, not assumed useful.", ["close"]),
    _benchmark("benchmark_buy_and_hold_btc", "Benchmark Buy And Hold BTC", "BTC passive hold reference.", "Active research must be compared to BTC hold.", ["close"]),
    _benchmark("benchmark_no_trade", "Benchmark No Trade", "Zero-risk no-trade baseline.", "A strategy can be worse than not trading and must prove otherwise.", []),
]

REJECTED_BENCHMARK_IDEAS = [
    {
        "benchmarkId": "martingale_inverse_averaging",
        "status": "rejected_idea",
        "reason": "Martingale or inverse averaging increases tail risk and conflicts with AlphaPilot risk-first principles.",
    }
]


def build_benchmark_suite_spec() -> dict[str, Any]:
    return {
        "suiteId": "alphapilot_benchmark_strategy_suite_v01",
        "purpose": "Compare AlphaPilot research candidates against transparent simple baselines.",
        "benchmarks": [item.to_dict() for item in BENCHMARK_SUITE_V01],
        "comparisonMetrics": COMPARISON_METRICS,
        "rejectedBenchmarkIdeas": REJECTED_BENCHMARK_IDEAS,
        "researchOnly": True,
        "implementationStatus": "implemented_for_research_backtest_v13_4_23",
    }
