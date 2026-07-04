# Market Regime Router Design

`MarketRegimeRouterV01` assigns each pair to a market state before any strategy
module is considered.

## First-Version Regimes

```text
trend
mean_reversion
avoid
```

Reserved for later:

```text
breakout
```

## Trend Regime Draft

Trend regime may require:

```text
4h close > EMA200
4h EMA20 > EMA50
1h close > EMA50
BTC 1h / 4h not weak
trend strength threshold met
```

Trend regime routes to:

```text
TrendContinuationModuleV01
```

## Mean Reversion Regime Draft

Mean reversion regime may require:

```text
4h not strong bear
short-term price deviation from EMA20 or Bollinger middle
short-term RSI low
moderate volatility
BTC not crashing
```

Mean reversion regime routes to:

```text
MeanReversionModuleV01
```

## Avoid Regime

Avoid should trigger on:

```text
BTC crash
4h strong bear
spread too wide
insufficient liquidity
abnormal volume
major data gap
overextended price move
```

Avoid means:

```text
do not generate a backtest trade candidate
```

## Safety Boundary

The router is a classification layer. It does not create orders and does not
approve Dry-run or live trading.

