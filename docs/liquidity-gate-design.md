# Liquidity Gate Design

The Liquidity Gate is a research-only check that estimates whether a theoretical
position has enough public liquidity context before it can be considered for
future shadow trading research.

It never places orders and never calls exchange private endpoints.

## Inputs

```text
symbol
timestamp
marketType
positionNotional
lastPrice
quoteVolume24h
quoteVolume1h
bidAskSpreadPct
orderbookDepthTop5
orderbookDepthTop10
maxPositionToVolumePct
maxPositionToDepthPct
```

## Default Rules

```text
missing quoteVolume1h prevents approval
missing quoteVolume1h and missing orderbook depth returns insufficient_liquidity_data
positionNotional > quoteVolume1h * 0.001 is rejected or needs review
bidAskSpreadPct > 0.0008 is rejected or needs review
positionNotional > orderbookDepthTop5 * 0.10 is rejected
```

The default ratios are intentionally conservative placeholders. Future versions
can calibrate them with shadow trading records and real public orderbook depth.

## Decisions

```text
approved_for_shadow_research
needs_review
rejected_by_liquidity_gate
insufficient_liquidity_data
```

Approval only means the candidate has enough public liquidity context for
research. It is not permission to trade.

## Missing Data Policy

Missing liquidity data is not filled with optimistic defaults. If core inputs
are missing, the result is `insufficient_liquidity_data` or `needs_review`.

## Safety Boundary

The Liquidity Gate uses public market data fields only. It does not store API
keys, does not read accounts or positions, and does not create orders.

