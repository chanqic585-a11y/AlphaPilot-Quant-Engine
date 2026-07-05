"""Schema for V13.4.23 benchmark suite report."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class BenchmarkSuiteReport:
    reportId: str
    timerange: str
    timeframe: str
    requestedPairs: list[str]
    supportedPairs: list[str]
    excludedPairs: list[dict[str, str]]
    benchmarks: list[dict[str, Any]]
    bestBenchmarkRaw: str | None
    bestBenchmarkSlippageAdjusted: str | None
    noTradeBaseline: dict[str, Any]
    buyHoldBtcBaseline: dict[str, Any]
    rejectedBenchmarkIdeas: list[dict[str, Any]]
    interpretation: list[str]
    warnings: list[str]
    dryRunApproved: bool
    liveTradingApproved: bool
    generatedAt: str
    source: str = "alphapilot_v13_4_23_benchmark_suite"
    slippageAppliedByFreqtrade: bool = False
    slippageAppliedByPostProcessing: bool = True
    slippageRatesOneWay: list[float] = field(default_factory=lambda: [0.0005, 0.001, 0.002])

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
