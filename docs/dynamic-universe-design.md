# Dynamic Universe Design

`DynamicUniverseV01` selects a small, current, liquid, research-ready universe
instead of applying one fixed strategy to a broad Top30 list.

## Goal

The universe builder should answer:

```text
Which OKX USDT swap pairs were active, liquid, and structurally usable at this
point in history?
```

It must not answer:

```text
Which coin should be bought now?
```

## Base Filters

The first version should require:

```text
OKX USDT perpetual swap
non-stablecoin
not delisting
at least 90 days of historical candles
low missing candle rate
24h quote volume above threshold
3d average quote volume above threshold
bid/ask spread below threshold
not in abnormal risk blacklist
```

## Rank Factors

Candidates are ranked by:

```text
24h quote volume
3d quote volume
24h absolute return
3d absolute return
3d volatility
volume expansion
liquidity stability
```

## Selection Size

Recommended first version:

```text
Top10
```

Maximum first-version experiment:

```text
Top15
```

Static Top30 remains useful only as a baseline comparison.

## Historical Snapshot Rule

Backtests must use historical snapshots:

```text
At each historical date, select pairs using only data visible before or at that
date.
```

Never use today's hot coin list to backtest the past.

## Snapshot Shape

```json
{
  "snapshotDate": "2026-01-05",
  "lookbackWindow": "3d",
  "selectedPairs": ["BTC/USDT:USDT", "ETH/USDT:USDT"],
  "rankFactors": {},
  "excludedPairs": [],
  "warnings": []
}
```

## Safety Boundary

Dynamic Universe is a research filter. It does not create orders, read accounts,
or approve live trading.

