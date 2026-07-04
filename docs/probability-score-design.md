# Probability Score Design

`ProbabilityScoreV01` asks whether similar historical conditions had a
statistical edge before a candidate is allowed into backtest trading logic.

## Why It Exists

Earlier strategies passed indicator conditions but failed expanded validation.
Probability Score prevents a signal from relying only on indicator alignment.

## Label Windows

Each candidate should be labeled over:

```text
future 8 candles
future 12 candles
future 24 candles
```

Labels:

```text
hit take profit before stop loss
hit stop loss before take profit
MFE
MAE
final return
holding time
```

## Condition Buckets

Probability should be grouped by:

```text
regime
pair liquidity bucket
volume rank bucket
volatility bucket
RSI bucket
distance to EMA20 bucket
distance to Bollinger bucket
BTC state
time of day
day of week
```

## Initial Pass Conditions

```text
sampleCount >= 50
hitTpBeforeSlProbability >= 0.45
profitFactor >= 1.2
expectancy > 0
```

If sample count is too low:

```text
observe_only
```

## Safety Boundary

Probability Score is not a profit prediction and not trading advice. It is a
research gate for backtest candidates only.

