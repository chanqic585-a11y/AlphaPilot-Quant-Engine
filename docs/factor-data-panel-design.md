# Factor Data Panel Design

The FactorDataPanel is the first AlphaPilot research surface for organizing
market, universe, regime, liquidity, and return fields into a time by pair
panel.

It is a schema in V13.4.20 only. It does not read OHLCV, compute factors, or
write strategy entries.

## Primary Index

```text
timestamp
pair
```

## V01 Fields

```text
timestamp
pair
open
high
low
close
volume
quoteVolume
vwap
returns_1
returns_3
returns_6
returns_12
marketReturn
btcReturn
universeMember
regimeLabel
liquidityBucket
volatilityBucket
```

## Future Fields

```text
fundingRate
openInterest
longShortRatio
orderbookSpread
orderbookDepth
newsSentiment
macroEventFlag
```

## Design Principle

The panel exists so AlphaPilot can evaluate factors before creating strategy
hypotheses. It is not a live signal feed.
