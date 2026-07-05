# Benchmark Results Interpretation

Benchmark results are research artifacts. They are not trading signals, not
orders, and not approval for Dry-run or live trading.

## Primary Metrics

- total return
- slippage-adjusted total return
- max drawdown
- profit factor
- slippage-adjusted profit factor
- win rate
- trade count
- max consecutive losses
- average holding minutes
- fees paid
- slippage cost estimate
- monthly stability
- pair stability

## Baseline Comparisons

The suite always includes:

```text
NoTrade baseline
BuyHoldBTC baseline
```

A benchmark can be worse than not trading. That outcome is valid research
evidence and should not be hidden.

## Slippage Stress

V13.4.23 applies slippage stress in post-processing:

```text
0.05% one-way
0.10% one-way
0.20% one-way
```

The JSON report explicitly records:

```text
slippageAppliedByFreqtrade: false
slippageAppliedByPostProcessing: true
```

## Promotion Boundary

No benchmark is promoted directly to execution.

Additional work is required before any later Dry-run discussion:

- expanded market validation
- slippage and liquidity stress
- out-of-sample review
- risk gate review
- manual approval workflow
- explicit safety sign-off

## V13.4.24 Result Review

V13.4.24 reviewed the V13.4.23 benchmark output and found:

- every active benchmark underperformed NoTrade after slippage stress
- every active benchmark underperformed BuyHoldBTC
- BenchmarkBollingerRebound was the relative best active benchmark, but still
  negative and not strategy-ready
- cost sensitivity was high across the active benchmark set
- exit attribution should be added to future benchmark reports

The recommended next step is research reset and hypothesis mining, not benchmark
parameter tuning.
