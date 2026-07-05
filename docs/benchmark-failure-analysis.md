# Benchmark Failure Analysis

The V13.4.23 benchmark results are useful because they show that simple,
transparent rules are not enough for AlphaPilot's current market sample.

## Failure Pattern

The active benchmark families all lost money after costs:

```text
BenchmarkEMATrend
BenchmarkRSIMeanReversion
BenchmarkMACDVolume
BenchmarkBollingerRebound
BenchmarkTD9Exhaustion
```

The common issues are:

- too much turnover for the available edge
- repeated stop-loss or adverse exits
- profit factor below 1
- drawdown too high
- slippage-adjusted returns worse than raw returns by a large margin
- no broad positive month or pair stability

## Relative Best Is Not Enough

BenchmarkBollingerRebound lost less than the other active benchmarks, but it
still failed the basic research bar:

- negative raw return
- worse slippage-adjusted return
- profit factor below 1
- high drawdown
- 0 positive months in the available monthly stability table

This makes it a hypothesis seed, not a strategy.

## Reporting Gap

The V13.4.23 suite does not expose detailed exit attribution in the aggregate
report. Future benchmark reports should add:

```text
stop_loss count
roi / take-profit count
signal_exit count
force_exit / EOF count
```

Without this, failure attribution can identify cost, frequency, pair, and month
patterns, but not the exact exit-path mix.
