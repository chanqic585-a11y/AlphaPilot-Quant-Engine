# AlphaPilot V13.7.40 Short-Cycle Parameter Search

This report searches short-cycle public-OHLCV research candidates with fixed 2R exits.
It is not exchange dry-run, not live trading, not an order, and not trading advice.

## Summary

- status: completed
- candidateCount: 1472
- approvedCount: 0
- selectedCount: 5
- approvedSelectedCount: 0
- targetR: 2.0
- feeRate: 0.0005
- slippageRate: 0.0005
- timerange: 20260101-

## Data Coverage

- 15m: 45 pairs
- 30m: 45 pairs
- 1h: 45 pairs

## Selected Candidates

| Candidate | TF | Family | Direction | Approved | Trades | Pairs | Win % | PF | Exp R | Test PF | Test Exp R | DD R | Failed Checks |
| --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 1h 空头上影拒绝 ATR1.2 | 1h | short_rejection | short | False | 97 | 39 | 45.3608 | 0.8303 | -0.0912 | 0.8264 | -0.08 | 22.6737 | total_trade_count_lt_100, total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive |
| 1h 空头上影拒绝 ATR1.2 | 1h | short_rejection | short | False | 88 | 39 | 46.5909 | 0.8438 | -0.0819 | 1.0281 | 0.0113 | 20.5354 | total_trade_count_lt_100, total_profit_factor_lt_1_10, test_profit_factor_lt_1_05 |
| 1h 空头上影拒绝 ATR1.6 | 1h | short_rejection | short | False | 97 | 39 | 48.4536 | 0.7758 | -0.0977 | 0.668 | -0.1142 | 17.1775 | total_trade_count_lt_100, total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive |
| 1h 空头上影拒绝 ATR1.6 | 1h | short_rejection | short | False | 105 | 40 | 47.619 | 0.7548 | -0.1131 | 0.7831 | -0.0686 | 22.2313 | total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive |
| 1h 空头上影拒绝 ATR1.2 | 1h | short_rejection | short | False | 105 | 40 | 43.8095 | 0.7562 | -0.1364 | 0.9969 | -0.0013 | 27.7071 | total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive |

### 1h 空头上影拒绝 ATR1.2

- candidateId: `v13_7_40_1h_short_rejection_1441`
- approved: False
- params: `{"upper_buffer": 0.003, "trend_tolerance": 1.0, "rsi_high": 62, "volume_min": 0.9, "stop_atr": 1.2, "max_hold": 8}`

#### Walk-Forward

| Split | Trades | Pairs | Win % | PF | Exp R | Total R | DD R |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| train | 52 | 32 | 36.5385 | 0.5887 | -0.2636 | -13.7046 | 22.6737 |
| validation | 9 | 7 | 77.7778 | 4.5177 | 0.8602 | 7.7419 | 1.2349 |
| test | 36 | 25 | 50.0 | 0.8264 | -0.08 | -2.8798 | 6.9668 |

#### Top Pair Breakdown

| Pair | Trades | Win % | PF | Exp R | Total R |
| --- | ---: | ---: | ---: | ---: | ---: |
| TAO/USDT:USDT | 5 | 80.0 | 4.0456 | 0.6494 | 3.2472 |
| WLD/USDT:USDT | 1 | 100.0 | -- | 1.8902 | 1.8902 |
| GMT/USDT:USDT | 1 | 100.0 | -- | 1.8551 | 1.8551 |
| LTC/USDT:USDT | 2 | 50.0 | 50.7312 | 0.9014 | 1.8029 |
| DOGE/USDT:USDT | 4 | 75.0 | 2.5108 | 0.4138 | 1.6552 |
| STX/USDT:USDT | 5 | 60.0 | 1.8286 | 0.2988 | 1.4939 |
| ARB/USDT:USDT | 3 | 66.6667 | 2.528 | 0.492 | 1.476 |
| AXS/USDT:USDT | 4 | 50.0 | 2.1172 | 0.3629 | 1.4515 |

### 1h 空头上影拒绝 ATR1.2

- candidateId: `v13_7_40_1h_short_rejection_1409`
- approved: False
- params: `{"upper_buffer": 0.0, "trend_tolerance": 1.0, "rsi_high": 62, "volume_min": 0.9, "stop_atr": 1.2, "max_hold": 8}`

#### Walk-Forward

| Split | Trades | Pairs | Win % | PF | Exp R | Total R | DD R |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| train | 47 | 32 | 36.1702 | 0.5079 | -0.3258 | -15.3122 | 20.5354 |
| validation | 9 | 7 | 77.7778 | 4.5177 | 0.8602 | 7.7419 | 1.2349 |
| test | 32 | 24 | 53.125 | 1.0281 | 0.0113 | 0.3601 | 5.7313 |

#### Top Pair Breakdown

| Pair | Trades | Win % | PF | Exp R | Total R |
| --- | ---: | ---: | ---: | ---: | ---: |
| STX/USDT:USDT | 4 | 75.0 | 4.5178 | 0.6418 | 2.5671 |
| AXS/USDT:USDT | 3 | 66.6667 | 12.379 | 0.8429 | 2.5286 |
| WLD/USDT:USDT | 1 | 100.0 | -- | 1.8902 | 1.8902 |
| GMT/USDT:USDT | 1 | 100.0 | -- | 1.8551 | 1.8551 |
| LTC/USDT:USDT | 2 | 50.0 | 50.7312 | 0.9014 | 1.8029 |
| RENDER/USDT:USDT | 2 | 100.0 | -- | 0.6688 | 1.3376 |
| TAO/USDT:USDT | 4 | 75.0 | 2.2329 | 0.3286 | 1.3145 |
| SUI/USDT:USDT | 3 | 66.6667 | 2.0132 | 0.3664 | 1.0992 |

### 1h 空头上影拒绝 ATR1.6

- candidateId: `v13_7_40_1h_short_rejection_1443`
- approved: False
- params: `{"upper_buffer": 0.003, "trend_tolerance": 1.0, "rsi_high": 62, "volume_min": 0.9, "stop_atr": 1.6, "max_hold": 8}`

#### Walk-Forward

| Split | Trades | Pairs | Win % | PF | Exp R | Total R | DD R |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| train | 52 | 32 | 42.3077 | 0.546 | -0.2445 | -12.7152 | 17.1775 |
| validation | 9 | 7 | 77.7778 | 4.865 | 0.8163 | 7.347 | 1.1765 |
| test | 36 | 25 | 50.0 | 0.668 | -0.1142 | -4.1124 | 5.7951 |

#### Top Pair Breakdown

| Pair | Trades | Win % | PF | Exp R | Total R |
| --- | ---: | ---: | ---: | ---: | ---: |
| AXS/USDT:USDT | 4 | 75.0 | 16.968 | 0.6653 | 2.6612 |
| TAO/USDT:USDT | 5 | 80.0 | 3.1145 | 0.444 | 2.2201 |
| STX/USDT:USDT | 5 | 60.0 | 3.9334 | 0.4435 | 2.2173 |
| GMT/USDT:USDT | 1 | 100.0 | -- | 1.8919 | 1.8919 |
| TIA/USDT:USDT | 5 | 60.0 | 2.5581 | 0.3683 | 1.8416 |
| ARB/USDT:USDT | 3 | 66.6667 | 2.9408 | 0.4687 | 1.406 |
| ATOM/USDT:USDT | 4 | 75.0 | 3.9132 | 0.2987 | 1.195 |
| SUI/USDT:USDT | 3 | 66.6667 | 2.0101 | 0.3582 | 1.0746 |

### 1h 空头上影拒绝 ATR1.6

- candidateId: `v13_7_40_1h_short_rejection_1427`
- approved: False
- params: `{"upper_buffer": 0.0, "trend_tolerance": 1.005, "rsi_high": 62, "volume_min": 0.9, "stop_atr": 1.6, "max_hold": 8}`

#### Walk-Forward

| Split | Trades | Pairs | Win % | PF | Exp R | Total R | DD R |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| train | 52 | 34 | 36.5385 | 0.3802 | -0.3742 | -19.4566 | 21.5005 |
| validation | 19 | 14 | 68.4211 | 2.5732 | 0.5215 | 9.909 | 2.4742 |
| test | 34 | 24 | 52.9412 | 0.7831 | -0.0686 | -2.3307 | 4.1017 |

#### Top Pair Breakdown

| Pair | Trades | Win % | PF | Exp R | Total R |
| --- | ---: | ---: | ---: | ---: | ---: |
| TIA/USDT:USDT | 7 | 71.4286 | 4.0122 | 0.5086 | 3.5602 |
| ETH/USDT:USDT | 3 | 66.6667 | 423.6589 | 0.9418 | 2.8255 |
| STX/USDT:USDT | 4 | 75.0 | 5.4322 | 0.6065 | 2.4258 |
| BCH/USDT:USDT | 4 | 75.0 | 18.2587 | 0.5383 | 2.153 |
| GMT/USDT:USDT | 1 | 100.0 | -- | 1.8919 | 1.8919 |
| AXS/USDT:USDT | 3 | 66.6667 | 10.9027 | 0.5501 | 1.6504 |
| LDO/USDT:USDT | 2 | 100.0 | -- | 0.5926 | 1.1852 |
| SUI/USDT:USDT | 3 | 66.6667 | 2.0101 | 0.3582 | 1.0746 |

### 1h 空头上影拒绝 ATR1.2

- candidateId: `v13_7_40_1h_short_rejection_1425`
- approved: False
- params: `{"upper_buffer": 0.0, "trend_tolerance": 1.005, "rsi_high": 62, "volume_min": 0.9, "stop_atr": 1.2, "max_hold": 8}`

#### Walk-Forward

| Split | Trades | Pairs | Win % | PF | Exp R | Total R | DD R |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| train | 52 | 34 | 32.6923 | 0.4419 | -0.3837 | -19.955 | 25.0119 |
| validation | 19 | 14 | 57.8947 | 1.6264 | 0.2986 | 5.673 | 4.7227 |
| test | 34 | 24 | 52.9412 | 0.9969 | -0.0013 | -0.0428 | 6.8375 |

#### Top Pair Breakdown

| Pair | Trades | Win % | PF | Exp R | Total R |
| --- | ---: | ---: | ---: | ---: | ---: |
| STX/USDT:USDT | 4 | 75.0 | 4.5178 | 0.6418 | 2.5671 |
| AXS/USDT:USDT | 3 | 66.6667 | 12.379 | 0.8429 | 2.5286 |
| WLD/USDT:USDT | 1 | 100.0 | -- | 1.8902 | 1.8902 |
| GMT/USDT:USDT | 1 | 100.0 | -- | 1.8551 | 1.8551 |
| LTC/USDT:USDT | 2 | 50.0 | 50.7312 | 0.9014 | 1.8029 |
| LDO/USDT:USDT | 2 | 100.0 | -- | 0.7901 | 1.5803 |
| RENDER/USDT:USDT | 2 | 100.0 | -- | 0.6688 | 1.3376 |
| TAO/USDT:USDT | 4 | 75.0 | 2.2329 | 0.3286 | 1.3145 |

## Top 25 Candidates

| Candidate | TF | Family | Direction | Approved | Trades | Pairs | Win % | PF | Exp R | Test PF | Test Exp R | DD R | Failed Checks |
| --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 1h 空头上影拒绝 ATR1.2 | 1h | short_rejection | short | False | 97 | 39 | 45.3608 | 0.8303 | -0.0912 | 0.8264 | -0.08 | 22.6737 | total_trade_count_lt_100, total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive |
| 1h 空头上影拒绝 ATR1.2 | 1h | short_rejection | short | False | 88 | 39 | 46.5909 | 0.8438 | -0.0819 | 1.0281 | 0.0113 | 20.5354 | total_trade_count_lt_100, total_profit_factor_lt_1_10, test_profit_factor_lt_1_05 |
| 1h 空头上影拒绝 ATR1.6 | 1h | short_rejection | short | False | 97 | 39 | 48.4536 | 0.7758 | -0.0977 | 0.668 | -0.1142 | 17.1775 | total_trade_count_lt_100, total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive |
| 1h 空头上影拒绝 ATR1.6 | 1h | short_rejection | short | False | 105 | 40 | 47.619 | 0.7548 | -0.1131 | 0.7831 | -0.0686 | 22.2313 | total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive |
| 1h 空头上影拒绝 ATR1.2 | 1h | short_rejection | short | False | 105 | 40 | 43.8095 | 0.7562 | -0.1364 | 0.9969 | -0.0013 | 27.7071 | total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive |
| 1h 空头上影拒绝 ATR1.2 | 1h | short_rejection | short | False | 68 | 34 | 52.9412 | 1.1217 | 0.0528 | 1.2974 | 0.104 | 10.8095 | total_trade_count_lt_100 |
| 1h 空头上影拒绝 ATR1.2 | 1h | short_rejection | short | False | 64 | 34 | 54.6875 | 1.193 | 0.0824 | 1.3929 | 0.1321 | 9.7058 | total_trade_count_lt_100 |
| 1h 空头上影拒绝 ATR1.6 | 1h | short_rejection | short | False | 116 | 40 | 48.2759 | 0.8143 | -0.0837 | 0.6536 | -0.1228 | 21.2204 | total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive |
| 1h 空头上影拒绝 ATR1.6 | 1h | short_rejection | short | False | 88 | 39 | 48.8636 | 0.7556 | -0.1069 | 0.816 | -0.0556 | 17.1421 | total_trade_count_lt_100, total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive |
| 1h 空头上影拒绝 ATR1.2 | 1h | short_rejection | short | False | 116 | 40 | 43.9655 | 0.7997 | -0.1117 | 0.8145 | -0.0864 | 28.7842 | total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive |
| 1h 空头上影拒绝 ATR1.2 | 1h | short_rejection | short | False | 75 | 35 | 50.6667 | 1.0351 | 0.016 | 1.1698 | 0.0637 | 11.94 | total_trade_count_lt_100, total_profit_factor_lt_1_10 |
| 1h 空头上影拒绝 ATR1.2 | 1h | short_rejection | short | False | 71 | 35 | 52.1127 | 1.0901 | 0.0406 | 1.2416 | 0.0879 | 10.8363 | total_trade_count_lt_100, total_profit_factor_lt_1_10 |
| 1h 空头上影拒绝 ATR1.6 | 1h | short_rejection | short | False | 68 | 34 | 57.3529 | 1.1382 | 0.0461 | 0.9974 | -0.0007 | 8.1299 | total_trade_count_lt_100, test_profit_factor_lt_1_05, test_expectancy_not_positive |
| 1h 空头上影拒绝 ATR1.6 | 1h | short_rejection | short | False | 64 | 34 | 59.375 | 1.2383 | 0.0765 | 1.0941 | 0.0238 | 7.6099 | total_trade_count_lt_100 |
| 1h 空头上影拒绝 ATR1.6 | 1h | short_rejection | short | False | 75 | 35 | 54.6667 | 0.9977 | -0.0008 | 0.8773 | -0.0367 | 9.2281 | total_trade_count_lt_100, total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive |
| 1h 空头上影拒绝 ATR1.2 | 1h | short_rejection | short | False | 97 | 39 | 37.1134 | 0.7714 | -0.1539 | 0.5159 | -0.3758 | 28.3743 | total_trade_count_lt_100, total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive |
| 1h 空头上影拒绝 ATR1.6 | 1h | short_rejection | short | False | 71 | 35 | 56.338 | 1.0679 | 0.0239 | 0.9448 | -0.0156 | 8.708 | total_trade_count_lt_100, total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive |
| 1h 空头上影拒绝 ATR1.6 | 1h | short_rejection | short | False | 97 | 39 | 44.3299 | 0.6865 | -0.1762 | 0.3127 | -0.4763 | 24.0871 | total_trade_count_lt_100, total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive |
| 1h 空头上影拒绝 ATR1.2 | 1h | short_rejection | short | False | 88 | 39 | 37.5 | 0.7684 | -0.1529 | 0.5164 | -0.3655 | 25.5025 | total_trade_count_lt_100, total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive |
| 1h 空头上影拒绝 ATR1.6 | 1h | short_rejection | short | False | 116 | 40 | 43.9655 | 0.7298 | -0.1529 | 0.32 | -0.4658 | 25.7749 | total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive |
| 1h 空头上影拒绝 ATR1.6 | 1h | short_rejection | short | False | 105 | 40 | 41.9048 | 0.7092 | -0.1685 | 0.303 | -0.4822 | 25.3876 | total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive |
| 1h 空头上影拒绝 ATR1.2 | 1h | short_rejection | short | False | 105 | 40 | 35.2381 | 0.7002 | -0.2053 | 0.5216 | -0.3559 | 34.0294 | total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive |
| 1h 空头上影拒绝 ATR1.2 | 1h | short_rejection | short | False | 116 | 40 | 36.2069 | 0.7429 | -0.1754 | 0.5205 | -0.3666 | 35.693 | total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive, drawdown_gt_35r |
| 1h 空头上影拒绝 ATR1.2 | 1h | short_rejection | short | False | 68 | 34 | 39.7059 | 0.9025 | -0.0605 | 0.6852 | -0.2277 | 12.2319 | total_trade_count_lt_100, total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive |
| 1h 空头上影拒绝 ATR1.6 | 1h | short_rejection | short | False | 88 | 39 | 43.1818 | 0.6949 | -0.1723 | 0.294 | -0.495 | 23.071 | total_trade_count_lt_100, total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive |

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
