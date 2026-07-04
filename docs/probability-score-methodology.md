# Probability Score Methodology

The probability score table answers a historical research question:

```text
In similar historical conditions, how often did price reach the TP threshold before the SL threshold?
```

It does not answer whether a user should trade now.

## Sample Construction

Each sample is built from:

```text
snapshotDate + selected pair + current 1h candle
```

The pair must be present in the V13.4.13 historical dynamic universe for that
snapshot date. The candle and indicators come from local public OHLCV files.

## Feature Buckets

V13.4.14 groups samples by:

```text
regimeCandidate
liquidityBucket
volatilityBucket
rsiBucket
emaDistanceBucket
bbPositionBucket
btcState
```

Missing values are not invented. They become `unavailable` or `unknown`.

## Score Table Metrics

Each bucket row includes:

```text
sampleCount
hitTpBeforeSlProbability
hitSlBeforeTpProbability
averageMfePct
averageMaePct
averageReturnPct
profitFactor
expectancy
confidenceLevel
decision
```

The first implementation uses the 12-bar label as the primary aggregation
window. Each sample still stores labels for 8, 12, and 24 bars.

## Conservative Gate

The table uses these research thresholds:

```text
sampleCount >= 50
hitTpBeforeSlProbability >= 0.45
profitFactor >= 1.2
expectancy > 0
```

Rows that do not satisfy the threshold remain:

```text
decision = observe_only
```

Rows with insufficient samples are:

```text
confidenceLevel = insufficient_sample
```

This table cannot approve Dry-run or live trading.

