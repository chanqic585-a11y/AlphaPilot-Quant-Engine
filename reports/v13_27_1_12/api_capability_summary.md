# V13.27.1.12 Public Data Capability Audit

Checked at: `2026-07-16T00:53:54Z`

Only public market-data sources are listed. Candidate availability does not count as formal evidence until a probe and completeness audit pass.

| Exchange | Data type | Endpoint or archive | Historical completeness | PIT semantics | Probe |
| --- | --- | --- | --- | --- | --- |
| OKX | perpetual_ohlcv | GET /api/v5/market/history-candles (SWAP) | candidate_unverified | event_history_unverified | not_run |
| OKX | spot_ohlcv | GET /api/v5/market/history-candles (SPOT) | candidate_unverified | event_history_unverified | not_run |
| OKX | ohlcv | GET /api/v5/market/history-candles | candidate_unverified | event_history_unverified | not_run |
| OKX | ohlcv_bulk | Historical Market Data / Candlestick download | candidate_unverified | event_history_unverified | not_run |
| OKX | funding | Historical Market Data / Funding rate download | candidate_unverified | event_history_unverified | not_run |
| OKX | open_interest | GET /api/v5/public/open-interest | current_only | current_snapshot_only | not_run |
| OKX | liquidation | GET /api/v5/public/liquidation-orders | insufficient_history | event_history_unverified | not_run |
| OKX | instrument_lifecycle | GET /api/v5/public/instruments | current_only | current_snapshot_only | not_run |
| OKX | instrument_history | GET /api/v5/public/instruments | current_only | current_snapshot_only | not_run |
| OKX | listing_delisting | GET /api/v5/public/instruments | current_only | current_snapshot_only | not_run |
| OKX | trading_state | GET /api/v5/public/instruments | current_only | current_snapshot_only | not_run |
| OKX | volume_24h_history | GET /api/v5/market/tickers | current_only | current_snapshot_only | not_run |
| OKX | orderbook_snapshots | GET /api/v5/market/books | current_only | current_snapshot_only | not_run |
| Binance | ohlcv | GET /fapi/v1/continuousKlines | candidate_unverified | event_history_unverified | not_run |
| Binance | funding | GET /fapi/v1/fundingRate | candidate_unverified | event_history_unverified | not_run |
| Binance | open_interest | GET /futures/data/openInterestHist | insufficient_history | event_history_unverified | not_run |
| Binance | basis | GET /futures/data/basis | insufficient_history | event_history_unverified | not_run |
| Binance | instrument_lifecycle | GET /fapi/v1/exchangeInfo | current_only | current_snapshot_only | not_run |

Formal source chains must be complete on one exchange; cross-exchange core-field splicing is prohibited.
