# AlphaPilot V13.7.40 Short-Cycle Parameter Search

This report searches short-cycle public-OHLCV research candidates with fixed 2R exits.
It is not exchange dry-run, not live trading, not an order, and not trading advice.

## Summary

- status: completed
- candidateCount: 608
- approvedCount: 0
- selectedCount: 5
- approvedSelectedCount: 0
- targetR: 2.0
- feeRate: 0.0005
- slippageRate: 0.0005
- timerange: 20260101-

## Data Coverage

- 15m: 5 pairs
- 30m: 5 pairs
- 1h: 5 pairs

## Selected Candidates

| Candidate | TF | Family | Direction | Approved | Trades | Pairs | Win % | PF | Exp R | Test PF | Test Exp R | DD R | Failed Checks |
| --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 1h 空头上影拒绝 ATR1.6 | 1h | short_rejection | short | False | 5 | 3 | 40.0 | 0.4982 | -0.221 | 1.0403 | 0.0142 | 1.1477 | total_trade_count_lt_100, test_trade_count_lt_20, pair_count_lt_8, total_profit_factor_lt_1_10, test_profit_factor_lt_1_05 |
| 1h 空头上影拒绝 ATR1.6 | 1h | short_rejection | short | False | 5 | 3 | 40.0 | 0.4982 | -0.221 | 1.0403 | 0.0142 | 1.1477 | total_trade_count_lt_100, test_trade_count_lt_20, pair_count_lt_8, total_profit_factor_lt_1_10, test_profit_factor_lt_1_05 |
| 1h 空头上影拒绝 ATR1.2 | 1h | short_rejection | short | False | 5 | 3 | 20.0 | 0.5699 | -0.2906 | 0.8825 | -0.0854 | 2.3058 | total_trade_count_lt_100, test_trade_count_lt_20, pair_count_lt_8, total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive |
| 1h 空头上影拒绝 ATR1.2 | 1h | short_rejection | short | False | 5 | 3 | 20.0 | 0.5699 | -0.2906 | 0.8825 | -0.0854 | 2.3058 | total_trade_count_lt_100, test_trade_count_lt_20, pair_count_lt_8, total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive |
| 1h 空头上影拒绝 ATR1.2 | 1h | short_rejection | short | False | 1 | 1 | 100.0 | -- | 1.9255 | -- | -- | 0.0 | total_trade_count_lt_100, test_trade_count_lt_20, pair_count_lt_8, total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive |

### 1h 空头上影拒绝 ATR1.6

- candidateId: `v13_7_40_1h_short_rejection_584`
- approved: False
- params: `{"upper_buffer": 0.003, "trend_tolerance": 1.0, "rsi_high": 62, "volume_min": 1.2, "stop_atr": 1.6, "max_hold": 12}`

#### Walk-Forward

| Split | Trades | Pairs | Win % | PF | Exp R | Total R | DD R |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| train | 2 | 2 | 0.0 | 0.0 | -0.5738 | -1.1477 | 1.1477 |
| validation | 0 | 0 | -- | -- | -- | 0.0 | 0.0 |
| test | 3 | 2 | 66.6667 | 1.0403 | 0.0142 | 0.0425 | 1.0546 |

#### Top Pair Breakdown

| Pair | Trades | Win % | PF | Exp R | Total R |
| --- | ---: | ---: | ---: | ---: | ---: |
| ARB/USDT:USDT | 2 | 100.0 | -- | 0.5486 | 1.0972 |
| ADA/USDT:USDT | 1 | 0.0 | 0.0 | -0.0546 | -0.0546 |
| APE/USDT:USDT | 2 | 0.0 | 0.0 | -1.0739 | -2.1478 |

### 1h 空头上影拒绝 ATR1.6

- candidateId: `v13_7_40_1h_short_rejection_600`
- approved: False
- params: `{"upper_buffer": 0.003, "trend_tolerance": 1.005, "rsi_high": 62, "volume_min": 1.2, "stop_atr": 1.6, "max_hold": 12}`

#### Walk-Forward

| Split | Trades | Pairs | Win % | PF | Exp R | Total R | DD R |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| train | 2 | 2 | 0.0 | 0.0 | -0.5738 | -1.1477 | 1.1477 |
| validation | 0 | 0 | -- | -- | -- | 0.0 | 0.0 |
| test | 3 | 2 | 66.6667 | 1.0403 | 0.0142 | 0.0425 | 1.0546 |

#### Top Pair Breakdown

| Pair | Trades | Win % | PF | Exp R | Total R |
| --- | ---: | ---: | ---: | ---: | ---: |
| ARB/USDT:USDT | 2 | 100.0 | -- | 0.5486 | 1.0972 |
| ADA/USDT:USDT | 1 | 0.0 | 0.0 | -0.0546 | -0.0546 |
| APE/USDT:USDT | 2 | 0.0 | 0.0 | -1.0739 | -2.1478 |

### 1h 空头上影拒绝 ATR1.2

- candidateId: `v13_7_40_1h_short_rejection_582`
- approved: False
- params: `{"upper_buffer": 0.003, "trend_tolerance": 1.0, "rsi_high": 62, "volume_min": 1.2, "stop_atr": 1.2, "max_hold": 12}`

#### Walk-Forward

| Split | Trades | Pairs | Win % | PF | Exp R | Total R | DD R |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| train | 2 | 2 | 0.0 | 0.0 | -0.5983 | -1.1966 | 1.1966 |
| validation | 0 | 0 | -- | -- | -- | 0.0 | 0.0 |
| test | 3 | 2 | 33.3333 | 0.8825 | -0.0854 | -0.2563 | 1.1092 |

#### Top Pair Breakdown

| Pair | Trades | Win % | PF | Exp R | Total R |
| --- | ---: | ---: | ---: | ---: | ---: |
| ARB/USDT:USDT | 2 | 50.0 | 1.7358 | 0.4081 | 0.8162 |
| ADA/USDT:USDT | 1 | 0.0 | 0.0 | -0.0727 | -0.0727 |
| APE/USDT:USDT | 2 | 0.0 | 0.0 | -1.0982 | -2.1963 |

### 1h 空头上影拒绝 ATR1.2

- candidateId: `v13_7_40_1h_short_rejection_598`
- approved: False
- params: `{"upper_buffer": 0.003, "trend_tolerance": 1.005, "rsi_high": 62, "volume_min": 1.2, "stop_atr": 1.2, "max_hold": 12}`

#### Walk-Forward

| Split | Trades | Pairs | Win % | PF | Exp R | Total R | DD R |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| train | 2 | 2 | 0.0 | 0.0 | -0.5983 | -1.1966 | 1.1966 |
| validation | 0 | 0 | -- | -- | -- | 0.0 | 0.0 |
| test | 3 | 2 | 33.3333 | 0.8825 | -0.0854 | -0.2563 | 1.1092 |

#### Top Pair Breakdown

| Pair | Trades | Win % | PF | Exp R | Total R |
| --- | ---: | ---: | ---: | ---: | ---: |
| ARB/USDT:USDT | 2 | 50.0 | 1.7358 | 0.4081 | 0.8162 |
| ADA/USDT:USDT | 1 | 0.0 | 0.0 | -0.0727 | -0.0727 |
| APE/USDT:USDT | 2 | 0.0 | 0.0 | -1.0982 | -2.1963 |

### 1h 空头上影拒绝 ATR1.2

- candidateId: `v13_7_40_1h_short_rejection_553`
- approved: False
- params: `{"upper_buffer": 0.0, "trend_tolerance": 1.0, "rsi_high": 70, "volume_min": 0.9, "stop_atr": 1.2, "max_hold": 8}`

#### Walk-Forward

| Split | Trades | Pairs | Win % | PF | Exp R | Total R | DD R |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| train | 1 | 1 | 100.0 | -- | 1.9255 | 1.9255 | 0.0 |
| validation | 0 | 0 | -- | -- | -- | 0.0 | 0.0 |
| test | 0 | 0 | -- | -- | -- | 0.0 | 0.0 |

#### Top Pair Breakdown

| Pair | Trades | Win % | PF | Exp R | Total R |
| --- | ---: | ---: | ---: | ---: | ---: |
| ARB/USDT:USDT | 1 | 100.0 | -- | 1.9255 | 1.9255 |

## Top 25 Candidates

| Candidate | TF | Family | Direction | Approved | Trades | Pairs | Win % | PF | Exp R | Test PF | Test Exp R | DD R | Failed Checks |
| --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 1h 空头上影拒绝 ATR1.6 | 1h | short_rejection | short | False | 5 | 3 | 40.0 | 0.4982 | -0.221 | 1.0403 | 0.0142 | 1.1477 | total_trade_count_lt_100, test_trade_count_lt_20, pair_count_lt_8, total_profit_factor_lt_1_10, test_profit_factor_lt_1_05 |
| 1h 空头上影拒绝 ATR1.6 | 1h | short_rejection | short | False | 5 | 3 | 40.0 | 0.4982 | -0.221 | 1.0403 | 0.0142 | 1.1477 | total_trade_count_lt_100, test_trade_count_lt_20, pair_count_lt_8, total_profit_factor_lt_1_10, test_profit_factor_lt_1_05 |
| 1h 空头上影拒绝 ATR1.2 | 1h | short_rejection | short | False | 5 | 3 | 20.0 | 0.5699 | -0.2906 | 0.8825 | -0.0854 | 2.3058 | total_trade_count_lt_100, test_trade_count_lt_20, pair_count_lt_8, total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive |
| 1h 空头上影拒绝 ATR1.2 | 1h | short_rejection | short | False | 5 | 3 | 20.0 | 0.5699 | -0.2906 | 0.8825 | -0.0854 | 2.3058 | total_trade_count_lt_100, test_trade_count_lt_20, pair_count_lt_8, total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive |
| 1h 空头上影拒绝 ATR1.2 | 1h | short_rejection | short | False | 1 | 1 | 100.0 | -- | 1.9255 | -- | -- | 0.0 | total_trade_count_lt_100, test_trade_count_lt_20, pair_count_lt_8, total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive |
| 1h 空头上影拒绝 ATR1.2 | 1h | short_rejection | short | False | 1 | 1 | 100.0 | -- | 1.9255 | -- | -- | 0.0 | total_trade_count_lt_100, test_trade_count_lt_20, pair_count_lt_8, total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive |
| 1h 空头上影拒绝 ATR1.6 | 1h | short_rejection | short | False | 1 | 1 | 100.0 | -- | 1.7431 | -- | -- | 0.0 | total_trade_count_lt_100, test_trade_count_lt_20, pair_count_lt_8, total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive |
| 1h 空头上影拒绝 ATR1.6 | 1h | short_rejection | short | False | 1 | 1 | 100.0 | -- | 1.9446 | -- | -- | 0.0 | total_trade_count_lt_100, test_trade_count_lt_20, pair_count_lt_8, total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive |
| 1h 空头上影拒绝 ATR1.2 | 1h | short_rejection | short | False | 1 | 1 | 100.0 | -- | 1.9255 | -- | -- | 0.0 | total_trade_count_lt_100, test_trade_count_lt_20, pair_count_lt_8, total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive |
| 1h 空头上影拒绝 ATR1.2 | 1h | short_rejection | short | False | 1 | 1 | 100.0 | -- | 1.9255 | -- | -- | 0.0 | total_trade_count_lt_100, test_trade_count_lt_20, pair_count_lt_8, total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive |
| 1h 空头上影拒绝 ATR1.6 | 1h | short_rejection | short | False | 1 | 1 | 100.0 | -- | 1.7431 | -- | -- | 0.0 | total_trade_count_lt_100, test_trade_count_lt_20, pair_count_lt_8, total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive |
| 1h 空头上影拒绝 ATR1.6 | 1h | short_rejection | short | False | 1 | 1 | 100.0 | -- | 1.9446 | -- | -- | 0.0 | total_trade_count_lt_100, test_trade_count_lt_20, pair_count_lt_8, total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive |
| 1h 空头上影拒绝 ATR1.2 | 1h | short_rejection | short | False | 1 | 1 | 100.0 | -- | 1.9255 | -- | -- | 0.0 | total_trade_count_lt_100, test_trade_count_lt_20, pair_count_lt_8, total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive |
| 1h 空头上影拒绝 ATR1.2 | 1h | short_rejection | short | False | 1 | 1 | 100.0 | -- | 1.9255 | -- | -- | 0.0 | total_trade_count_lt_100, test_trade_count_lt_20, pair_count_lt_8, total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive |
| 1h 空头上影拒绝 ATR1.6 | 1h | short_rejection | short | False | 1 | 1 | 100.0 | -- | 1.7431 | -- | -- | 0.0 | total_trade_count_lt_100, test_trade_count_lt_20, pair_count_lt_8, total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive |
| 1h 空头上影拒绝 ATR1.6 | 1h | short_rejection | short | False | 1 | 1 | 100.0 | -- | 1.9446 | -- | -- | 0.0 | total_trade_count_lt_100, test_trade_count_lt_20, pair_count_lt_8, total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive |
| 1h 空头上影拒绝 ATR1.2 | 1h | short_rejection | short | False | 1 | 1 | 100.0 | -- | 1.9255 | -- | -- | 0.0 | total_trade_count_lt_100, test_trade_count_lt_20, pair_count_lt_8, total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive |
| 1h 空头上影拒绝 ATR1.2 | 1h | short_rejection | short | False | 1 | 1 | 100.0 | -- | 1.9255 | -- | -- | 0.0 | total_trade_count_lt_100, test_trade_count_lt_20, pair_count_lt_8, total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive |
| 1h 空头上影拒绝 ATR1.6 | 1h | short_rejection | short | False | 1 | 1 | 100.0 | -- | 1.7431 | -- | -- | 0.0 | total_trade_count_lt_100, test_trade_count_lt_20, pair_count_lt_8, total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive |
| 1h 空头上影拒绝 ATR1.6 | 1h | short_rejection | short | False | 1 | 1 | 100.0 | -- | 1.9446 | -- | -- | 0.0 | total_trade_count_lt_100, test_trade_count_lt_20, pair_count_lt_8, total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive |
| 1h 空头上影拒绝 ATR1.6 | 1h | short_rejection | short | False | 9 | 4 | 44.4444 | 0.774 | -0.1106 | 1.0403 | 0.0142 | 2.2576 | total_trade_count_lt_100, test_trade_count_lt_20, pair_count_lt_8, total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, validation_expectancy_too_negative |
| 1h 空头上影拒绝 ATR1.6 | 1h | short_rejection | short | False | 11 | 4 | 45.4545 | 0.7219 | -0.1395 | 1.0403 | 0.0142 | 3.0037 | total_trade_count_lt_100, test_trade_count_lt_20, pair_count_lt_8, total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, validation_expectancy_too_negative |
| 15m 放量回踩修复 ATR1.3 | 15m | volume_rebound_long | long | False | 230 | 5 | 30.8696 | 0.6408 | -0.2946 | 1.0937 | 0.0634 | 82.3479 | pair_count_lt_8, total_profit_factor_lt_1_10, validation_expectancy_too_negative, drawdown_gt_35r |
| 15m 放量回踩修复 ATR1.3 | 15m | volume_rebound_long | long | False | 230 | 5 | 30.8696 | 0.6408 | -0.2946 | 1.0937 | 0.0634 | 82.3479 | pair_count_lt_8, total_profit_factor_lt_1_10, validation_expectancy_too_negative, drawdown_gt_35r |
| 15m 放量回踩修复 ATR1.3 | 15m | volume_rebound_long | long | False | 218 | 5 | 29.8165 | 0.6074 | -0.3268 | 1.0796 | 0.0542 | 82.3012 | pair_count_lt_8, total_profit_factor_lt_1_10, validation_expectancy_too_negative, drawdown_gt_35r |

## Safety Boundary

- apiKeyStorage: False
- tradeApiEnabled: False
- withdrawApiEnabled: False
- realAccountReads: False
- realPositionReads: False
- orderCreation: False
- exchangeDryRun: False
- liveTrading: False
- autoTrading: False
- researchOnly: True

## Next Step

Only approved selected candidates may enter local sandbox / paper-observation review.
Exchange dry-run and live trading remain blocked until real forward samples are available.
