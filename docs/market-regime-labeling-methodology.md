# Market Regime Labeling Methodology

V13.4.27 labels market regime from local BTC/USDT:USDT 4h OHLCV.

The labels are research context only. They are not trading signals and do not
trigger strategy entries.

## Inputs

```text
pair = BTC/USDT:USDT
timeframe = 4h
timerange = 20260101-
source = local public OKX futures OHLCV
```

## Indicators

The labeler computes:

- EMA20
- EMA50
- EMA200
- 3-day BTC return
- 7-day BTC return
- rolling 4h volatility

## Labels

The labeler can assign multiple labels per candle:

```text
bull
bear
sideways
high_volatility
crash
recovery
unknown
```

Examples:

- `bull`: close above EMA200 and EMA20 above EMA50
- `bear`: close below EMA200 and EMA20 below EMA50
- `sideways`: EMA20 and EMA50 are close together
- `high_volatility`: rolling volatility is in the top local quintile
- `crash`: 3-day return is at or below -10%
- `recovery`: 7-day return is at or above +10% and price is above EMA20

## BTC Sanity Points

The report checks local BTC prices near:

```text
2025-10-01
2026-01-01
2026-04-01
2026-06-01
2026-07-01
```

If no candle exists near a checkpoint, the report writes a warning instead of
fetching external data.

## Limitation

Existing strategy reports before V13.4.27 were not tagged per trade by regime.
V13.4.27 therefore performs sample-level regime interpretation. Future
backtest and factor reports should include regime tags directly.
