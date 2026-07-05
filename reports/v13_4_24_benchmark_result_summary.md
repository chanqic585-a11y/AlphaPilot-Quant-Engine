# AlphaPilot V13.4.24 Benchmark Result Review Summary

This review reads V13.4.23 benchmark reports only. It does not run a new backtest, approve Dry-run, or approve live trading.

## Core Conclusion

- Active benchmarks did not prove a tradable advantage.
- BenchmarkBollingerRebound was the relative best active benchmark, but relative best does not mean usable.
- NoTrade and BuyHoldBTC remain mandatory baselines for future strategy research.
- The recommended next step is Strategy Research Factory / Factor Hypothesis Mining, not benchmark parameter tuning.

## NoTrade Comparison

- baselineReturnPct: 0.0
- activeBenchmarksOutperformed: 0/5
- summary: All active benchmarks underperformed NoTrade on the selected sample, before and after slippage stress.

## BuyHoldBTC Comparison

- buyHoldReturnPct: -27.9751
- buyHoldMaxDrawdownPct: 40.3093
- activeBenchmarksOutperformed: 0/5
- summary: All active benchmarks underperformed BuyHoldBTC; simple passive BTC exposure lost less than frequent benchmark trading in this sample.

## Best Benchmark Review

- className: BenchmarkBollingerRebound
- rawReturnPct: -87.6274
- slippageAdjustedReturnPct: -181.9728
- maxDrawdownPct: 87.6274
- profitFactor: 0.4513
- tradeCount: 816
- conclusion: relative best != tradable

## Benchmark Family Review

| Benchmark | Status | Raw Return % | Adj Return % | PF | Trades | Cost Sensitivity | Main Weakness |
|---|---|---:|---:|---:|---:|---|---|
| BenchmarkEMATrend | failed_benchmark | -99.971 | -204.7794 | 0.5658 | 2723 | very_high | Excessive trade frequency and repeated losses overwhelm any simple rule edge. |
| BenchmarkRSIMeanReversion | failed_benchmark | -99.831 | -195.5122 | 0.404 | 2190 | very_high | Excessive trade frequency and repeated losses overwhelm any simple rule edge. |
| BenchmarkMACDVolume | failed_benchmark | -99.6544 | -229.9537 | 0.6115 | 2141 | very_high | Excessive trade frequency and repeated losses overwhelm any simple rule edge. |
| BenchmarkBollingerRebound | research_reference | -87.6274 | -181.9728 | 0.4513 | 816 | high | Relative best, but still negative with high drawdown and profit factor below 1. |
| BenchmarkTD9Exhaustion | failed_benchmark | -96.7071 | -223.5336 | 0.5499 | 1333 | very_high | Very high cost sensitivity after slippage stress. |

## Failure Findings

- 5/5 active benchmarks failed to beat NoTrade after slippage stress.
- All active benchmarks failed to beat BuyHoldBTC on the selected Top10 / 1h / 20260101- sample.
- BenchmarkBollingerRebound is the relative best active benchmark, but it remains negative and has profit factor below 1.
- High or very high cost sensitivity appears in: BenchmarkEMATrend, BenchmarkRSIMeanReversion, BenchmarkMACDVolume, BenchmarkBollingerRebound, BenchmarkTD9Exhaustion.
- Pair and month stability do not show a robust positive pattern; losses are broad rather than isolated to one small pocket.
- Exit attribution is not available in the V13.4.23 benchmark report and should be added to future benchmark reporting.
- Current evidence does not support Dry-run, live trading, or direct benchmark parameter tuning.

## Useful Hypothesis Seeds

- bollinger_mean_reversion_research: Study mean-reversion / deviation recovery with stricter filters, lower frequency, and stronger regime context.
- avoid_simple_ema_trend_baseline: Simple EMA trend is a negative reference; future trend logic needs richer regime and volatility context.
- momentum_volume_needs_quality_filter: Momentum plus volume alone is insufficient; study quality filters and fewer trades.
- td9_not_standalone: TD-style exhaustion counts should not stand alone; only consider as one contextual feature.
- baseline_discipline_required: Every future strategy candidate must clear NoTrade, BuyHoldBTC, and BenchmarkBollingerRebound after costs.

## Rejected Ideas

- rejected_benchmark_martingale: Martingale or inverse averaging creates unacceptable tail risk and conflicts with AlphaPilot risk-first principles.

## Recommended Next Step

- V13.4.25 - Strategy Research Factory: Factor Hypothesis Mining

## Safety Boundary

- dryRunApproved: false
- liveTradingApproved: false
- no new backtest run
- no benchmark strategy code changes
- no real API key
- no Trade API / Withdraw API
- no account or position reads
- no real orders
- no auto trading

## Warnings

- BenchmarkBollingerRebound exit attribution unavailable in V13.4.23 report.
- BenchmarkEMATrend exit attribution unavailable in V13.4.23 report.
- BenchmarkMACDVolume exit attribution unavailable in V13.4.23 report.
- BenchmarkRSIMeanReversion exit attribution unavailable in V13.4.23 report.
- BenchmarkTD9Exhaustion exit attribution unavailable in V13.4.23 report.
