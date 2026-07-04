# Probability Label Definition

V13.4.14 labels candidate samples by looking forward from the current candle.
Labels are for historical evaluation only.

## Windows

Default windows:

```text
8 bars
12 bars
24 bars
```

For the current 1h timeframe this means:

```text
8h
12h
24h
```

## TP / SL

Default thresholds:

```text
TP = +5%
SL = -2.5%
```

For each window, the label builder records:

```text
hitTpBeforeSl
hitSlBeforeTp
noHit
mfePct
maePct
futureReturnAtWindowEnd
barsToTp
barsToSl
outcomeReturnPct
```

If TP and SL occur inside the same candle, V13.4.14 uses a conservative
ordering and treats SL as first.

## No-Lookahead Rule

Feature values are point-in-time:

```text
current candle + prior candles only
```

Forward labels are allowed to inspect future candles, but only as labels:

```text
future candles -> labels only
labels -> never written back into feature buckets
```

Missing current candles or incomplete future windows are counted as
`insufficientDataCount`; the builder does not fill missing prices or create fake
future candles.

## Safety Boundary

Labels are not trade commands. V13.4.14 does not generate orders, run a
strategy backtest, enter Dry-run, use API keys, call Trade API or Withdraw API,
read accounts, read positions, or auto trade.

