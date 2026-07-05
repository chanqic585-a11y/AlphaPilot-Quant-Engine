# AlphaPilot V13.4.28 Market Data Coverage and Expansion

Status: completed_with_unresolved_gaps

V13.4.28 repairs local OHLCV coverage where possible and adds a public-data
expansion skeleton for future research inputs. It does not implement strategy
logic, run backtests, enter Dry-run, call private APIs, read accounts, create
orders, or auto trade.

## Coverage Repair

- preRepairMissingFileCount: 4
- postRepairMissingFileCount: 4
- postRepairWarningCount: 1
- conclusion: The repair attempt completed, but the same missing local OHLCV gaps remain.

## Public Data Expansion Schemas

- Funding Rate: schema_only_not_collected
- Open Interest: schema_only_not_collected
- Orderbook Spread Proxy: schema_only_not_collected
- Liquidation: schema_only_not_collected
- Market Regime Proxy: schema_only_not_collected

## Data Source Registry

- okx_public_ohlcv: apiKey=False private=False status=active_local_freqtrade_path
- okx_public_funding_rate: apiKey=False private=False status=planned_not_collected
- okx_public_open_interest: apiKey=False private=False status=planned_not_collected
- okx_public_ticker: apiKey=False private=False status=planned_not_collected
- okx_public_orderbook_snapshot: apiKey=False private=False status=planned_not_collected
- local_freqtrade_ohlcv: apiKey=False private=False status=active_local_cache

## Next Step Recommendation

- Resolve remaining local OHLCV coverage gaps before approving V13.4.29 strategy specification.
- Review whether unresolved pairs are unavailable on OKX futures or need universe replacement/mapping.
- Keep V13.4.29 Bear Regime Short Strategy Specification blocked until coverage policy is explicit.

## Safety Boundary

- dryRunApproved: False
- liveTradingApproved: False
- no Trade API
- no Withdraw API
- no API key storage
- no account or position reads
- no order creation
- no auto trading

Warnings:

- Missing local OHLCV files remain after the public download repair attempt.
- The affected symbols may be unavailable in the configured OKX futures market universe.
- 4 pair/timeframe files are missing locally.
- Public data expansion is schema-only in V13.4.28; no new external collector is active.
