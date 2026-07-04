# Shadow Trading Design

Shadow Trading is the next research layer after V13.4.11. V13.4.11 only defines
the schema; it does not start polling, execute orders, or run Dry-run.

## Purpose

Shadow Trading records what would have happened after a research signal without
placing any order. It is used to measure whether backtest assumptions survive
live market conditions such as spread, liquidity, slippage, and path dependency.

## V13.4.11 Schemas

```text
ShadowSignal
ShadowExecutionSnapshot
ShadowOutcome
```

## ShadowSignal

Captures the research signal at the time it appears:

```text
signalId
strategyId
symbol
timeframe
signalTime
theoreticalEntryPrice
stopLossPrice
takeProfitPrice
positionNotional
liquidityGateResult
liveFeasibilityScore
```

## ShadowExecutionSnapshot

Captures public market execution context at signal time:

```text
bidPrice
askPrice
midPrice
spreadPct
orderbookDepthTop5
orderbookDepthTop10
quoteVolume1h
quoteVolume24h
estimatedSlippagePct
```

## ShadowOutcome

Captures follow-up research outcomes:

```text
wouldHitStop
wouldHitTakeProfit
maxFavorableExcursionPct
maxAdverseExcursionPct
followUpPrices
outcomeNotes
```

## Follow-Up Windows

Suggested windows:

```text
1m
5m
15m
1h
4h
24h
```

## Safety Boundary

Shadow Trading is observation only. It must not create orders, cancel orders,
read account balances, read positions, or trigger automatic trading.

