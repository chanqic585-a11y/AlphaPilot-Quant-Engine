# Strategy Research Reset Plan

V13.4.24 resets the research direction away from writing more simple benchmark
strategies.

## Why Reset

The V13.4.23 benchmark suite showed that simple rule families did not provide a
tradable edge in the selected sample. Continuing to tune those benchmark
parameters would risk overfitting a weak base.

## Reset Completed By

```text
V13.4.25 - Strategy Research Factory: Factor Hypothesis Mining
```

V13.4.25 completed the reset by converting V13.4.22 factor evidence, V13.4.23
benchmark outcomes, and V13.4.24 failure review into a structured hypothesis
registry.

## Goals

- combine V13.4.22 factor evaluation with V13.4.23 benchmark results
- use V13.4.24 failure attribution to avoid high-turnover weak rules
- extract research-only hypotheses
- prioritize Bollinger / mean-reversion and low-frequency quality filters
- compare all future hypotheses against NoTrade, BuyHoldBTC, and
  BenchmarkBollingerRebound

## Non Goals

```text
no new trading strategy implementation
no new backtest run
no Dry-run
no live trading
no real API key
no Trade API / Withdraw API
no account / position reads
no real orders
no auto trading
```

## Current Next Version

```text
V13.4.26 - Factor Hypothesis Validation Dataset
```

V13.4.26 should validate the high-priority hypotheses from V13.4.25 in a
research dataset before any future strategy implementation.
