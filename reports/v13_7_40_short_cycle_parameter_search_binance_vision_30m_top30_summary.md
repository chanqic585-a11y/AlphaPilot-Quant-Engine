# AlphaPilot V13.7.40 Short-Cycle Parameter Search

This report searches short-cycle public-OHLCV research candidates with fixed 2R exits.
It is not exchange dry-run, not live trading, not an order, and not trading advice.

## Summary

- status: completed
- candidateCount: 592
- approvedCount: 0
- observationCandidateCount: 0
- selectedCount: 5
- approvedSelectedCount: 0
- observationSelectedCount: 0
- targetR: 2.0
- feeRate: 0.0005
- slippageRate: 0.0005
- timerange: 20200101-

## Data Coverage

- 30m: 30 pairs

## Selected Candidates

| Candidate | TF | Family | Direction | Tier | Strict | Observation | Trades | Pairs | Win % | PF | Exp R | Test PF | Test Exp R | DD R | Failed Checks | Observation Checks |
| --- | --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| 30m 低波压缩突破 ATR1.6 | 30m | squeeze_breakout_long | long | rejected | False | False | 4959 | 30 | 34.6844 | 0.6646 | -0.217 | 0.7641 | -0.1476 | 1103.8525 | total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive, validation_expectancy_too_negative, drawdown_gt_35r | observation_total_profit_factor_lt_1_00, observation_test_profit_factor_lt_1_00, observation_test_expectancy_not_positive, observation_validation_expectancy_too_negative, observation_drawdown_gt_45r |
| 30m 低波压缩突破 ATR1.6 | 30m | squeeze_breakout_long | long | rejected | False | False | 4921 | 30 | 32.5544 | 0.6804 | -0.2279 | 0.7896 | -0.1433 | 1161.4029 | total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive, validation_expectancy_too_negative, drawdown_gt_35r | observation_total_profit_factor_lt_1_00, observation_test_profit_factor_lt_1_00, observation_test_expectancy_not_positive, observation_validation_expectancy_too_negative, observation_drawdown_gt_45r |
| 30m 低波压缩突破 ATR1.6 | 30m | squeeze_breakout_long | long | rejected | False | False | 5961 | 30 | 35.0445 | 0.6676 | -0.2138 | 0.7548 | -0.1524 | 1278.627 | total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive, validation_expectancy_too_negative, drawdown_gt_35r | observation_total_profit_factor_lt_1_00, observation_test_profit_factor_lt_1_00, observation_test_expectancy_not_positive, observation_validation_expectancy_too_negative, observation_drawdown_gt_45r |
| 30m 低波压缩突破 ATR1.6 | 30m | squeeze_breakout_long | long | rejected | False | False | 5514 | 30 | 33.8049 | 0.6432 | -0.2362 | 0.7161 | -0.1825 | 1302.2251 | total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive, validation_expectancy_too_negative, drawdown_gt_35r | observation_total_profit_factor_lt_1_00, observation_test_profit_factor_lt_1_00, observation_test_expectancy_not_positive, observation_validation_expectancy_too_negative, observation_drawdown_gt_45r |
| 30m 低波压缩突破 ATR1.6 | 30m | squeeze_breakout_long | long | rejected | False | False | 5467 | 30 | 32.0468 | 0.6693 | -0.24 | 0.7433 | -0.1799 | 1318.0224 | total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive, validation_expectancy_too_negative, drawdown_gt_35r | observation_total_profit_factor_lt_1_00, observation_test_profit_factor_lt_1_00, observation_test_expectancy_not_positive, observation_validation_expectancy_too_negative, observation_drawdown_gt_45r |

### 30m 低波压缩突破 ATR1.6

- candidateId: `v13_7_40_30m_squeeze_breakout_long_903`
- approved: False
- observationCandidate: False
- approvalTier: rejected
- params: `{"lookback": 40, "squeeze_window": 80, "squeeze_ratio": 0.75, "volume_min": 1.4, "stop_atr": 1.6, "max_hold": 12}`

#### Walk-Forward

| Split | Trades | Pairs | Win % | PF | Exp R | Total R | DD R |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| train | 1842 | 24 | 32.6276 | 0.6279 | -0.2414 | -444.6422 | 464.456 |
| validation | 1379 | 30 | 33.14 | 0.5949 | -0.272 | -375.1305 | 382.5592 |
| test | 1738 | 30 | 38.0898 | 0.7641 | -0.1476 | -256.5548 | 315.127 |

#### Top Pair Breakdown

| Pair | Trades | Win % | PF | Exp R | Total R |
| --- | ---: | ---: | ---: | ---: | ---: |
| INJ/USDT:USDT | 87 | 41.3793 | 1.0229 | 0.0126 | 1.094 |
| JUP/USDT:USDT | 72 | 40.2778 | 0.9585 | -0.0249 | -1.7957 |
| ENA/USDT:USDT | 50 | 40.0 | 0.7444 | -0.1597 | -7.9847 |
| PYTH/USDT:USDT | 83 | 37.3494 | 0.8008 | -0.1151 | -9.554 |
| DOGE/USDT:USDT | 197 | 39.5939 | 0.9169 | -0.0489 | -9.6426 |
| AXS/USDT:USDT | 169 | 38.4615 | 0.8314 | -0.1008 | -17.0373 |
| LDO/USDT:USDT | 110 | 39.0909 | 0.7309 | -0.1721 | -18.928 |
| GMT/USDT:USDT | 119 | 36.1345 | 0.7071 | -0.1738 | -20.6778 |

### 30m 低波压缩突破 ATR1.6

- candidateId: `v13_7_40_30m_squeeze_breakout_long_904`
- approved: False
- observationCandidate: False
- approvalTier: rejected
- params: `{"lookback": 40, "squeeze_window": 80, "squeeze_ratio": 0.75, "volume_min": 1.4, "stop_atr": 1.6, "max_hold": 20}`

#### Walk-Forward

| Split | Trades | Pairs | Win % | PF | Exp R | Total R | DD R |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| train | 1824 | 24 | 30.7566 | 0.6445 | -0.258 | -470.5472 | 493.5802 |
| validation | 1365 | 30 | 30.696 | 0.5996 | -0.2952 | -402.973 | 412.3557 |
| test | 1732 | 30 | 35.9122 | 0.7896 | -0.1433 | -248.1893 | 321.2523 |

#### Top Pair Breakdown

| Pair | Trades | Win % | PF | Exp R | Total R |
| --- | ---: | ---: | ---: | ---: | ---: |
| INJ/USDT:USDT | 86 | 39.5349 | 1.1578 | 0.0936 | 8.0457 |
| JUP/USDT:USDT | 72 | 40.2778 | 1.0157 | 0.0096 | 0.6917 |
| DOGE/USDT:USDT | 195 | 38.9744 | 0.9306 | -0.0449 | -8.7636 |
| ENA/USDT:USDT | 50 | 30.0 | 0.7205 | -0.2017 | -10.0839 |
| PYTH/USDT:USDT | 83 | 36.1446 | 0.7269 | -0.1822 | -15.1203 |
| AVAX/USDT:USDT | 181 | 35.3591 | 0.8694 | -0.0876 | -15.8482 |
| AXS/USDT:USDT | 167 | 37.7246 | 0.8283 | -0.1133 | -18.9283 |
| LDO/USDT:USDT | 109 | 35.7798 | 0.7383 | -0.1779 | -19.391 |

### 30m 低波压缩突破 ATR1.6

- candidateId: `v13_7_40_30m_squeeze_breakout_long_899`
- approved: False
- observationCandidate: False
- approvalTier: rejected
- params: `{"lookback": 40, "squeeze_window": 80, "squeeze_ratio": 0.75, "volume_min": 1.1, "stop_atr": 1.6, "max_hold": 12}`

#### Walk-Forward

| Split | Trades | Pairs | Win % | PF | Exp R | Total R | DD R |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| train | 2132 | 24 | 32.7861 | 0.637 | -0.2334 | -497.6679 | 511.7223 |
| validation | 1701 | 30 | 33.6273 | 0.6033 | -0.2661 | -452.6929 | 463.6031 |
| test | 2128 | 30 | 38.4398 | 0.7548 | -0.1524 | -324.2738 | 362.9163 |

#### Top Pair Breakdown

| Pair | Trades | Win % | PF | Exp R | Total R |
| --- | ---: | ---: | ---: | ---: | ---: |
| JUP/USDT:USDT | 87 | 44.8276 | 1.0724 | 0.0406 | 3.5312 |
| ENA/USDT:USDT | 59 | 42.3729 | 0.9022 | -0.0574 | -3.3874 |
| INJ/USDT:USDT | 111 | 39.6396 | 0.9241 | -0.0441 | -4.8928 |
| DOGE/USDT:USDT | 224 | 39.2857 | 0.8634 | -0.0811 | -18.1558 |
| LDO/USDT:USDT | 133 | 38.3459 | 0.7553 | -0.1577 | -20.9801 |
| APT/USDT:USDT | 129 | 36.4341 | 0.7379 | -0.1674 | -21.5933 |
| PYTH/USDT:USDT | 114 | 35.0877 | 0.6931 | -0.1952 | -22.2533 |
| OP/USDT:USDT | 159 | 34.5912 | 0.7675 | -0.1458 | -23.1766 |

### 30m 低波压缩突破 ATR1.6

- candidateId: `v13_7_40_30m_squeeze_breakout_long_919`
- approved: False
- observationCandidate: False
- approvalTier: rejected
- params: `{"lookback": 40, "squeeze_window": 120, "squeeze_ratio": 0.75, "volume_min": 1.4, "stop_atr": 1.6, "max_hold": 12}`

#### Walk-Forward

| Split | Trades | Pairs | Win % | PF | Exp R | Total R | DD R |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| train | 1962 | 25 | 33.4862 | 0.6555 | -0.2214 | -434.4347 | 444.5203 |
| validation | 1629 | 30 | 31.0006 | 0.5513 | -0.3173 | -516.9356 | 526.1509 |
| test | 1923 | 30 | 36.5055 | 0.7161 | -0.1825 | -350.8547 | 383.2255 |

#### Top Pair Breakdown

| Pair | Trades | Win % | PF | Exp R | Total R |
| --- | ---: | ---: | ---: | ---: | ---: |
| INJ/USDT:USDT | 104 | 42.3077 | 1.048 | 0.0269 | 2.7937 |
| JUP/USDT:USDT | 90 | 36.6667 | 0.8401 | -0.1004 | -9.038 |
| ENA/USDT:USDT | 64 | 35.9375 | 0.7202 | -0.1762 | -11.2752 |
| ORDI/USDT:USDT | 109 | 36.6972 | 0.7388 | -0.1579 | -17.2143 |
| DOGE/USDT:USDT | 230 | 37.8261 | 0.8597 | -0.0844 | -19.406 |
| PYTH/USDT:USDT | 87 | 28.7356 | 0.5998 | -0.2728 | -23.7356 |
| GMT/USDT:USDT | 128 | 32.8125 | 0.6708 | -0.2065 | -26.429 |
| ONDO/USDT:USDT | 71 | 30.9859 | 0.4512 | -0.4036 | -28.6567 |

### 30m 低波压缩突破 ATR1.6

- candidateId: `v13_7_40_30m_squeeze_breakout_long_920`
- approved: False
- observationCandidate: False
- approvalTier: rejected
- params: `{"lookback": 40, "squeeze_window": 120, "squeeze_ratio": 0.75, "volume_min": 1.4, "stop_atr": 1.6, "max_hold": 20}`

#### Walk-Forward

| Split | Trades | Pairs | Win % | PF | Exp R | Total R | DD R |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| train | 1944 | 25 | 31.9444 | 0.6797 | -0.2294 | -445.9591 | 462.811 |
| validation | 1614 | 30 | 29.368 | 0.5774 | -0.3238 | -522.5739 | 535.4652 |
| test | 1909 | 30 | 34.4159 | 0.7433 | -0.1799 | -343.515 | 374.8005 |

#### Top Pair Breakdown

| Pair | Trades | Win % | PF | Exp R | Total R |
| --- | ---: | ---: | ---: | ---: | ---: |
| INJ/USDT:USDT | 103 | 40.7767 | 1.1502 | 0.0879 | 9.0496 |
| ENA/USDT:USDT | 64 | 34.375 | 0.8409 | -0.1065 | -6.8155 |
| JUP/USDT:USDT | 89 | 35.9551 | 0.8447 | -0.1017 | -9.0551 |
| ORDI/USDT:USDT | 108 | 33.3333 | 0.7981 | -0.133 | -14.3623 |
| DOGE/USDT:USDT | 227 | 37.0044 | 0.9017 | -0.0656 | -14.8856 |
| ADA/USDT:USDT | 251 | 39.0438 | 0.8676 | -0.0878 | -22.0379 |
| PYTH/USDT:USDT | 87 | 29.8851 | 0.5928 | -0.3046 | -26.5043 |
| APE/USDT:USDT | 146 | 33.5616 | 0.719 | -0.1987 | -29.0125 |

## Top 25 Candidates

| Candidate | TF | Family | Direction | Tier | Strict | Observation | Trades | Pairs | Win % | PF | Exp R | Test PF | Test Exp R | DD R | Failed Checks | Observation Checks |
| --- | --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| 30m 低波压缩突破 ATR1.6 | 30m | squeeze_breakout_long | long | rejected | False | False | 4959 | 30 | 34.6844 | 0.6646 | -0.217 | 0.7641 | -0.1476 | 1103.8525 | total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive, validation_expectancy_too_negative, drawdown_gt_35r | observation_total_profit_factor_lt_1_00, observation_test_profit_factor_lt_1_00, observation_test_expectancy_not_positive, observation_validation_expectancy_too_negative, observation_drawdown_gt_45r |
| 30m 低波压缩突破 ATR1.6 | 30m | squeeze_breakout_long | long | rejected | False | False | 4921 | 30 | 32.5544 | 0.6804 | -0.2279 | 0.7896 | -0.1433 | 1161.4029 | total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive, validation_expectancy_too_negative, drawdown_gt_35r | observation_total_profit_factor_lt_1_00, observation_test_profit_factor_lt_1_00, observation_test_expectancy_not_positive, observation_validation_expectancy_too_negative, observation_drawdown_gt_45r |
| 30m 低波压缩突破 ATR1.6 | 30m | squeeze_breakout_long | long | rejected | False | False | 5961 | 30 | 35.0445 | 0.6676 | -0.2138 | 0.7548 | -0.1524 | 1278.627 | total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive, validation_expectancy_too_negative, drawdown_gt_35r | observation_total_profit_factor_lt_1_00, observation_test_profit_factor_lt_1_00, observation_test_expectancy_not_positive, observation_validation_expectancy_too_negative, observation_drawdown_gt_45r |
| 30m 低波压缩突破 ATR1.6 | 30m | squeeze_breakout_long | long | rejected | False | False | 5514 | 30 | 33.8049 | 0.6432 | -0.2362 | 0.7161 | -0.1825 | 1302.2251 | total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive, validation_expectancy_too_negative, drawdown_gt_35r | observation_total_profit_factor_lt_1_00, observation_test_profit_factor_lt_1_00, observation_test_expectancy_not_positive, observation_validation_expectancy_too_negative, observation_drawdown_gt_45r |
| 30m 低波压缩突破 ATR1.6 | 30m | squeeze_breakout_long | long | rejected | False | False | 5467 | 30 | 32.0468 | 0.6693 | -0.24 | 0.7433 | -0.1799 | 1318.0224 | total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive, validation_expectancy_too_negative, drawdown_gt_35r | observation_total_profit_factor_lt_1_00, observation_test_profit_factor_lt_1_00, observation_test_expectancy_not_positive, observation_validation_expectancy_too_negative, observation_drawdown_gt_45r |
| 30m 低波压缩突破 ATR1.6 | 30m | squeeze_breakout_long | long | rejected | False | False | 5884 | 30 | 32.6818 | 0.6831 | -0.2253 | 0.7919 | -0.141 | 1352.1933 | total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive, validation_expectancy_too_negative, drawdown_gt_35r | observation_total_profit_factor_lt_1_00, observation_test_profit_factor_lt_1_00, observation_test_expectancy_not_positive, observation_validation_expectancy_too_negative, observation_drawdown_gt_45r |
| 30m 低波压缩突破 ATR1.2 | 30m | squeeze_breakout_long | long | rejected | False | False | 5030 | 30 | 31.5905 | 0.6356 | -0.2771 | 0.7027 | -0.2208 | 1398.8767 | total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive, validation_expectancy_too_negative, drawdown_gt_35r | observation_total_profit_factor_lt_1_00, observation_test_profit_factor_lt_1_00, observation_test_expectancy_not_positive, observation_validation_expectancy_too_negative, observation_drawdown_gt_45r |
| 30m 低波压缩突破 ATR1.2 | 30m | squeeze_breakout_long | long | rejected | False | False | 5013 | 30 | 29.982 | 0.6448 | -0.2834 | 0.7047 | -0.2306 | 1427.6454 | total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive, validation_expectancy_too_negative, drawdown_gt_35r | observation_total_profit_factor_lt_1_00, observation_test_profit_factor_lt_1_00, observation_test_expectancy_not_positive, observation_validation_expectancy_too_negative, observation_drawdown_gt_45r |
| 30m 低波压缩突破 ATR1.6 | 30m | squeeze_breakout_long | long | rejected | False | False | 6579 | 30 | 34.2605 | 0.6487 | -0.2304 | 0.7256 | -0.1742 | 1515.6761 | total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive, validation_expectancy_too_negative, drawdown_gt_35r | observation_total_profit_factor_lt_1_00, observation_test_profit_factor_lt_1_00, observation_test_expectancy_not_positive, observation_validation_expectancy_too_negative, observation_drawdown_gt_45r |
| 30m 低波压缩突破 ATR1.6 | 30m | squeeze_breakout_long | long | rejected | False | False | 6483 | 30 | 32.269 | 0.6741 | -0.2354 | 0.756 | -0.1694 | 1528.4734 | total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive, validation_expectancy_too_negative, drawdown_gt_35r | observation_total_profit_factor_lt_1_00, observation_test_profit_factor_lt_1_00, observation_test_expectancy_not_positive, observation_validation_expectancy_too_negative, observation_drawdown_gt_45r |
| 30m 低波压缩突破 ATR1.2 | 30m | squeeze_breakout_long | long | rejected | False | False | 6067 | 30 | 31.9927 | 0.638 | -0.2736 | 0.6972 | -0.224 | 1662.7897 | total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive, validation_expectancy_too_negative, drawdown_gt_35r | observation_total_profit_factor_lt_1_00, observation_test_profit_factor_lt_1_00, observation_test_expectancy_not_positive, observation_validation_expectancy_too_negative, observation_drawdown_gt_45r |
| 30m 低波压缩突破 ATR1.2 | 30m | squeeze_breakout_long | long | rejected | False | False | 6035 | 30 | 30.2237 | 0.648 | -0.2797 | 0.7082 | -0.2266 | 1692.9226 | total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive, validation_expectancy_too_negative, drawdown_gt_35r | observation_total_profit_factor_lt_1_00, observation_test_profit_factor_lt_1_00, observation_test_expectancy_not_positive, observation_validation_expectancy_too_negative, observation_drawdown_gt_45r |
| 30m 低波压缩突破 ATR1.2 | 30m | squeeze_breakout_long | long | rejected | False | False | 5565 | 30 | 29.3621 | 0.6178 | -0.3107 | 0.6548 | -0.2766 | 1729.0599 | total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive, validation_expectancy_too_negative, drawdown_gt_35r | observation_total_profit_factor_lt_1_00, observation_test_profit_factor_lt_1_00, observation_test_expectancy_not_positive, observation_validation_expectancy_too_negative, observation_drawdown_gt_45r |
| 30m 低波压缩突破 ATR1.2 | 30m | squeeze_breakout_long | long | rejected | False | False | 5585 | 30 | 30.6177 | 0.6021 | -0.3099 | 0.6435 | -0.2732 | 1730.6143 | total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive, validation_expectancy_too_negative, drawdown_gt_35r | observation_total_profit_factor_lt_1_00, observation_test_profit_factor_lt_1_00, observation_test_expectancy_not_positive, observation_validation_expectancy_too_negative, observation_drawdown_gt_45r |
| 30m 低波压缩突破 ATR1.6 | 30m | squeeze_breakout_long | long | rejected | False | False | 8774 | 30 | 34.2489 | 0.66 | -0.2218 | 0.7445 | -0.1613 | 1949.0774 | total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive, validation_expectancy_too_negative, drawdown_gt_35r | observation_total_profit_factor_lt_1_00, observation_test_profit_factor_lt_1_00, observation_test_expectancy_not_positive, observation_validation_expectancy_too_negative, observation_drawdown_gt_45r |
| 30m 低波压缩突破 ATR1.6 | 30m | squeeze_breakout_long | long | rejected | False | False | 8668 | 30 | 32.2566 | 0.6754 | -0.2332 | 0.7598 | -0.1663 | 2026.0795 | total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive, validation_expectancy_too_negative, drawdown_gt_35r | observation_total_profit_factor_lt_1_00, observation_test_profit_factor_lt_1_00, observation_test_expectancy_not_positive, observation_validation_expectancy_too_negative, observation_drawdown_gt_45r |
| 30m 低波压缩突破 ATR1.2 | 30m | squeeze_breakout_long | long | rejected | False | False | 6695 | 30 | 30.8887 | 0.6033 | -0.3073 | 0.6493 | -0.2663 | 2057.6555 | total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive, validation_expectancy_too_negative, drawdown_gt_35r | observation_total_profit_factor_lt_1_00, observation_test_profit_factor_lt_1_00, observation_test_expectancy_not_positive, observation_validation_expectancy_too_negative, observation_drawdown_gt_45r |
| 30m 低波压缩突破 ATR1.2 | 30m | squeeze_breakout_long | long | rejected | False | False | 6656 | 30 | 29.5222 | 0.6183 | -0.3098 | 0.6648 | -0.2664 | 2062.1092 | total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive, validation_expectancy_too_negative, drawdown_gt_35r | observation_total_profit_factor_lt_1_00, observation_test_profit_factor_lt_1_00, observation_test_expectancy_not_positive, observation_validation_expectancy_too_negative, observation_drawdown_gt_45r |
| 30m 低波压缩突破 ATR1.6 | 30m | squeeze_breakout_long | long | rejected | False | False | 9577 | 30 | 33.9041 | 0.6493 | -0.232 | 0.7027 | -0.1921 | 2227.3813 | total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive, validation_expectancy_too_negative, drawdown_gt_35r | observation_total_profit_factor_lt_1_00, observation_test_profit_factor_lt_1_00, observation_test_expectancy_not_positive, observation_validation_expectancy_too_negative, observation_drawdown_gt_45r |
| 30m 低波压缩突破 ATR1.6 | 30m | squeeze_breakout_long | long | rejected | False | False | 10353 | 30 | 34.7339 | 0.6653 | -0.2166 | 0.7475 | -0.1573 | 2242.6559 | total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive, validation_expectancy_too_negative, drawdown_gt_35r | observation_total_profit_factor_lt_1_00, observation_test_profit_factor_lt_1_00, observation_test_expectancy_not_positive, observation_validation_expectancy_too_negative, observation_drawdown_gt_45r |
| 30m 低波压缩突破 ATR1.6 | 30m | squeeze_breakout_long | long | rejected | False | False | 9451 | 30 | 32.1659 | 0.6754 | -0.2356 | 0.7246 | -0.1953 | 2234.1383 | total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive, validation_expectancy_too_negative, drawdown_gt_35r | observation_total_profit_factor_lt_1_00, observation_test_profit_factor_lt_1_00, observation_test_expectancy_not_positive, observation_validation_expectancy_too_negative, observation_drawdown_gt_45r |
| 30m 低波压缩突破 ATR1.6 | 30m | squeeze_breakout_long | long | rejected | False | False | 10164 | 30 | 32.4085 | 0.679 | -0.2297 | 0.7533 | -0.1702 | 2334.9326 | total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive, validation_expectancy_too_negative, drawdown_gt_35r | observation_total_profit_factor_lt_1_00, observation_test_profit_factor_lt_1_00, observation_test_expectancy_not_positive, observation_validation_expectancy_too_negative, observation_drawdown_gt_45r |
| 30m 低波压缩突破 ATR1.6 | 30m | squeeze_breakout_long | long | rejected | False | False | 10587 | 30 | 32.7855 | 0.6891 | -0.222 | 0.7797 | -0.1516 | 2364.1795 | total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive, validation_expectancy_too_negative, drawdown_gt_35r | observation_total_profit_factor_lt_1_00, observation_test_profit_factor_lt_1_00, observation_test_expectancy_not_positive, observation_validation_expectancy_too_negative, observation_drawdown_gt_45r |
| 30m 低波压缩突破 ATR1.6 | 30m | squeeze_breakout_long | long | rejected | False | False | 10691 | 30 | 34.3466 | 0.6587 | -0.2222 | 0.7247 | -0.1749 | 2384.3389 | total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive, validation_expectancy_too_negative, drawdown_gt_35r | observation_total_profit_factor_lt_1_00, observation_test_profit_factor_lt_1_00, observation_test_expectancy_not_positive, observation_validation_expectancy_too_negative, observation_drawdown_gt_45r |
| 30m 低波压缩突破 ATR1.6 | 30m | squeeze_breakout_long | long | rejected | False | False | 11358 | 30 | 32.7963 | 0.6913 | -0.2217 | 0.7573 | -0.1696 | 2521.1747 | total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive, validation_expectancy_too_negative, drawdown_gt_35r | observation_total_profit_factor_lt_1_00, observation_test_profit_factor_lt_1_00, observation_test_expectancy_not_positive, observation_validation_expectancy_too_negative, observation_drawdown_gt_45r |

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
