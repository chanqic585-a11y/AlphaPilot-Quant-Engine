# Next Experiment Plan

Recommended next version:

```text
V13.4.26 - Factor Hypothesis Validation Dataset
```

## Goal

Build a validation dataset for the V13.4.25 high-priority hypotheses before any
future strategy implementation.

## Scope

V13.4.26 should:

- materialize hypothesis validation rows from FactorDataPanel and benchmark reports
- segment by volatility, ATR, trend strength, EMA50 distance, Bollinger position, volume expansion, and liquidity context
- compare candidate contexts against NoTrade, BuyHoldBTC, and BenchmarkBollingerRebound after costs
- record invalidated and deferred hypotheses explicitly
- preserve no-lookahead behavior for universe and factor inputs

## Non Goals

```text
no Freqtrade strategy implementation
no new backtest execution
no Dry-run
no Trade API
no Withdraw API
no API key
no account or position read
no order creation
no auto trading
```

## Minimum Promotion Gate

A research hypothesis should not move toward strategy design unless it has:

- sufficient coverage
- clear benchmark-relative improvement
- cost-adjusted evidence
- pair and month stability
- execution-reality notes
- clear invalidation rules

Passing this gate would still not be Dry-run approval. It would only justify a
future strategy design discussion.
