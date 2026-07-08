# AlphaPilot V13.7.40 Short-Cycle Parameter Search

This report searches short-cycle public-OHLCV research candidates with fixed 2R exits.
It is not exchange dry-run, not live trading, not an order, and not trading advice.

## Summary

- status: completed
- candidateCount: 928
- approvedCount: 0
- observationCandidateCount: 4
- selectedCount: 5
- approvedSelectedCount: 0
- observationSelectedCount: 4
- targetR: 2.0
- feeRate: 0.0005
- slippageRate: 0.0005
- timerange: 20200101-

## Data Coverage

- 1h: 44 pairs

## Selected Candidates

| Candidate | TF | Family | Direction | Tier | Strict | Observation | Trades | Pairs | Win % | PF | Exp R | Test PF | Test Exp R | DD R | Failed Checks | Observation Checks |
| --- | --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| 1h 空头上影拒绝 ATR1.2 | 1h | short_rejection | short | observation_candidate | False | True | 473 | 44 | 44.8203 | 1.0056 | 0.0029 | 1.3016 | 0.142 | 27.5951 | total_profit_factor_lt_1_10 | -- |
| 1h 空头上影拒绝 ATR1.2 | 1h | short_rejection | short | observation_candidate | False | True | 473 | 44 | 42.2833 | 1.0521 | 0.0302 | 1.1818 | 0.1022 | 22.9435 | total_profit_factor_lt_1_10 | -- |
| 1h 空头上影拒绝 ATR1.2 | 1h | short_rejection | short | observation_candidate | False | True | 453 | 44 | 44.5916 | 1.0021 | 0.0011 | 1.1954 | 0.0953 | 25.2311 | total_profit_factor_lt_1_10, validation_expectancy_too_negative | -- |
| 1h 空头上影拒绝 ATR1.2 | 1h | short_rejection | short | observation_candidate | False | True | 453 | 44 | 41.9426 | 1.0399 | 0.0232 | 1.0623 | 0.0364 | 20.7585 | total_profit_factor_lt_1_10 | -- |
| 1h 空头上影拒绝 ATR1.2 | 1h | short_rejection | short | rejected | False | False | 547 | 44 | 43.3272 | 0.9564 | -0.0236 | 1.2225 | 0.1106 | 38.086 | total_profit_factor_lt_1_10, validation_expectancy_too_negative, drawdown_gt_35r | observation_total_profit_factor_lt_1_00 |

### 1h 空头上影拒绝 ATR1.2

- candidateId: `v13_7_40_1h_short_rejection_2021`
- approved: False
- observationCandidate: True
- approvalTier: observation_candidate
- params: `{"upper_buffer": 0.003, "trend_tolerance": 1.0, "rsi_high": 62, "volume_min": 1.2, "stop_atr": 1.2, "max_hold": 8}`

#### Walk-Forward

| Split | Trades | Pairs | Win % | PF | Exp R | Total R | DD R |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| train | 155 | 31 | 36.7742 | 0.8305 | -0.0942 | -14.596 | 21.399 |
| validation | 156 | 43 | 45.5128 | 0.9174 | -0.0451 | -7.029 | 24.1912 |
| test | 162 | 43 | 51.8519 | 1.3016 | 0.142 | 23.0067 | 10.5841 |

#### Top Pair Breakdown

| Pair | Trades | Win % | PF | Exp R | Total R |
| --- | ---: | ---: | ---: | ---: | ---: |
| LTC/USDT:USDT | 20 | 50.0 | 2.1588 | 0.3969 | 7.9374 |
| APT/USDT:USDT | 8 | 62.5 | 3.6806 | 0.8195 | 6.5559 |
| BTC/USDT:USDT | 11 | 63.6364 | 3.0404 | 0.5739 | 6.3127 |
| SEI/USDT:USDT | 7 | 71.4286 | 3.5039 | 0.79 | 5.5297 |
| AXS/USDT:USDT | 15 | 53.3333 | 2.3352 | 0.3011 | 4.5172 |
| ADA/USDT:USDT | 13 | 61.5385 | 1.8386 | 0.3359 | 4.3665 |
| DOGE/USDT:USDT | 19 | 63.1579 | 1.6615 | 0.2198 | 4.1763 |
| ONDO/USDT:USDT | 5 | 80.0 | 4.641 | 0.787 | 3.9352 |

### 1h 空头上影拒绝 ATR1.2

- candidateId: `v13_7_40_1h_short_rejection_2022`
- approved: False
- observationCandidate: True
- approvalTier: observation_candidate
- params: `{"upper_buffer": 0.003, "trend_tolerance": 1.0, "rsi_high": 62, "volume_min": 1.2, "stop_atr": 1.2, "max_hold": 12}`

#### Walk-Forward

| Split | Trades | Pairs | Win % | PF | Exp R | Total R | DD R |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| train | 155 | 31 | 40.0 | 0.9644 | -0.0211 | -3.2756 | 18.0568 |
| validation | 156 | 43 | 41.6667 | 1.0109 | 0.0063 | 0.988 | 22.9152 |
| test | 162 | 43 | 45.0617 | 1.1818 | 0.1022 | 16.5549 | 16.1571 |

#### Top Pair Breakdown

| Pair | Trades | Win % | PF | Exp R | Total R |
| --- | ---: | ---: | ---: | ---: | ---: |
| LTC/USDT:USDT | 20 | 70.0 | 3.2579 | 0.7462 | 14.9248 |
| BTC/USDT:USDT | 11 | 81.8182 | 4.0146 | 0.7966 | 8.7631 |
| APT/USDT:USDT | 8 | 75.0 | 3.7696 | 0.7575 | 6.0597 |
| GALA/USDT:USDT | 8 | 75.0 | 3.6262 | 0.7477 | 5.9819 |
| SEI/USDT:USDT | 7 | 71.4286 | 3.6577 | 0.8385 | 5.8693 |
| ONDO/USDT:USDT | 5 | 80.0 | 5.6997 | 1.0159 | 5.0794 |
| AXS/USDT:USDT | 15 | 53.3333 | 2.0206 | 0.3283 | 4.9246 |
| ADA/USDT:USDT | 13 | 46.1538 | 1.796 | 0.3512 | 4.5654 |

### 1h 空头上影拒绝 ATR1.2

- candidateId: `v13_7_40_1h_short_rejection_1989`
- approved: False
- observationCandidate: True
- approvalTier: observation_candidate
- params: `{"upper_buffer": 0.0, "trend_tolerance": 1.0, "rsi_high": 62, "volume_min": 1.2, "stop_atr": 1.2, "max_hold": 8}`

#### Walk-Forward

| Split | Trades | Pairs | Win % | PF | Exp R | Total R | DD R |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| train | 161 | 31 | 39.7516 | 0.9546 | -0.024 | -3.865 | 20.1913 |
| validation | 140 | 40 | 44.2857 | 0.869 | -0.0723 | -10.128 | 22.0344 |
| test | 152 | 43 | 50.0 | 1.1954 | 0.0953 | 14.4871 | 12.4348 |

#### Top Pair Breakdown

| Pair | Trades | Win % | PF | Exp R | Total R |
| --- | ---: | ---: | ---: | ---: | ---: |
| LTC/USDT:USDT | 19 | 52.6316 | 2.5585 | 0.4741 | 9.0077 |
| BTC/USDT:USDT | 11 | 63.6364 | 3.0404 | 0.5739 | 6.3127 |
| SEI/USDT:USDT | 7 | 71.4286 | 3.5039 | 0.79 | 5.5297 |
| DOGE/USDT:USDT | 18 | 66.6667 | 2.0206 | 0.2944 | 5.2984 |
| APT/USDT:USDT | 7 | 57.1429 | 2.9001 | 0.6639 | 4.647 |
| AXS/USDT:USDT | 15 | 53.3333 | 2.3352 | 0.3011 | 4.5172 |
| ADA/USDT:USDT | 13 | 61.5385 | 1.8386 | 0.3359 | 4.3665 |
| ONDO/USDT:USDT | 5 | 80.0 | 4.641 | 0.787 | 3.9352 |

### 1h 空头上影拒绝 ATR1.2

- candidateId: `v13_7_40_1h_short_rejection_1990`
- approved: False
- observationCandidate: True
- approvalTier: observation_candidate
- params: `{"upper_buffer": 0.0, "trend_tolerance": 1.0, "rsi_high": 62, "volume_min": 1.2, "stop_atr": 1.2, "max_hold": 12}`

#### Walk-Forward

| Split | Trades | Pairs | Win % | PF | Exp R | Total R | DD R |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| train | 161 | 31 | 42.236 | 1.0824 | 0.0468 | 7.5319 | 17.771 |
| validation | 140 | 40 | 40.7143 | 0.9687 | -0.0184 | -2.5807 | 20.7585 |
| test | 152 | 43 | 42.7632 | 1.0623 | 0.0364 | 5.5355 | 17.809 |

#### Top Pair Breakdown

| Pair | Trades | Win % | PF | Exp R | Total R |
| --- | ---: | ---: | ---: | ---: | ---: |
| LTC/USDT:USDT | 19 | 73.6842 | 3.8873 | 0.8418 | 15.9951 |
| BTC/USDT:USDT | 11 | 81.8182 | 4.0146 | 0.7966 | 8.7631 |
| GALA/USDT:USDT | 8 | 75.0 | 3.6262 | 0.7477 | 5.9819 |
| SEI/USDT:USDT | 7 | 71.4286 | 3.6577 | 0.8385 | 5.8693 |
| DOGE/USDT:USDT | 18 | 44.4444 | 1.6795 | 0.2878 | 5.18 |
| ONDO/USDT:USDT | 5 | 80.0 | 5.6997 | 1.0159 | 5.0794 |
| AXS/USDT:USDT | 15 | 53.3333 | 2.0206 | 0.3283 | 4.9246 |
| ADA/USDT:USDT | 13 | 46.1538 | 1.796 | 0.3512 | 4.5654 |

### 1h 空头上影拒绝 ATR1.2

- candidateId: `v13_7_40_1h_short_rejection_2037`
- approved: False
- observationCandidate: False
- approvalTier: rejected
- params: `{"upper_buffer": 0.003, "trend_tolerance": 1.005, "rsi_high": 62, "volume_min": 1.2, "stop_atr": 1.2, "max_hold": 8}`

#### Walk-Forward

| Split | Trades | Pairs | Win % | PF | Exp R | Total R | DD R |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| train | 170 | 31 | 35.2941 | 0.7759 | -0.1286 | -21.8576 | 28.8831 |
| validation | 182 | 43 | 44.5055 | 0.8763 | -0.0695 | -12.6462 | 32.1658 |
| test | 195 | 44 | 49.2308 | 1.2225 | 0.1106 | 21.5731 | 16.0458 |

#### Top Pair Breakdown

| Pair | Trades | Win % | PF | Exp R | Total R |
| --- | ---: | ---: | ---: | ---: | ---: |
| BTC/USDT:USDT | 15 | 66.6667 | 3.0956 | 0.597 | 8.9547 |
| LTC/USDT:USDT | 22 | 50.0 | 2.0926 | 0.3949 | 8.6889 |
| MANA/USDT:USDT | 12 | 66.6667 | 2.494 | 0.5721 | 6.8648 |
| APT/USDT:USDT | 8 | 62.5 | 3.6806 | 0.8195 | 6.5559 |
| AXS/USDT:USDT | 16 | 56.25 | 2.9048 | 0.4028 | 6.4443 |
| DOGE/USDT:USDT | 23 | 60.8696 | 1.6572 | 0.2447 | 5.6279 |
| SEI/USDT:USDT | 7 | 71.4286 | 3.5039 | 0.79 | 5.5297 |
| ADA/USDT:USDT | 15 | 60.0 | 1.8009 | 0.3404 | 5.1062 |

## Top 25 Candidates

| Candidate | TF | Family | Direction | Tier | Strict | Observation | Trades | Pairs | Win % | PF | Exp R | Test PF | Test Exp R | DD R | Failed Checks | Observation Checks |
| --- | --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| 1h 空头上影拒绝 ATR1.2 | 1h | short_rejection | short | observation_candidate | False | True | 473 | 44 | 44.8203 | 1.0056 | 0.0029 | 1.3016 | 0.142 | 27.5951 | total_profit_factor_lt_1_10 | -- |
| 1h 空头上影拒绝 ATR1.2 | 1h | short_rejection | short | observation_candidate | False | True | 473 | 44 | 42.2833 | 1.0521 | 0.0302 | 1.1818 | 0.1022 | 22.9435 | total_profit_factor_lt_1_10 | -- |
| 1h 空头上影拒绝 ATR1.2 | 1h | short_rejection | short | observation_candidate | False | True | 453 | 44 | 44.5916 | 1.0021 | 0.0011 | 1.1954 | 0.0953 | 25.2311 | total_profit_factor_lt_1_10, validation_expectancy_too_negative | -- |
| 1h 空头上影拒绝 ATR1.2 | 1h | short_rejection | short | observation_candidate | False | True | 453 | 44 | 41.9426 | 1.0399 | 0.0232 | 1.0623 | 0.0364 | 20.7585 | total_profit_factor_lt_1_10 | -- |
| 1h 空头上影拒绝 ATR1.2 | 1h | short_rejection | short | rejected | False | False | 547 | 44 | 43.3272 | 0.9564 | -0.0236 | 1.2225 | 0.1106 | 38.086 | total_profit_factor_lt_1_10, validation_expectancy_too_negative, drawdown_gt_35r | observation_total_profit_factor_lt_1_00 |
| 1h 空头上影拒绝 ATR1.6 | 1h | short_rejection | short | rejected | False | False | 468 | 44 | 46.1538 | 0.9413 | -0.0262 | 1.1233 | 0.0513 | 26.7703 | total_profit_factor_lt_1_10 | observation_total_profit_factor_lt_1_00 |
| 1h 空头上影拒绝 ATR1.2 | 1h | short_rejection | short | rejected | False | False | 547 | 44 | 40.585 | 0.9847 | -0.0092 | 1.1007 | 0.0594 | 34.3268 | total_profit_factor_lt_1_10 | observation_total_profit_factor_lt_1_00 |
| 1h 空头上影拒绝 ATR1.6 | 1h | short_rejection | short | rejected | False | False | 450 | 44 | 46.0 | 0.9349 | -0.0289 | 1.0255 | 0.011 | 24.8452 | total_profit_factor_lt_1_10, test_profit_factor_lt_1_05 | observation_total_profit_factor_lt_1_00 |
| 1h 空头上影拒绝 ATR1.2 | 1h | short_rejection | short | rejected | False | False | 521 | 44 | 42.6104 | 0.9284 | -0.0391 | 1.0973 | 0.0504 | 35.9933 | total_profit_factor_lt_1_10, validation_expectancy_too_negative, drawdown_gt_35r | observation_total_profit_factor_lt_1_00 |
| 1h 空头上影拒绝 ATR1.6 | 1h | short_rejection | short | rejected | False | False | 541 | 44 | 44.9168 | 0.9122 | -0.0407 | 1.0896 | 0.0394 | 35.5773 | total_profit_factor_lt_1_10, validation_expectancy_too_negative, drawdown_gt_35r | observation_total_profit_factor_lt_1_00 |
| 1h 空头上影拒绝 ATR1.6 | 1h | short_rejection | short | rejected | False | False | 468 | 44 | 43.5897 | 0.962 | -0.0194 | 0.9501 | -0.0255 | 23.5066 | total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive | observation_total_profit_factor_lt_1_00, observation_test_profit_factor_lt_1_00, observation_test_expectancy_not_positive |
| 1h 空头上影拒绝 ATR1.6 | 1h | short_rejection | short | rejected | False | False | 450 | 44 | 43.3333 | 0.9655 | -0.0176 | 0.8899 | -0.0577 | 23.0317 | total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive | observation_total_profit_factor_lt_1_00, observation_test_profit_factor_lt_1_00, observation_test_expectancy_not_positive |
| 1h 空头上影拒绝 ATR1.6 | 1h | short_rejection | short | rejected | False | False | 541 | 44 | 42.1442 | 0.9265 | -0.0391 | 0.9598 | -0.0211 | 31.3022 | total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive, validation_expectancy_too_negative | observation_total_profit_factor_lt_1_00, observation_test_profit_factor_lt_1_00, observation_test_expectancy_not_positive |
| 1h 空头上影拒绝 ATR1.2 | 1h | short_rejection | short | rejected | False | False | 521 | 44 | 39.7313 | 0.9478 | -0.0318 | 0.971 | -0.0179 | 33.0075 | total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive, validation_expectancy_too_negative | observation_total_profit_factor_lt_1_00, observation_test_profit_factor_lt_1_00, observation_test_expectancy_not_positive |
| 1h 空头上影拒绝 ATR1.0 | 1h | short_rejection | short | rejected | False | False | 832 | 44 | 38.8221 | 0.9455 | -0.037 | 1.1163 | 0.075 | 60.6004 | total_profit_factor_lt_1_10, validation_expectancy_too_negative, drawdown_gt_35r | observation_total_profit_factor_lt_1_00, observation_drawdown_gt_45r |
| 1h 空头上影拒绝 ATR1.6 | 1h | short_rejection | short | rejected | False | False | 518 | 44 | 44.4015 | 0.8856 | -0.0532 | 0.9662 | -0.0155 | 37.5353 | total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive, validation_expectancy_too_negative, drawdown_gt_35r | observation_total_profit_factor_lt_1_00, observation_test_profit_factor_lt_1_00, observation_test_expectancy_not_positive |
| 1h 空头上影拒绝 ATR1.0 | 1h | short_rejection | short | rejected | False | False | 864 | 44 | 38.4259 | 0.9346 | -0.0446 | 1.086 | 0.056 | 63.8096 | total_profit_factor_lt_1_10, validation_expectancy_too_negative, drawdown_gt_35r | observation_total_profit_factor_lt_1_00, observation_drawdown_gt_45r |
| 1h 空头上影拒绝 ATR1.0 | 1h | short_rejection | short | rejected | False | False | 832 | 44 | 39.3029 | 0.93 | -0.0463 | 1.1291 | 0.0793 | 67.9006 | total_profit_factor_lt_1_10, validation_expectancy_too_negative, drawdown_gt_35r | observation_total_profit_factor_lt_1_00, observation_drawdown_gt_45r |
| 1h 空头上影拒绝 ATR1.6 | 1h | short_rejection | short | rejected | False | False | 518 | 44 | 41.5058 | 0.9075 | -0.0494 | 0.8729 | -0.069 | 37.6172 | total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive, validation_expectancy_too_negative, drawdown_gt_35r | observation_total_profit_factor_lt_1_00, observation_test_profit_factor_lt_1_00, observation_test_expectancy_not_positive |
| 1h 空头上影拒绝 ATR1.0 | 1h | short_rejection | short | rejected | False | False | 832 | 44 | 40.8654 | 0.9047 | -0.0592 | 1.1193 | 0.0683 | 75.4746 | total_profit_factor_lt_1_10, validation_expectancy_too_negative, drawdown_gt_35r | observation_total_profit_factor_lt_1_00, observation_drawdown_gt_45r |
| 1h 空头上影拒绝 ATR1.0 | 1h | short_rejection | short | rejected | False | False | 864 | 44 | 38.8889 | 0.9171 | -0.0552 | 1.0953 | 0.0593 | 72.485 | total_profit_factor_lt_1_10, validation_expectancy_too_negative, drawdown_gt_35r | observation_total_profit_factor_lt_1_00, observation_drawdown_gt_45r |
| 1h 空头上影拒绝 ATR1.2 | 1h | short_rejection | short | rejected | False | False | 824 | 44 | 39.0777 | 0.9215 | -0.051 | 0.962 | -0.0247 | 61.2478 | total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive, validation_expectancy_too_negative, drawdown_gt_35r | observation_total_profit_factor_lt_1_00, observation_test_profit_factor_lt_1_00, observation_test_expectancy_not_positive, observation_drawdown_gt_45r |
| 1h 空头上影拒绝 ATR1.4 | 1h | short_rejection | short | rejected | False | False | 819 | 44 | 44.0781 | 0.8851 | -0.0588 | 1.0138 | 0.0067 | 64.7576 | total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, validation_expectancy_too_negative, drawdown_gt_35r | observation_total_profit_factor_lt_1_00, observation_drawdown_gt_45r |
| 1h 空头上影拒绝 ATR1.0 | 1h | short_rejection | short | rejected | False | False | 864 | 44 | 40.5093 | 0.8973 | -0.0643 | 1.0953 | 0.055 | 77.8196 | total_profit_factor_lt_1_10, validation_expectancy_too_negative, drawdown_gt_35r | observation_total_profit_factor_lt_1_00, observation_drawdown_gt_45r |
| 1h 空头上影拒绝 ATR1.2 | 1h | short_rejection | short | rejected | False | False | 824 | 44 | 42.7184 | 0.8982 | -0.0573 | 1.0358 | 0.0192 | 70.4704 | total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, validation_expectancy_too_negative, drawdown_gt_35r | observation_total_profit_factor_lt_1_00, observation_drawdown_gt_45r |

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
