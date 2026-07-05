# NoTrade and BuyHoldBTC Baseline Importance

AlphaPilot must compare every strategy hypothesis against two simple baselines:

```text
NoTrade
BuyHoldBTC
```

## NoTrade

NoTrade matters because a strategy can be worse than not trading. If active
rules create turnover, fees, slippage, and drawdown without adding enough edge,
the correct research conclusion is to do nothing.

In V13.4.24, every active benchmark underperformed NoTrade.

## BuyHoldBTC

BuyHoldBTC matters because passive BTC exposure can be a better reference than a
frequent altcoin rotation strategy. If a strategy cannot beat a simple BTC hold
baseline after costs and drawdown, it should not be promoted.

In V13.4.24, every active benchmark underperformed BuyHoldBTC.

## Future Rule

Future strategy research must compare against:

```text
NoTrade
BuyHoldBTC
BenchmarkBollingerRebound
```

Passing one baseline is not enough. AlphaPilot needs robust evidence across
return, drawdown, cost sensitivity, pair stability, and month stability.
