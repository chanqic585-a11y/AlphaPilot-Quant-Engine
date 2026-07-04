# V13.4.13 Historical Dynamic Universe Summary

## Build Status

- status: success
- timerange: 20260101-
- refreshFrequency: daily
- maxPairs: 10
- candidateMode: top30
- snapshotCount: 155
- candidatePairsCount: 30
- averageSelectedPairs: 10.0

## Data Availability

- supportedPairs: 28
- missingDataPairs: TON/USDT:USDT, FET/USDT:USDT
- insufficientDataPairs: none
- pairsWithEstimatedQuoteVolume: 28
- pairsWithHighMissingRate: none

## Top Most Selected Pairs

- ETH/USDT:USDT: 155
- SOL/USDT:USDT: 155
- DOGE/USDT:USDT: 153
- BTC/USDT:USDT: 152
- PEPE/USDT:USDT: 144
- SUI/USDT:USDT: 131
- XRP/USDT:USDT: 125
- FIL/USDT:USDT: 101
- ADA/USDT:USDT: 99
- NEAR/USDT:USDT: 61
- AAVE/USDT:USDT: 51
- BCH/USDT:USDT: 41
- ORDI/USDT:USDT: 28
- LINK/USDT:USDT: 26
- UNI/USDT:USDT: 25

## Most Excluded Pairs

- TON/USDT:USDT: 155
- FET/USDT:USDT: 155

## Lookahead Bias Protection

- Each snapshot uses only candles with date < snapshotDate 00:00 UTC.
- Ranking factors are recalculated per snapshot and never use future candles.
- Rolling windows are sliced before snapshotDate and cannot cross into future dates.
- Pairs with insufficient history or missing data are excluded instead of filled with fake values.
- The builder starts after warmupDays to avoid ranking from shallow history.

## Output Files

- snapshots: reports\v13_4_13_dynamic_universe_snapshots.json
- sampleSnapshots: reports\v13_4_13_dynamic_universe_sample_snapshots.json
- buildReport: reports/v13_4_13_dynamic_universe_build_report.json

## Warnings

- TON/USDT:USDT: missing_ohlcv_file
- FET/USDT:USDT: missing_ohlcv_file

## Safety

This builder reads local public OHLCV files only. It does not run a strategy backtest, enter Dry-run, use API keys, call Trade API or Withdraw API, read accounts, read positions, create orders, or auto trade.

Next step: V13.4.14 - Probability Score Dataset and Label Builder
