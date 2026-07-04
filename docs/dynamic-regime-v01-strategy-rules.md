# Dynamic Regime V0.1 Strategy Rules

`AlphaPilotDynamicRegimeV01` is a research backtest strategy skeleton for the
new dynamic universe and regime-router mainline.

## Timeframes

```text
primary: 1h
higher timeframe: 4h
BTC informative: 1h and 4h
```

## Core Indicators

1h:

```text
EMA20
EMA50
EMA200
RSI14
MACD histogram
Bollinger Bands
ATR14
volumeRatio
```

4h:

```text
EMA20
EMA50
EMA200
```

BTC:

```text
BTC 1h return_3
BTC 4h close vs EMA200
```

## Regime Router

The router outputs:

```text
trend
mean_reversion
avoid
```

Trend requires pair 4h structure, pair 1h structure, and BTC safety context.
Mean reversion requires BTC not crashing, low or recovering RSI, and price near
the lower Bollinger area. Avoid is used when key data is missing, BTC is
crashing, ATR is extreme, or the 4h structure is strongly weak.

## Entry Gates

Every entry candidate must pass:

```text
dynamic universe
regime router
module-specific conditions
probability score
liquidity gate
data completeness
```

Probability score defaults:

```text
sampleCount >= 50
profitFactor >= 1.2
expectancy > 0
decision = research_candidate
```

If the matched probability bucket is missing or insufficient, the final entry is
blocked.

## Exit Logic

The strategy uses:

```text
stoploss = -2.5%
minimal_roi = 4%
```

`custom_exit` distinguishes entry tags:

- trend candidates use a 12h non-profitable time stop and profit-only MACD
  weakness exit.
- mean-reversion candidates can exit at 2.5% or use an 8h non-profitable time
  stop.

## Research Status

This strategy is not Dry-run approved and not live approved. V13.4.15 does not
run the strategy. V13.4.16 is responsible for smoke backtest validation.

