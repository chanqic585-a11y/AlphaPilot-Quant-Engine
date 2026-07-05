# Market Data Source Registry

V13.4.28 adds a descriptive public data source registry in:

```text
alphapilot/data_expansion/data_source_registry.py
```

The registry does not create clients or fetch data. It records source metadata
for future public data engineering.

## Registered Sources

```text
okx_public_ohlcv
okx_public_funding_rate
okx_public_open_interest
okx_public_ticker
okx_public_orderbook_snapshot
local_freqtrade_ohlcv
```

Each source records:

```text
sourceId
exchange
dataType
requiresApiKey
usesPrivateEndpoint
supportsHistorical
supportsRealtime
status
notes
```

V13.4.28 keeps `requiresApiKey=false` and `usesPrivateEndpoint=false` for all
registered sources.

## Source Status

The local Freqtrade OHLCV cache is active. Funding, open interest, ticker, and
orderbook snapshot sources are planned but not collected in V13.4.28.

## Safety Boundary

The registry is research metadata only. It does not use API keys, private
exchange endpoints, account data, order data, Trade API, Withdraw API, or auto
trading.
