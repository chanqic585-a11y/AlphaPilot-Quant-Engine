# V13.4.2 Signal Audit Summary

## Conclusion

V13.4.2 adds signal audit instrumentation and does not tune strategy parameters or enter Dry-run.

## Overall

- Candles evaluated: 26496
- Base candidate count: 26496
- Final entry count: 305
- Actual trade count: 230
- Conversion rate: 1.1511%
- Filter effectiveness available: True

## Skip Reasons

- data_missing: 0 (0.0%)
- btc_crash_filter: 315 (1.1889%)
- weak_4h_trend: 11926 (45.0106%)
- rsi_out_of_range: 7062 (26.6531%)
- volume_ratio_too_low: 6243 (23.562%)
- macd_not_improving: 635 (2.3966%)
- ema20_reclaim_failed: 10 (0.0377%)
- price_too_extended: 0 (0.0%)
- entry_signal_passed: 305 (1.1511%)
- unknown: 0 (0.0%)

## Filter Stats

- data_ready: pass=26496, fail=0, primaryBlocks=0
- btc_crash_filter: pass=26181, fail=315, primaryBlocks=315
- 4h_trend_filter: pass=14344, fail=12152, primaryBlocks=11926
- rsi_filter: pass=13574, fail=12922, primaryBlocks=7062
- volume_filter: pass=4713, fail=21783, primaryBlocks=6243
- macd_filter: pass=13273, fail=13223, primaryBlocks=635
- ema20_reclaim_filter: pass=23105, fail=3391, primaryBlocks=10
- no_chase_filter: pass=25054, fail=1442, primaryBlocks=0

## Pair Breakdown

- BTC/USDT:USDT: candles=8832, base=8832, final=91, trades=72
- ETH/USDT:USDT: candles=8832, base=8832, final=79, trades=59
- SOL/USDT:USDT: candles=8832, base=8832, final=135, trades=99

## Main Findings

- Most common skip reason: weak_4h_trend (11926)
- Least primary-blocking filter: no_chase_filter (0)
- V13.4.2 cannot approve Dry-run; it only prepares evidence for V13.4.3 strategy design.

## Safety

This audit reads local backtest and OHLCV files only. It does not use API keys, call Trade API or Withdraw API, read accounts, create orders, execute Dry-run, or auto trade.
