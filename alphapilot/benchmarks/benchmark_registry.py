"""Benchmark registry for V13.4.23.

Benchmark records are comparison references only. They are not approved for
Dry-run or live trading.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class BenchmarkRegistryItem:
    benchmarkId: str
    name: str
    type: str
    timeframe: str
    direction: str
    status: str
    description: str
    riskNotes: list[str]
    isFreqtradeStrategy: bool
    className: str | None
    isReportOnly: bool
    dryRunApproved: bool = False
    liveTradingApproved: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


COMMON_RISK_NOTES = [
    "Research-only benchmark. Not a production AlphaPilot strategy.",
    "Benchmark performance does not approve Dry-run or live trading.",
    "No benchmark may use real API keys, Trade API, Withdraw API, account reads, orders, or auto trading.",
]


BENCHMARK_REGISTRY = [
    BenchmarkRegistryItem(
        benchmarkId="benchmark_no_trade",
        name="Benchmark No Trade",
        type="report_only_baseline",
        timeframe="1h",
        direction="none",
        status="research_only",
        description="Zero-return no-trade baseline.",
        riskNotes=COMMON_RISK_NOTES,
        isFreqtradeStrategy=False,
        className=None,
        isReportOnly=True,
    ),
    BenchmarkRegistryItem(
        benchmarkId="benchmark_buy_hold_btc",
        name="Benchmark Buy Hold BTC",
        type="report_only_baseline",
        timeframe="1h",
        direction="long_only_reference",
        status="research_only",
        description="Passive BTC hold reference over the same timerange.",
        riskNotes=COMMON_RISK_NOTES,
        isFreqtradeStrategy=False,
        className=None,
        isReportOnly=True,
    ),
    BenchmarkRegistryItem(
        benchmarkId="benchmark_ema_trend",
        name="Benchmark EMA Trend",
        type="freqtrade_backtest_baseline",
        timeframe="1h",
        direction="long_only",
        status="research_only",
        description="EMA20/EMA50 trend-following baseline with MACD confirmation.",
        riskNotes=COMMON_RISK_NOTES,
        isFreqtradeStrategy=True,
        className="BenchmarkEMATrend",
        isReportOnly=False,
    ),
    BenchmarkRegistryItem(
        benchmarkId="benchmark_rsi_mean_reversion",
        name="Benchmark RSI Mean Reversion",
        type="freqtrade_backtest_baseline",
        timeframe="1h",
        direction="long_only",
        status="research_only",
        description="RSI and Bollinger lower-band mean-reversion baseline.",
        riskNotes=COMMON_RISK_NOTES,
        isFreqtradeStrategy=True,
        className="BenchmarkRSIMeanReversion",
        isReportOnly=False,
    ),
    BenchmarkRegistryItem(
        benchmarkId="benchmark_macd_volume",
        name="Benchmark MACD Volume",
        type="freqtrade_backtest_baseline",
        timeframe="1h",
        direction="long_only",
        status="research_only",
        description="MACD momentum with volume confirmation baseline.",
        riskNotes=COMMON_RISK_NOTES,
        isFreqtradeStrategy=True,
        className="BenchmarkMACDVolume",
        isReportOnly=False,
    ),
    BenchmarkRegistryItem(
        benchmarkId="benchmark_bollinger_rebound",
        name="Benchmark Bollinger Rebound",
        type="freqtrade_backtest_baseline",
        timeframe="1h",
        direction="long_only",
        status="research_only",
        description="Bollinger lower-band reclaim baseline.",
        riskNotes=COMMON_RISK_NOTES,
        isFreqtradeStrategy=True,
        className="BenchmarkBollingerRebound",
        isReportOnly=False,
    ),
    BenchmarkRegistryItem(
        benchmarkId="benchmark_td9_exhaustion",
        name="Benchmark TD9 Exhaustion",
        type="freqtrade_backtest_baseline",
        timeframe="1h",
        direction="long_only",
        status="research_only",
        description="Simplified TD9-style exhaustion baseline.",
        riskNotes=COMMON_RISK_NOTES,
        isFreqtradeStrategy=True,
        className="BenchmarkTD9Exhaustion",
        isReportOnly=False,
    ),
]


REJECTED_BENCHMARK_IDEAS = [
    {
        "benchmarkId": "rejected_benchmark_martingale",
        "name": "Rejected Benchmark Martingale",
        "status": "rejected_benchmark_idea",
        "reason": "Martingale or inverse averaging creates unacceptable tail risk and conflicts with AlphaPilot risk-first principles.",
        "dryRunApproved": False,
        "liveTradingApproved": False,
    }
]


def list_benchmark_registry() -> list[dict[str, Any]]:
    return [item.to_dict() for item in BENCHMARK_REGISTRY]


def list_freqtrade_benchmark_classes() -> list[str]:
    return [item.className for item in BENCHMARK_REGISTRY if item.isFreqtradeStrategy and item.className]


def get_benchmark_by_class(class_name: str) -> dict[str, Any] | None:
    for item in BENCHMARK_REGISTRY:
        if item.className == class_name:
            return item.to_dict()
    return None
