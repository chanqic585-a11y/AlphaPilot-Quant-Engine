# AlphaPilot V13.4.28 Data Coverage Repair Report

Status: completed_with_unresolved_gaps

V13.4.28 attempted to repair local public OHLCV coverage. It did not implement
a strategy, run a backtest, enter Dry-run, call private exchange APIs, read
accounts, create orders, or auto trade.

## Repair Command

```powershell
powershell -ExecutionPolicy Bypass -File scripts/download_data.ps1 -UseTop30 -Timeframes "1h,4h" -Timerange "20260101-" -Prepend -Run
```

## Pre-Repair Summary

- status: warning
- pairCount: 30
- pairTimeframeCount: 60
- missingFileCount: 4
- warningCount: 1
- invalidCount: 0

## Post-Repair Summary

- status: warning
- pairCount: 30
- pairTimeframeCount: 60
- missingFileCount: 4
- warningCount: 1
- invalidCount: 0

## Missing Pair/Timeframes From Baseline

- FET/USDT:USDT 1h: Missing local 1h futures OHLCV file. -> user_data/data/okx/futures/FET_USDT_USDT-1h-futures.feather
- FET/USDT:USDT 4h: Missing local 4h futures OHLCV file. -> user_data/data/okx/futures/FET_USDT_USDT-4h-futures.feather
- TON/USDT:USDT 1h: Missing local 1h futures OHLCV file. -> user_data/data/okx/futures/TON_USDT_USDT-1h-futures.feather
- TON/USDT:USDT 4h: Missing local 4h futures OHLCV file. -> user_data/data/okx/futures/TON_USDT_USDT-4h-futures.feather

## Coverage Gaps

- FET/USDT:USDT 1h: missing_file -> unresolved (Missing local 1h futures OHLCV file.)
- FET/USDT:USDT 4h: missing_file -> unresolved (Missing local 4h futures OHLCV file.)
- ORDI/USDT:USDT 4h: warning -> unresolved (Extreme close-to-close returns detected: 1.; quoteVolume is not present in raw OHLCV; research layers estimate it when needed.)
- TON/USDT:USDT 1h: missing_file -> unresolved (Missing local 1h futures OHLCV file.)
- TON/USDT:USDT 4h: missing_file -> unresolved (Missing local 4h futures OHLCV file.)

## Conclusion

The repair attempt completed, but the same missing local OHLCV gaps remain.

Warnings:

- Missing local OHLCV files remain after the public download repair attempt.
- The affected symbols may be unavailable in the configured OKX futures market universe.
- 4 pair/timeframe files are missing locally.
