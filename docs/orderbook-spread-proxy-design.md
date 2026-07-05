# Orderbook Spread Proxy Design

The orderbook spread proxy is a future public liquidity-context input. V13.4.28
only registers the schema; it does not poll public orderbooks.

## Intended Use

The first proxy is intentionally simple:

```text
spreadBps = (bestAsk - bestBid) / midPrice * 10000
```

It can later support liquidity gating, slippage assumptions, and execution
reality checks. It is not a live execution module.

## Required Fields

```text
exchange
pair
marketType
timestamp
bestBid
bestAsk
spreadBps
depthSampleAvailable
sourceId
qualityStatus
warnings
```

`spreadBps` must remain null when bid/ask are unavailable.

## Quality Requirements

- bestAsk must be greater than or equal to bestBid when both exist
- public snapshot timestamps must be preserved
- missing snapshots must be marked unavailable
- no private endpoint or API key source is allowed

## Safety Boundary

The spread proxy is research context only. It does not create orders, place
orders, cancel orders, read accounts, or auto trade.
