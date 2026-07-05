"""Benchmark suite research helpers."""

from alphapilot.benchmarks.benchmark_registry import (
    BENCHMARK_REGISTRY,
    REJECTED_BENCHMARK_IDEAS,
    BenchmarkRegistryItem,
    get_benchmark_by_class,
    list_benchmark_registry,
    list_freqtrade_benchmark_classes,
)
from alphapilot.benchmarks.benchmark_suite_spec import build_benchmark_suite_spec
from alphapilot.benchmarks.benchmark_suite_runner import (
    BenchmarkSuiteScope,
    default_benchmark_strategies,
    resolve_benchmark_pairs,
)
from alphapilot.benchmarks.benchmark_strategy_schema import BenchmarkStrategySpec
from alphapilot.benchmarks.buy_hold_baseline import (
    build_buy_hold_btc_baseline,
    build_no_trade_baseline,
)

__all__ = [
    "BENCHMARK_REGISTRY",
    "REJECTED_BENCHMARK_IDEAS",
    "BenchmarkSuiteScope",
    "BenchmarkRegistryItem",
    "BenchmarkStrategySpec",
    "build_benchmark_suite_spec",
    "build_buy_hold_btc_baseline",
    "build_no_trade_baseline",
    "default_benchmark_strategies",
    "get_benchmark_by_class",
    "list_benchmark_registry",
    "list_freqtrade_benchmark_classes",
    "resolve_benchmark_pairs",
]
