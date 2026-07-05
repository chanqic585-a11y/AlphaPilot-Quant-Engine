"""Benchmark suite runner command builder.

The PowerShell runner executes Docker/Freqtrade. This module keeps strategy and
pair selection centralized for V13.4.23.
"""

from __future__ import annotations

from dataclasses import dataclass

from alphapilot.benchmarks.benchmark_registry import list_freqtrade_benchmark_classes
from alphapilot.universe.top30_usdt_swap import get_top30_usdt_swap_pairs


@dataclass(frozen=True)
class BenchmarkSuiteScope:
    timerange: str = "20260101-"
    timeframe: str = "1h"
    pairsMode: str = "top10"


def get_top10_usdt_swap_pairs() -> list[str]:
    return get_top30_usdt_swap_pairs()[:10]


def resolve_benchmark_pairs(use_top10: bool = True, use_top30: bool = False, pairs: str = "") -> list[str]:
    if pairs.strip():
        return [part.strip() for part in pairs.split(",") if part.strip()]
    if use_top30:
        return get_top30_usdt_swap_pairs()
    if use_top10:
        return get_top10_usdt_swap_pairs()
    return get_top10_usdt_swap_pairs()


def default_benchmark_strategies() -> list[str]:
    return list_freqtrade_benchmark_classes()
