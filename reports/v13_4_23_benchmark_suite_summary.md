# AlphaPilot V13.4.23 Benchmark Strategy Suite Summary

This is a research-only benchmark comparison. It is not a Dry-run approval and not live trading approval.

## Scope

- timerange: 20260101-
- timeframe: 1h
- requestedPairs: 10
- supportedPairs: 10
- bestBenchmarkRaw: BenchmarkBollingerRebound
- bestBenchmarkSlippageAdjusted: BenchmarkBollingerRebound
- dryRunApproved: False
- liveTradingApproved: False

## Benchmark Table

| Benchmark | Type | Return % | Adj Return % | Drawdown % | PF | Adj PF | Trades | Win Rate % |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Benchmark No Trade | report_only_baseline | 0.0 | 0.0 | 0.0 | None | None | 0 | None |
| Benchmark Buy Hold BTC | report_only_baseline | -27.9751 | -27.9751 | 40.3093 | None | None | 1 | None |
| Benchmark EMA Trend | freqtrade_backtest_baseline | -99.971 | -204.7794 | 99.9714 | 0.5658 | 0.3369 | 2723 | 25.2663 |
| Benchmark RSI Mean Reversion | freqtrade_backtest_baseline | -99.831 | -195.5122 | 99.8411 | 0.404 | 0.1709 | 2190 | 31.5525 |
| Benchmark MACD Volume | freqtrade_backtest_baseline | -99.6544 | -229.9537 | 99.6755 | 0.6115 | 0.3365 | 2141 | 30.78 |
| Benchmark Bollinger Rebound | freqtrade_backtest_baseline | -87.6274 | -181.9728 | 87.6274 | 0.4513 | 0.1895 | 816 | 34.5588 |
| Benchmark TD9 Exhaustion | freqtrade_backtest_baseline | -96.7071 | -223.5336 | 96.9997 | 0.5499 | 0.2596 | 1333 | 31.2078 |

## Rejected Benchmark Ideas

- Rejected Benchmark Martingale: rejected_benchmark_idea - Martingale or inverse averaging creates unacceptable tail risk and conflicts with AlphaPilot risk-first principles.

## Interpretation

- Benchmark profitability does not imply trade readiness.
- Benchmarks are comparison references only.
- Future complex strategies must beat NoTrade, BuyHoldBTC, and simple benchmark baselines after costs.
- No benchmark is approved for Dry-run or live trading.
- Martingale and inverse averaging are rejected benchmark ideas.

## Warnings

- none

## Safety Boundary

- no Dry-run
- no live trading
- no real API key
- no Trade API / Withdraw API
- no account or position reads
- no real orders
- no auto trading
