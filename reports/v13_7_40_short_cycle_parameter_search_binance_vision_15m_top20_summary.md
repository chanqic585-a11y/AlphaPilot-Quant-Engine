# AlphaPilot V13.7.40 Short-Cycle Parameter Search

This report searches short-cycle public-OHLCV research candidates with fixed 2R exits.
It is not exchange dry-run, not live trading, not an order, and not trading advice.

## Summary

- status: completed
- candidateCount: 672
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

- 15m: 20 pairs

## Selected Candidates

| Candidate | TF | Family | Direction | Tier | Strict | Observation | Trades | Pairs | Win % | PF | Exp R | Test PF | Test Exp R | DD R | Failed Checks | Observation Checks |
| --- | --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| 15m 放量回踩修复 ATR1.3 | 15m | volume_rebound_long | long | rejected | False | False | 6952 | 20 | 31.8182 | 0.6085 | -0.3201 | 0.5923 | -0.3378 | 2226.1681 | total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive, validation_expectancy_too_negative, drawdown_gt_35r | observation_total_profit_factor_lt_1_00, observation_test_profit_factor_lt_1_00, observation_test_expectancy_not_positive, observation_validation_expectancy_too_negative, observation_drawdown_gt_45r |
| 15m 放量回踩修复 ATR1.3 | 15m | volume_rebound_long | long | rejected | False | False | 6952 | 20 | 31.8182 | 0.6085 | -0.3201 | 0.5923 | -0.3378 | 2226.1681 | total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive, validation_expectancy_too_negative, drawdown_gt_35r | observation_total_profit_factor_lt_1_00, observation_test_profit_factor_lt_1_00, observation_test_expectancy_not_positive, observation_validation_expectancy_too_negative, observation_drawdown_gt_45r |
| 15m 放量回踩修复 ATR1.3 | 15m | volume_rebound_long | long | rejected | False | False | 6933 | 20 | 30.9534 | 0.6103 | -0.3292 | 0.5868 | -0.3533 | 2282.7172 | total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive, validation_expectancy_too_negative, drawdown_gt_35r | observation_total_profit_factor_lt_1_00, observation_test_profit_factor_lt_1_00, observation_test_expectancy_not_positive, observation_validation_expectancy_too_negative, observation_drawdown_gt_45r |
| 15m 放量回踩修复 ATR1.3 | 15m | volume_rebound_long | long | rejected | False | False | 6933 | 20 | 30.9534 | 0.6103 | -0.3292 | 0.5868 | -0.3533 | 2282.7172 | total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive, validation_expectancy_too_negative, drawdown_gt_35r | observation_total_profit_factor_lt_1_00, observation_test_profit_factor_lt_1_00, observation_test_expectancy_not_positive, observation_validation_expectancy_too_negative, observation_drawdown_gt_45r |
| 15m 放量回踩修复 ATR1.3 | 15m | volume_rebound_long | long | rejected | False | False | 7415 | 20 | 31.5846 | 0.6071 | -0.3208 | 0.5995 | -0.3297 | 2379.4474 | total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive, validation_expectancy_too_negative, drawdown_gt_35r | observation_total_profit_factor_lt_1_00, observation_test_profit_factor_lt_1_00, observation_test_expectancy_not_positive, observation_validation_expectancy_too_negative, observation_drawdown_gt_45r |

### 15m 放量回踩修复 ATR1.3

- candidateId: `v13_7_40_15m_volume_rebound_long_519`
- approved: False
- observationCandidate: False
- approvalTier: rejected
- params: `{"volume_min": 2.3, "rsi_min": 34, "rsi_max": 62, "ema_touch_pct": 0.003, "trend_tolerance": 1.0, "stop_atr": 1.3, "max_hold": 16}`

#### Walk-Forward

| Split | Trades | Pairs | Win % | PF | Exp R | Total R | DD R |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| train | 2745 | 19 | 32.0219 | 0.6424 | -0.2822 | -774.5777 | 777.6698 |
| validation | 2099 | 20 | 32.0629 | 0.5829 | -0.352 | -738.9289 | 766.9167 |
| test | 2108 | 20 | 31.3093 | 0.5923 | -0.3378 | -712.0982 | 722.5481 |

#### Top Pair Breakdown

| Pair | Trades | Win % | PF | Exp R | Total R |
| --- | ---: | ---: | ---: | ---: | ---: |
| ENA/USDT:USDT | 117 | 35.8974 | 0.8456 | -0.1106 | -12.9424 |
| ARB/USDT:USDT | 171 | 34.5029 | 0.711 | -0.2236 | -38.2276 |
| GALA/USDT:USDT | 216 | 30.5556 | 0.6782 | -0.2512 | -54.2673 |
| INJ/USDT:USDT | 260 | 31.9231 | 0.6955 | -0.2346 | -60.9891 |
| GMT/USDT:USDT | 292 | 33.2192 | 0.7082 | -0.2216 | -64.7093 |
| FIL/USDT:USDT | 320 | 34.6875 | 0.7283 | -0.2051 | -65.6231 |
| AVAX/USDT:USDT | 279 | 31.8996 | 0.6749 | -0.2626 | -73.2728 |
| APT/USDT:USDT | 225 | 28.0 | 0.5603 | -0.3597 | -80.9285 |

### 15m 放量回踩修复 ATR1.3

- candidateId: `v13_7_40_15m_volume_rebound_long_551`
- approved: False
- observationCandidate: False
- approvalTier: rejected
- params: `{"volume_min": 2.3, "rsi_min": 40, "rsi_max": 62, "ema_touch_pct": 0.003, "trend_tolerance": 1.0, "stop_atr": 1.3, "max_hold": 16}`

#### Walk-Forward

| Split | Trades | Pairs | Win % | PF | Exp R | Total R | DD R |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| train | 2745 | 19 | 32.0219 | 0.6424 | -0.2822 | -774.5777 | 777.6698 |
| validation | 2099 | 20 | 32.0629 | 0.5829 | -0.352 | -738.9289 | 766.9167 |
| test | 2108 | 20 | 31.3093 | 0.5923 | -0.3378 | -712.0982 | 722.5481 |

#### Top Pair Breakdown

| Pair | Trades | Win % | PF | Exp R | Total R |
| --- | ---: | ---: | ---: | ---: | ---: |
| ENA/USDT:USDT | 117 | 35.8974 | 0.8456 | -0.1106 | -12.9424 |
| ARB/USDT:USDT | 171 | 34.5029 | 0.711 | -0.2236 | -38.2276 |
| GALA/USDT:USDT | 216 | 30.5556 | 0.6782 | -0.2512 | -54.2673 |
| INJ/USDT:USDT | 260 | 31.9231 | 0.6955 | -0.2346 | -60.9891 |
| GMT/USDT:USDT | 292 | 33.2192 | 0.7082 | -0.2216 | -64.7093 |
| FIL/USDT:USDT | 320 | 34.6875 | 0.7283 | -0.2051 | -65.6231 |
| AVAX/USDT:USDT | 279 | 31.8996 | 0.6749 | -0.2626 | -73.2728 |
| APT/USDT:USDT | 225 | 28.0 | 0.5603 | -0.3597 | -80.9285 |

### 15m 放量回踩修复 ATR1.3

- candidateId: `v13_7_40_15m_volume_rebound_long_520`
- approved: False
- observationCandidate: False
- approvalTier: rejected
- params: `{"volume_min": 2.3, "rsi_min": 34, "rsi_max": 62, "ema_touch_pct": 0.003, "trend_tolerance": 1.0, "stop_atr": 1.3, "max_hold": 24}`

#### Walk-Forward

| Split | Trades | Pairs | Win % | PF | Exp R | Total R | DD R |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| train | 2739 | 19 | 31.3618 | 0.6461 | -0.29 | -794.2403 | 797.3325 |
| validation | 2093 | 20 | 31.247 | 0.5894 | -0.3565 | -746.2557 | 769.4527 |
| test | 2101 | 20 | 30.1285 | 0.5868 | -0.3533 | -742.1878 | 749.8738 |

#### Top Pair Breakdown

| Pair | Trades | Win % | PF | Exp R | Total R |
| --- | ---: | ---: | ---: | ---: | ---: |
| ENA/USDT:USDT | 117 | 33.3333 | 0.8226 | -0.1309 | -15.3189 |
| ARB/USDT:USDT | 171 | 33.3333 | 0.7142 | -0.2262 | -38.6829 |
| GALA/USDT:USDT | 216 | 31.0185 | 0.6823 | -0.2521 | -54.4451 |
| INJ/USDT:USDT | 259 | 31.2741 | 0.6963 | -0.2403 | -62.2444 |
| AVAX/USDT:USDT | 279 | 31.8996 | 0.6942 | -0.2528 | -70.5253 |
| FIL/USDT:USDT | 319 | 32.9154 | 0.7092 | -0.2286 | -72.934 |
| GMT/USDT:USDT | 290 | 32.069 | 0.6846 | -0.2515 | -72.9437 |
| APT/USDT:USDT | 225 | 27.5556 | 0.5523 | -0.3753 | -84.434 |

### 15m 放量回踩修复 ATR1.3

- candidateId: `v13_7_40_15m_volume_rebound_long_552`
- approved: False
- observationCandidate: False
- approvalTier: rejected
- params: `{"volume_min": 2.3, "rsi_min": 40, "rsi_max": 62, "ema_touch_pct": 0.003, "trend_tolerance": 1.0, "stop_atr": 1.3, "max_hold": 24}`

#### Walk-Forward

| Split | Trades | Pairs | Win % | PF | Exp R | Total R | DD R |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| train | 2739 | 19 | 31.3618 | 0.6461 | -0.29 | -794.2403 | 797.3325 |
| validation | 2093 | 20 | 31.247 | 0.5894 | -0.3565 | -746.2557 | 769.4527 |
| test | 2101 | 20 | 30.1285 | 0.5868 | -0.3533 | -742.1878 | 749.8738 |

#### Top Pair Breakdown

| Pair | Trades | Win % | PF | Exp R | Total R |
| --- | ---: | ---: | ---: | ---: | ---: |
| ENA/USDT:USDT | 117 | 33.3333 | 0.8226 | -0.1309 | -15.3189 |
| ARB/USDT:USDT | 171 | 33.3333 | 0.7142 | -0.2262 | -38.6829 |
| GALA/USDT:USDT | 216 | 31.0185 | 0.6823 | -0.2521 | -54.4451 |
| INJ/USDT:USDT | 259 | 31.2741 | 0.6963 | -0.2403 | -62.2444 |
| AVAX/USDT:USDT | 279 | 31.8996 | 0.6942 | -0.2528 | -70.5253 |
| FIL/USDT:USDT | 319 | 32.9154 | 0.7092 | -0.2286 | -72.934 |
| GMT/USDT:USDT | 290 | 32.069 | 0.6846 | -0.2515 | -72.9437 |
| APT/USDT:USDT | 225 | 27.5556 | 0.5523 | -0.3753 | -84.434 |

### 15m 放量回踩修复 ATR1.3

- candidateId: `v13_7_40_15m_volume_rebound_long_527`
- approved: False
- observationCandidate: False
- approvalTier: rejected
- params: `{"volume_min": 2.3, "rsi_min": 34, "rsi_max": 62, "ema_touch_pct": 0.008, "trend_tolerance": 1.0, "stop_atr": 1.3, "max_hold": 16}`

#### Walk-Forward

| Split | Trades | Pairs | Win % | PF | Exp R | Total R | DD R |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| train | 2968 | 19 | 31.4016 | 0.6312 | -0.2923 | -867.6686 | 870.7608 |
| validation | 2213 | 20 | 31.9476 | 0.5842 | -0.3501 | -774.6819 | 795.8992 |
| test | 2234 | 20 | 31.4682 | 0.5995 | -0.3297 | -736.5335 | 745.4847 |

#### Top Pair Breakdown

| Pair | Trades | Win % | PF | Exp R | Total R |
| --- | ---: | ---: | ---: | ---: | ---: |
| ENA/USDT:USDT | 126 | 35.7143 | 0.8318 | -0.121 | -15.2453 |
| ARB/USDT:USDT | 197 | 34.0102 | 0.7088 | -0.2264 | -44.61 |
| GALA/USDT:USDT | 231 | 30.303 | 0.6775 | -0.2508 | -57.9384 |
| INJ/USDT:USDT | 292 | 31.1644 | 0.6823 | -0.2457 | -71.739 |
| GMT/USDT:USDT | 318 | 33.0189 | 0.7 | -0.2292 | -72.8924 |
| AVAX/USDT:USDT | 297 | 32.3232 | 0.6856 | -0.2522 | -74.8919 |
| APE/USDT:USDT | 285 | 31.9298 | 0.6175 | -0.2962 | -84.4115 |
| FIL/USDT:USDT | 349 | 32.6648 | 0.6717 | -0.2541 | -88.6772 |

## Top 25 Candidates

| Candidate | TF | Family | Direction | Tier | Strict | Observation | Trades | Pairs | Win % | PF | Exp R | Test PF | Test Exp R | DD R | Failed Checks | Observation Checks |
| --- | --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| 15m 放量回踩修复 ATR1.3 | 15m | volume_rebound_long | long | rejected | False | False | 6952 | 20 | 31.8182 | 0.6085 | -0.3201 | 0.5923 | -0.3378 | 2226.1681 | total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive, validation_expectancy_too_negative, drawdown_gt_35r | observation_total_profit_factor_lt_1_00, observation_test_profit_factor_lt_1_00, observation_test_expectancy_not_positive, observation_validation_expectancy_too_negative, observation_drawdown_gt_45r |
| 15m 放量回踩修复 ATR1.3 | 15m | volume_rebound_long | long | rejected | False | False | 6952 | 20 | 31.8182 | 0.6085 | -0.3201 | 0.5923 | -0.3378 | 2226.1681 | total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive, validation_expectancy_too_negative, drawdown_gt_35r | observation_total_profit_factor_lt_1_00, observation_test_profit_factor_lt_1_00, observation_test_expectancy_not_positive, observation_validation_expectancy_too_negative, observation_drawdown_gt_45r |
| 15m 放量回踩修复 ATR1.3 | 15m | volume_rebound_long | long | rejected | False | False | 6933 | 20 | 30.9534 | 0.6103 | -0.3292 | 0.5868 | -0.3533 | 2282.7172 | total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive, validation_expectancy_too_negative, drawdown_gt_35r | observation_total_profit_factor_lt_1_00, observation_test_profit_factor_lt_1_00, observation_test_expectancy_not_positive, observation_validation_expectancy_too_negative, observation_drawdown_gt_45r |
| 15m 放量回踩修复 ATR1.3 | 15m | volume_rebound_long | long | rejected | False | False | 6933 | 20 | 30.9534 | 0.6103 | -0.3292 | 0.5868 | -0.3533 | 2282.7172 | total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive, validation_expectancy_too_negative, drawdown_gt_35r | observation_total_profit_factor_lt_1_00, observation_test_profit_factor_lt_1_00, observation_test_expectancy_not_positive, observation_validation_expectancy_too_negative, observation_drawdown_gt_45r |
| 15m 放量回踩修复 ATR1.3 | 15m | volume_rebound_long | long | rejected | False | False | 7415 | 20 | 31.5846 | 0.6071 | -0.3208 | 0.5995 | -0.3297 | 2379.4474 | total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive, validation_expectancy_too_negative, drawdown_gt_35r | observation_total_profit_factor_lt_1_00, observation_test_profit_factor_lt_1_00, observation_test_expectancy_not_positive, observation_validation_expectancy_too_negative, observation_drawdown_gt_45r |
| 15m 放量回踩修复 ATR1.3 | 15m | volume_rebound_long | long | rejected | False | False | 7415 | 20 | 31.5846 | 0.6071 | -0.3208 | 0.5995 | -0.3297 | 2379.4474 | total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive, validation_expectancy_too_negative, drawdown_gt_35r | observation_total_profit_factor_lt_1_00, observation_test_profit_factor_lt_1_00, observation_test_expectancy_not_positive, observation_validation_expectancy_too_negative, observation_drawdown_gt_45r |
| 15m 放量回踩修复 ATR1.3 | 15m | volume_rebound_long | long | rejected | False | False | 7392 | 20 | 30.79 | 0.6087 | -0.3301 | 0.5914 | -0.3479 | 2440.2381 | total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive, validation_expectancy_too_negative, drawdown_gt_35r | observation_total_profit_factor_lt_1_00, observation_test_profit_factor_lt_1_00, observation_test_expectancy_not_positive, observation_validation_expectancy_too_negative, observation_drawdown_gt_45r |
| 15m 放量回踩修复 ATR1.3 | 15m | volume_rebound_long | long | rejected | False | False | 7392 | 20 | 30.79 | 0.6087 | -0.3301 | 0.5914 | -0.3479 | 2440.2381 | total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive, validation_expectancy_too_negative, drawdown_gt_35r | observation_total_profit_factor_lt_1_00, observation_test_profit_factor_lt_1_00, observation_test_expectancy_not_positive, observation_validation_expectancy_too_negative, observation_drawdown_gt_45r |
| 15m 放量回踩修复 ATR1.0 | 15m | volume_rebound_long | long | rejected | False | False | 7050 | 20 | 30.1986 | 0.5524 | -0.4106 | 0.5332 | -0.4343 | 2896.7739 | total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive, validation_expectancy_too_negative, drawdown_gt_35r | observation_total_profit_factor_lt_1_00, observation_test_profit_factor_lt_1_00, observation_test_expectancy_not_positive, observation_validation_expectancy_too_negative, observation_drawdown_gt_45r |
| 15m 放量回踩修复 ATR1.0 | 15m | volume_rebound_long | long | rejected | False | False | 7050 | 20 | 30.1986 | 0.5524 | -0.4106 | 0.5332 | -0.4343 | 2896.7739 | total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive, validation_expectancy_too_negative, drawdown_gt_35r | observation_total_profit_factor_lt_1_00, observation_test_profit_factor_lt_1_00, observation_test_expectancy_not_positive, observation_validation_expectancy_too_negative, observation_drawdown_gt_45r |
| 15m 放量回踩修复 ATR1.0 | 15m | volume_rebound_long | long | rejected | False | False | 7057 | 20 | 30.3528 | 0.5479 | -0.4107 | 0.5355 | -0.4278 | 2900.3207 | total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive, validation_expectancy_too_negative, drawdown_gt_35r | observation_total_profit_factor_lt_1_00, observation_test_profit_factor_lt_1_00, observation_test_expectancy_not_positive, observation_validation_expectancy_too_negative, observation_drawdown_gt_45r |
| 15m 放量回踩修复 ATR1.0 | 15m | volume_rebound_long | long | rejected | False | False | 7057 | 20 | 30.3528 | 0.5479 | -0.4107 | 0.5355 | -0.4278 | 2900.3207 | total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive, validation_expectancy_too_negative, drawdown_gt_35r | observation_total_profit_factor_lt_1_00, observation_test_profit_factor_lt_1_00, observation_test_expectancy_not_positive, observation_validation_expectancy_too_negative, observation_drawdown_gt_45r |
| 15m 放量回踩修复 ATR1.0 | 15m | volume_rebound_long | long | rejected | False | False | 7540 | 20 | 30.1857 | 0.5482 | -0.4091 | 0.5379 | -0.4239 | 3086.5782 | total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive, validation_expectancy_too_negative, drawdown_gt_35r | observation_total_profit_factor_lt_1_00, observation_test_profit_factor_lt_1_00, observation_test_expectancy_not_positive, observation_validation_expectancy_too_negative, observation_drawdown_gt_45r |
| 15m 放量回踩修复 ATR1.0 | 15m | volume_rebound_long | long | rejected | False | False | 7540 | 20 | 30.1857 | 0.5482 | -0.4091 | 0.5379 | -0.4239 | 3086.5782 | total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive, validation_expectancy_too_negative, drawdown_gt_35r | observation_total_profit_factor_lt_1_00, observation_test_profit_factor_lt_1_00, observation_test_expectancy_not_positive, observation_validation_expectancy_too_negative, observation_drawdown_gt_45r |
| 15m 放量回踩修复 ATR1.0 | 15m | volume_rebound_long | long | rejected | False | False | 7533 | 20 | 30.0013 | 0.5517 | -0.4102 | 0.5341 | -0.4322 | 3091.5058 | total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive, validation_expectancy_too_negative, drawdown_gt_35r | observation_total_profit_factor_lt_1_00, observation_test_profit_factor_lt_1_00, observation_test_expectancy_not_positive, observation_validation_expectancy_too_negative, observation_drawdown_gt_45r |
| 15m 放量回踩修复 ATR1.0 | 15m | volume_rebound_long | long | rejected | False | False | 7533 | 20 | 30.0013 | 0.5517 | -0.4102 | 0.5341 | -0.4322 | 3091.5058 | total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive, validation_expectancy_too_negative, drawdown_gt_35r | observation_total_profit_factor_lt_1_00, observation_test_profit_factor_lt_1_00, observation_test_expectancy_not_positive, observation_validation_expectancy_too_negative, observation_drawdown_gt_45r |
| 15m 放量回踩修复 ATR1.3 | 15m | volume_rebound_long | long | rejected | False | False | 9570 | 20 | 31.3584 | 0.5758 | -0.355 | 0.5725 | -0.3575 | 3397.4553 | total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive, validation_expectancy_too_negative, drawdown_gt_35r | observation_total_profit_factor_lt_1_00, observation_test_profit_factor_lt_1_00, observation_test_expectancy_not_positive, observation_validation_expectancy_too_negative, observation_drawdown_gt_45r |
| 15m 放量回踩修复 ATR1.3 | 15m | volume_rebound_long | long | rejected | False | False | 9570 | 20 | 31.3584 | 0.5758 | -0.355 | 0.5725 | -0.3575 | 3397.4553 | total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive, validation_expectancy_too_negative, drawdown_gt_35r | observation_total_profit_factor_lt_1_00, observation_test_profit_factor_lt_1_00, observation_test_expectancy_not_positive, observation_validation_expectancy_too_negative, observation_drawdown_gt_45r |
| 15m 放量突破延续 ATR1.6 | 15m | breakout_volume_long | long | rejected | False | False | 16163 | 20 | 33.0508 | 0.7086 | -0.2152 | 0.669 | -0.2504 | 3501.508 | total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive, validation_expectancy_too_negative, drawdown_gt_35r | observation_total_profit_factor_lt_1_00, observation_test_profit_factor_lt_1_00, observation_test_expectancy_not_positive, observation_drawdown_gt_45r |
| 15m 放量突破延续 ATR1.6 | 15m | breakout_volume_long | long | rejected | False | False | 16295 | 20 | 33.9675 | 0.6943 | -0.2141 | 0.6501 | -0.2511 | 3501.6092 | total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive, validation_expectancy_too_negative, drawdown_gt_35r | observation_total_profit_factor_lt_1_00, observation_test_profit_factor_lt_1_00, observation_test_expectancy_not_positive, observation_drawdown_gt_45r |
| 15m 放量回踩修复 ATR1.3 | 15m | volume_rebound_long | long | rejected | False | False | 9542 | 20 | 30.6016 | 0.5804 | -0.3629 | 0.5706 | -0.3714 | 3462.6157 | total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive, validation_expectancy_too_negative, drawdown_gt_35r | observation_total_profit_factor_lt_1_00, observation_test_profit_factor_lt_1_00, observation_test_expectancy_not_positive, observation_validation_expectancy_too_negative, observation_drawdown_gt_45r |
| 15m 放量回踩修复 ATR1.3 | 15m | volume_rebound_long | long | rejected | False | False | 9542 | 20 | 30.6016 | 0.5804 | -0.3629 | 0.5706 | -0.3714 | 3462.6157 | total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive, validation_expectancy_too_negative, drawdown_gt_35r | observation_total_profit_factor_lt_1_00, observation_test_profit_factor_lt_1_00, observation_test_expectancy_not_positive, observation_validation_expectancy_too_negative, observation_drawdown_gt_45r |
| 15m 放量回踩修复 ATR1.3 | 15m | volume_rebound_long | long | rejected | False | False | 10144 | 20 | 31.1909 | 0.5766 | -0.3534 | 0.5778 | -0.3512 | 3585.8758 | total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive, validation_expectancy_too_negative, drawdown_gt_35r | observation_total_profit_factor_lt_1_00, observation_test_profit_factor_lt_1_00, observation_test_expectancy_not_positive, observation_validation_expectancy_too_negative, observation_drawdown_gt_45r |
| 15m 放量回踩修复 ATR1.3 | 15m | volume_rebound_long | long | rejected | False | False | 10144 | 20 | 31.1909 | 0.5766 | -0.3534 | 0.5778 | -0.3512 | 3585.8758 | total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive, validation_expectancy_too_negative, drawdown_gt_35r | observation_total_profit_factor_lt_1_00, observation_test_profit_factor_lt_1_00, observation_test_expectancy_not_positive, observation_validation_expectancy_too_negative, observation_drawdown_gt_45r |
| 15m 放量回踩修复 ATR1.3 | 15m | volume_rebound_long | long | rejected | False | False | 10112 | 20 | 30.4688 | 0.5805 | -0.3619 | 0.573 | -0.3682 | 3659.4639 | total_profit_factor_lt_1_10, test_profit_factor_lt_1_05, test_expectancy_not_positive, validation_expectancy_too_negative, drawdown_gt_35r | observation_total_profit_factor_lt_1_00, observation_test_profit_factor_lt_1_00, observation_test_expectancy_not_positive, observation_validation_expectancy_too_negative, observation_drawdown_gt_45r |

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
