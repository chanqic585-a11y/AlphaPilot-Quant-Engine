# AlphaPilot V13.5.15 Multi-Exchange Data Coverage

This is a public historical data coverage report. It is not a strategy change, Dry-run approval, or live-trading approval.

## Coverage

- Expected files: 600
- Available files: 73
- Available percentage: 12.1667%
- Core BTC/ETH/SOL coverage: 18 / 18 (100.0%)

## By Exchange

- okx: 61 / 200 files, 39 pairs, latest=2026-07-05T16:00:00+00:00
  - 4h: 38 / 100 files, avgRows=9468.18
  - 1d: 23 / 100 files, avgRows=1876.43
- binance: 6 / 200 files, 3 pairs, latest=2026-07-05T16:00:00+00:00
  - 4h: 3 / 100 files, avgRows=13752.67
  - 1d: 3 / 100 files, avgRows=2291.33
- bybit: 6 / 200 files, 3 pairs, latest=2026-07-05T16:00:00+00:00
  - 4h: 3 / 100 files, avgRows=11914.33
  - 1d: 3 / 100 files, avgRows=1985.0

## Decision

- multiExchangeCoreDataReady: True
- top100OkxExpansionPartial: True
- top100FullMultiExchangeReady: False
- readyToRunMultiExchangeStrategyRobustness: False
- nextAction: build_exchange_aware_feature_panel_and_core_triad_replay

## Runtime Notes

- OKX Top100 2020-2026 expansion can be too heavy for one uninterrupted command; partial public files are reported instead of fabricated.
- Binance and Bybit core BTC/ETH/SOL public OHLCV samples were added for exchange-path validation.
- The current strategy feature panel remains OKX-centered; multi-exchange data must be wired deliberately before robustness claims.

## Safety Boundary

- No Trade API.
- No Withdraw API.
- No API key storage.
- No real account reads.
- No real position reads.
- No order creation.
- No automatic trading.
