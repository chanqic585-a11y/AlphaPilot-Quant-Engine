# Historical Dynamic Universe Builder

`Historical Dynamic Universe Builder` produces point-in-time universe snapshots
for future backtests.

## Default Configuration

```text
market = okx_usdt_swap
candidateMode = top30
timeframeForRanking = 1h
refreshFrequency = daily
maxPairs = 10
timerange = 20260101-
warmupDays = 30
minimumHistoryDays = 30
idealHistoryDays = 90
```

V13.4.13 starts from the fixed Top30 supported-pair list because earlier project
versions already downloaded local 1h futures data for that universe. Future
versions can expand the candidate source to a full exchange futures universe.

## Factors

Liquidity factors:

```text
quoteVolume24h
quoteVolume3d
volumeStability3d
missingCandleRate
```

Activity factors:

```text
absReturn24h
absReturn3d
volatility24h
volatility3d
volumeExpansion24h
volumeExpansion3d
```

Risk filters:

```text
missingCandleRate > 5%
quoteVolume24h <= 0
quoteVolume3d <= 0
history < minimumHistoryDays
missing OHLCV file
```

## Future Interface

The schema exposes helper functions for future backtest integration:

```text
find_snapshot_for_timestamp(...)
get_pairs_for_timestamp(...)
get_pair_scores_for_date(...)
```

These helpers allow future strategy code to retrieve the correct historical
pair set without using future data.

## Blocked Builds

If no usable OHLCV exists, the builder writes a blocked report. It must not
claim success and the version should not be tagged until data availability is
fixed.

## Feather Dependency

Local Freqtrade data is usually stored as `.feather`. Reading that format
requires `pyarrow` in the Python runtime. If `pyarrow` or another reader
dependency is missing, the builder records the read failure and blocks the
affected pair instead of fabricating OHLCV data.
