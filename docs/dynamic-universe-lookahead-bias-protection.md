# Dynamic Universe Lookahead Bias Protection

The most important V13.4.13 rule is:

```text
Each snapshot can only use candles that closed before snapshotDate.
```

## Why It Matters

Using today's hot coins to backtest past dates creates selection bias. A
strategy may look strong only because the universe was chosen with information
that did not exist at the historical decision time.

## Builder Rules

V13.4.13 enforces:

```text
1. Snapshot timestamp is snapshotDate 00:00 UTC.
2. All factor windows use candles with date < snapshotDate 00:00 UTC.
3. 24h factors use only the previous 24 closed 1h candles.
4. 3d factors use only the previous 72 closed 1h candles.
5. Volume expansion compares previous 24h volume to earlier historical volume.
6. Pairs with insufficient history are excluded instead of filled.
7. Ranking is recalculated per snapshot from the cross section visible at that time.
```

## Not Allowed

```text
using full dataframe averages across future dates
using today's Top30 hot list as historical selection
ranking by future returns
using future volume to decide past pair inclusion
filling missing OHLCV with optimistic values
```

## Backtest Integration

Future strategy versions should call:

```text
get_pairs_for_timestamp(timestamp)
```

and use the returned pair list for that historical point only.

## Safety Boundary

Lookahead bias protection is a research data rule. It does not approve Dry-run
or live trading.

