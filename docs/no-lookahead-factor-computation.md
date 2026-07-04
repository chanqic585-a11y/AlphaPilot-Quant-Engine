# No-Lookahead Factor Computation

V13.4.21 introduces point-in-time factor computation rules.

## Rules

1. Rolling features use only current and historical rows within each pair.
2. Cross-sectional ranks use only pairs sharing the same timestamp.
3. BTC relative strength context is matched by exact timestamp.
4. Forward labels are not computed in the factor panel.
5. Trade outcomes and backtest results never flow into factor values.
6. Missing values remain null instead of being filled from the future.
7. Dynamic universe membership is read from historical snapshots when enabled.

## Examples

Allowed:

```text
ts_return(close, 12) at timestamp T uses close(T) and close(T-12)
rank(quoteVolume) at timestamp T ranks pairs available at timestamp T
```

Not allowed:

```text
using future return labels in a factor value
using future universe membership for an earlier timestamp
backfilling missing factor values from later candles
promoting factor rows directly into strategy entries
```

## V13.4.21 Scope

The implementation builds research data only. It does not run a backtest,
enter Dry-run, create orders, or auto trade.
