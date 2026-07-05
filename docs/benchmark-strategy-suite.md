# Benchmark Strategy Suite

The Benchmark Strategy Suite defines comparison references for future
AlphaPilot strategy research.

Benchmarks are not live strategies and are not Dry-run approvals.

## V01 Benchmarks

```text
Benchmark_EMA_Trend
Benchmark_RSI_MeanReversion
Benchmark_MACD_Volume
Benchmark_Bollinger_Rebound
Benchmark_TD9_Exhaustion
Benchmark_BuyAndHold_BTC
Benchmark_NoTrade
```

## Comparison Questions

- Is AlphaPilot better than no trade?
- Is AlphaPilot better than holding BTC?
- Is AlphaPilot better than a simple EMA trend baseline?
- Is AlphaPilot better than a simple RSI mean-reversion baseline?
- Does strategy complexity improve drawdown, stability, or profit factor after
  fees and slippage?

## Comparison Metrics

```text
total return
slippage-adjusted return
max drawdown
profit factor
win rate
trade count
max loss streak
monthly stability
pair stability
```

## Rejected Benchmark Idea

Martingale or inverse averaging is recorded only as a rejected benchmark idea.
It conflicts with AlphaPilot's risk-first design.

## V13.4.23 Implementation

V13.4.23 implements the benchmark suite as local research code and report
generation:

```text
user_data/strategies/AlphaPilotBenchmarkStrategies.py
alphapilot/benchmarks/benchmark_registry.py
scripts/run_benchmark_suite.ps1
alphapilot/reports/generate_benchmark_suite_report.py
```

The suite remains research-only:

```text
dryRunApproved: false
liveTradingApproved: false
no Trade API / Withdraw API
no real API key
no account / position reads
no real orders
no auto trading
```
