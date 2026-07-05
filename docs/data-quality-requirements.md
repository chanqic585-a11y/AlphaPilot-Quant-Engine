# Public Market Data Quality Requirements

V13.4.28 requires missing public market data to stay visible. Missing values
must not be converted into favorable assumptions.

## OHLCV Coverage

Local OHLCV coverage is checked with:

```powershell
python -m alphapilot.reports.generate_market_regime_data_integrity_review
```

For V13.4.28 post-repair outputs, use versioned output paths so V13.4.27
baseline files are preserved.

## Expansion Data Rules

Future funding, open-interest, orderbook, liquidation, and regime-proxy records
must follow these rules:

- keep UTC timestamps
- preserve source IDs
- preserve source units
- store null when public data is unavailable
- record warnings for unavailable or partial data
- reject private endpoint sources
- reject API-key-required sources
- never fabricate missing context fields

## Reporting Rules

Reports must include:

- coverage status
- missing pair/timeframe records
- warning records
- source registry state
- safety boundary flags
- next-step recommendation

## Safety Boundary

Data quality reports are research artifacts only. They do not run strategies,
execute backtests, enter Dry-run, use Trade API, use Withdraw API, read
accounts, read positions, create orders, or auto trade.
