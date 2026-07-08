# AlphaPilot V13.7.40 Short-Cycle Parameter Search

This report searches short-cycle public-OHLCV research candidates with fixed 2R exits.
It is not exchange dry-run, not live trading, not an order, and not trading advice.

## Summary

- status: completed
- candidateCount: 1011
- approvedCount: 33
- observationCandidateCount: 54
- selectedCount: 5
- approvedSelectedCount: 5
- observationSelectedCount: 0
- targetR: 2.0
- feeRate: 0.0005
- slippageRate: 0.0005
- timerange: 20200101-

## Data Coverage

- 1h: 44 pairs

## Selected Candidates

| Candidate | TF | Family | Direction | Tier | Asset Filter | Strict | Observation | Trades | Pairs | Win % | PF | Exp R | Test PF | Test Exp R | DD R | Failed Checks | Observation Checks |
| --- | --- | --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| 1h 空头上影拒绝 ATR1.0 资产筛选Top10 | 1h | short_rejection | short | strict_approved_asset_filtered | Top10 | True | True | 219 | 10 | 51.1416 | 1.517 | 0.2818 | 1.5075 | 0.285 | 10.9678 | -- | -- |
| 1h 空头上影拒绝 ATR1.0 资产筛选Top10 | 1h | short_rejection | short | strict_approved_asset_filtered | Top10 | True | True | 219 | 10 | 49.3151 | 1.4348 | 0.2273 | 1.5031 | 0.2749 | 11.8513 | -- | -- |
| 1h 空头上影拒绝 ATR1.0 资产筛选Top10 | 1h | short_rejection | short | strict_approved_asset_filtered | Top10 | True | True | 219 | 10 | 49.3151 | 1.5112 | 0.2905 | 1.3785 | 0.2347 | 11.966 | -- | -- |
| 1h 空头上影拒绝 ATR1.0 资产筛选Top8 | 1h | short_rejection | short | strict_approved_asset_filtered | Top8 | True | True | 175 | 8 | 52.0 | 1.5545 | 0.2998 | 1.4233 | 0.2419 | 9.903 | -- | -- |
| 1h 空头上影拒绝 ATR1.2 资产筛选Top10 | 1h | short_rejection | short | strict_approved_asset_filtered | Top10 | True | True | 131 | 10 | 54.9618 | 1.685 | 0.2624 | 1.3186 | 0.1538 | 7.2055 | -- | -- |

### 1h 空头上影拒绝 ATR1.0 资产筛选Top10

- candidateId: `v13_7_40_1h_short_rejection_2149_asset_filter_top10`
- approved: True
- observationCandidate: True
- approvalTier: strict_approved_asset_filtered
- params: `{"upper_buffer": 0.006, "trend_tolerance": 1.0, "rsi_high": 60, "volume_min": 1.2, "stop_atr": 1.0, "max_hold": 12}`
- assetFilter: `{"enabled": true, "selectionMethod": "train_segment_positive_pair_filter", "selectedPairCount": 10, "selectedPairs": ["APE/USDT:USDT", "APT/USDT:USDT", "BTC/USDT:USDT", "GALA/USDT:USDT", "LTC/USDT:USDT", "MANA/USDT:USDT", "NEAR/USDT:USDT", "SAND/USDT:USDT", "SOL/USDT:USDT", "TRX/USDT:USDT"], "minTrainTradesPerPair": 3, "minTrainProfitFactor": 1.05, "requiresPositiveTrainExpectancy": true, "note": "Pairs are selected from the train segment only; validation and test remain out of selection."}`

#### Walk-Forward

| Split | Trades | Pairs | Win % | PF | Exp R | Total R | DD R |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| train | 90 | 10 | 56.6667 | 1.8975 | 0.4388 | 39.4879 | 5.9133 |
| validation | 64 | 10 | 43.75 | 1.0951 | 0.0577 | 3.6951 | 10.9539 |
| test | 65 | 10 | 50.7692 | 1.5075 | 0.285 | 18.5277 | 10.9678 |

#### Top Pair Breakdown

| Pair | Trades | Win % | PF | Exp R | Total R |
| --- | ---: | ---: | ---: | ---: | ---: |
| GALA/USDT:USDT | 25 | 64.0 | 2.562 | 0.629 | 15.7257 |
| LTC/USDT:USDT | 30 | 53.3333 | 1.7487 | 0.4057 | 12.1713 |
| APT/USDT:USDT | 15 | 66.6667 | 3.0111 | 0.7332 | 10.9982 |
| MANA/USDT:USDT | 21 | 52.381 | 1.7429 | 0.3664 | 7.6939 |
| SOL/USDT:USDT | 23 | 52.1739 | 1.4003 | 0.2182 | 5.0177 |
| BTC/USDT:USDT | 21 | 57.1429 | 1.3257 | 0.1926 | 4.0453 |
| TRX/USDT:USDT | 15 | 46.6667 | 1.4996 | 0.2685 | 4.0268 |
| APE/USDT:USDT | 20 | 40.0 | 1.0999 | 0.0634 | 1.2676 |

### 1h 空头上影拒绝 ATR1.0 资产筛选Top10

- candidateId: `v13_7_40_1h_short_rejection_2148_asset_filter_top10`
- approved: True
- observationCandidate: True
- approvalTier: strict_approved_asset_filtered
- params: `{"upper_buffer": 0.006, "trend_tolerance": 1.0, "rsi_high": 60, "volume_min": 1.2, "stop_atr": 1.0, "max_hold": 8}`
- assetFilter: `{"enabled": true, "selectionMethod": "train_segment_positive_pair_filter", "selectedPairCount": 10, "selectedPairs": ["APE/USDT:USDT", "APT/USDT:USDT", "BTC/USDT:USDT", "GALA/USDT:USDT", "LTC/USDT:USDT", "MANA/USDT:USDT", "NEAR/USDT:USDT", "SAND/USDT:USDT", "SOL/USDT:USDT", "TRX/USDT:USDT"], "minTrainTradesPerPair": 3, "minTrainProfitFactor": 1.05, "requiresPositiveTrainExpectancy": true, "note": "Pairs are selected from the train segment only; validation and test remain out of selection."}`

#### Walk-Forward

| Split | Trades | Pairs | Win % | PF | Exp R | Total R | DD R |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| train | 90 | 10 | 52.2222 | 1.7545 | 0.3573 | 32.1584 | 5.9133 |
| validation | 64 | 10 | 42.1875 | 0.993 | -0.004 | -0.2548 | 11.8513 |
| test | 65 | 10 | 52.3077 | 1.5031 | 0.2749 | 17.8667 | 10.3932 |

#### Top Pair Breakdown

| Pair | Trades | Win % | PF | Exp R | Total R |
| --- | ---: | ---: | ---: | ---: | ---: |
| GALA/USDT:USDT | 25 | 64.0 | 2.5136 | 0.5758 | 14.3962 |
| APT/USDT:USDT | 15 | 60.0 | 2.703 | 0.656 | 9.8401 |
| MANA/USDT:USDT | 21 | 57.1429 | 1.7521 | 0.3697 | 7.7647 |
| LTC/USDT:USDT | 30 | 46.6667 | 1.5294 | 0.2519 | 7.556 |
| SOL/USDT:USDT | 23 | 43.4783 | 1.4109 | 0.2118 | 4.8713 |
| BTC/USDT:USDT | 21 | 47.619 | 1.2696 | 0.1517 | 3.1857 |
| SAND/USDT:USDT | 17 | 47.0588 | 1.229 | 0.1352 | 2.2978 |
| TRX/USDT:USDT | 15 | 46.6667 | 1.2041 | 0.1209 | 1.8129 |

### 1h 空头上影拒绝 ATR1.0 资产筛选Top10

- candidateId: `v13_7_40_1h_short_rejection_2150_asset_filter_top10`
- approved: True
- observationCandidate: True
- approvalTier: strict_approved_asset_filtered
- params: `{"upper_buffer": 0.006, "trend_tolerance": 1.0, "rsi_high": 60, "volume_min": 1.2, "stop_atr": 1.0, "max_hold": 16}`
- assetFilter: `{"enabled": true, "selectionMethod": "train_segment_positive_pair_filter", "selectedPairCount": 10, "selectedPairs": ["APE/USDT:USDT", "APT/USDT:USDT", "BTC/USDT:USDT", "GALA/USDT:USDT", "LTC/USDT:USDT", "MANA/USDT:USDT", "NEAR/USDT:USDT", "SAND/USDT:USDT", "SOL/USDT:USDT", "TRX/USDT:USDT"], "minTrainTradesPerPair": 3, "minTrainProfitFactor": 1.05, "requiresPositiveTrainExpectancy": true, "note": "Pairs are selected from the train segment only; validation and test remain out of selection."}`

#### Walk-Forward

| Split | Trades | Pairs | Win % | PF | Exp R | Total R | DD R |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| train | 90 | 10 | 54.4444 | 1.9173 | 0.452 | 40.683 | 5.9133 |
| validation | 64 | 10 | 45.3125 | 1.1929 | 0.1199 | 7.6711 | 8.7007 |
| test | 65 | 10 | 46.1538 | 1.3785 | 0.2347 | 15.2586 | 11.966 |

#### Top Pair Breakdown

| Pair | Trades | Win % | PF | Exp R | Total R |
| --- | ---: | ---: | ---: | ---: | ---: |
| GALA/USDT:USDT | 25 | 64.0 | 3.0253 | 0.8156 | 20.39 |
| APT/USDT:USDT | 15 | 66.6667 | 3.3674 | 0.8631 | 12.9469 |
| LTC/USDT:USDT | 30 | 53.3333 | 1.7304 | 0.3957 | 11.8725 |
| MANA/USDT:USDT | 21 | 57.1429 | 1.8581 | 0.4219 | 8.8595 |
| SOL/USDT:USDT | 23 | 52.1739 | 1.5428 | 0.2959 | 6.8048 |
| TRX/USDT:USDT | 15 | 53.3333 | 1.4146 | 0.2461 | 3.6911 |
| BTC/USDT:USDT | 21 | 42.8571 | 1.0452 | 0.0321 | 0.6751 |
| SAND/USDT:USDT | 17 | 41.1765 | 1.0356 | 0.0233 | 0.3957 |

### 1h 空头上影拒绝 ATR1.0 资产筛选Top8

- candidateId: `v13_7_40_1h_short_rejection_2077_asset_filter_top8`
- approved: True
- observationCandidate: True
- approvalTier: strict_approved_asset_filtered
- params: `{"upper_buffer": 0.003, "trend_tolerance": 1.0, "rsi_high": 60, "volume_min": 1.2, "stop_atr": 1.0, "max_hold": 12}`
- assetFilter: `{"enabled": true, "selectionMethod": "train_segment_positive_pair_filter", "selectedPairCount": 8, "selectedPairs": ["APE/USDT:USDT", "APT/USDT:USDT", "BTC/USDT:USDT", "GALA/USDT:USDT", "LTC/USDT:USDT", "NEAR/USDT:USDT", "SOL/USDT:USDT", "TRX/USDT:USDT"], "minTrainTradesPerPair": 3, "minTrainProfitFactor": 1.05, "requiresPositiveTrainExpectancy": true, "note": "Pairs are selected from the train segment only; validation and test remain out of selection."}`

#### Walk-Forward

| Split | Trades | Pairs | Win % | PF | Exp R | Total R | DD R |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| train | 73 | 8 | 58.9041 | 2.055 | 0.4906 | 35.8128 | 3.5047 |
| validation | 46 | 8 | 43.4783 | 1.1085 | 0.0677 | 3.113 | 8.8535 |
| test | 56 | 8 | 50.0 | 1.4233 | 0.2419 | 13.5464 | 9.903 |

#### Top Pair Breakdown

| Pair | Trades | Win % | PF | Exp R | Total R |
| --- | ---: | ---: | ---: | ---: | ---: |
| GALA/USDT:USDT | 23 | 60.8696 | 2.2925 | 0.5658 | 13.0124 |
| APT/USDT:USDT | 14 | 71.4286 | 3.7386 | 0.8616 | 12.0625 |
| LTC/USDT:USDT | 29 | 51.7241 | 1.6338 | 0.3553 | 10.3025 |
| SOL/USDT:USDT | 22 | 54.5455 | 1.5398 | 0.2797 | 6.1536 |
| BTC/USDT:USDT | 21 | 57.1429 | 1.3257 | 0.1926 | 4.0453 |
| TRX/USDT:USDT | 15 | 46.6667 | 1.4996 | 0.2685 | 4.0268 |
| NEAR/USDT:USDT | 31 | 41.9355 | 1.0828 | 0.0517 | 1.6015 |
| APE/USDT:USDT | 20 | 40.0 | 1.0999 | 0.0634 | 1.2676 |

### 1h 空头上影拒绝 ATR1.2 资产筛选Top10

- candidateId: `v13_7_40_1h_short_rejection_2021_asset_filter_top10`
- approved: True
- observationCandidate: True
- approvalTier: strict_approved_asset_filtered
- params: `{"upper_buffer": 0.003, "trend_tolerance": 1.0, "rsi_high": 62, "volume_min": 1.2, "stop_atr": 1.2, "max_hold": 8}`
- assetFilter: `{"enabled": true, "selectionMethod": "train_segment_positive_pair_filter", "selectedPairCount": 10, "selectedPairs": ["ADA/USDT:USDT", "AXS/USDT:USDT", "BTC/USDT:USDT", "DOGE/USDT:USDT", "GALA/USDT:USDT", "LTC/USDT:USDT", "NEAR/USDT:USDT", "SAND/USDT:USDT", "SOL/USDT:USDT", "TRX/USDT:USDT"], "minTrainTradesPerPair": 3, "minTrainProfitFactor": 1.05, "requiresPositiveTrainExpectancy": true, "note": "Pairs are selected from the train segment only; validation and test remain out of selection."}`

#### Walk-Forward

| Split | Trades | Pairs | Win % | PF | Exp R | Total R | DD R |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| train | 63 | 10 | 52.381 | 1.9439 | 0.3266 | 20.577 | 2.9473 |
| validation | 34 | 10 | 61.7647 | 1.7159 | 0.2521 | 8.5697 | 4.4041 |
| test | 34 | 10 | 52.9412 | 1.3186 | 0.1538 | 5.2281 | 7.2055 |

#### Top Pair Breakdown

| Pair | Trades | Win % | PF | Exp R | Total R |
| --- | ---: | ---: | ---: | ---: | ---: |
| LTC/USDT:USDT | 20 | 50.0 | 2.1588 | 0.3969 | 7.9374 |
| BTC/USDT:USDT | 11 | 63.6364 | 3.0404 | 0.5739 | 6.3127 |
| AXS/USDT:USDT | 15 | 53.3333 | 2.3352 | 0.3011 | 4.5172 |
| ADA/USDT:USDT | 13 | 61.5385 | 1.8386 | 0.3359 | 4.3665 |
| DOGE/USDT:USDT | 19 | 63.1579 | 1.6615 | 0.2198 | 4.1763 |
| GALA/USDT:USDT | 8 | 75.0 | 2.5748 | 0.4484 | 3.587 |
| TRX/USDT:USDT | 7 | 57.1429 | 2.1499 | 0.4988 | 3.4917 |
| NEAR/USDT:USDT | 13 | 61.5385 | 1.1802 | 0.0762 | 0.99 |

## Top 25 Candidates

| Candidate | TF | Family | Direction | Tier | Asset Filter | Strict | Observation | Trades | Pairs | Win % | PF | Exp R | Test PF | Test Exp R | DD R | Failed Checks | Observation Checks |
| --- | --- | --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| 1h 空头上影拒绝 ATR1.0 资产筛选Top10 | 1h | short_rejection | short | strict_approved_asset_filtered | Top10 | True | True | 219 | 10 | 51.1416 | 1.517 | 0.2818 | 1.5075 | 0.285 | 10.9678 | -- | -- |
| 1h 空头上影拒绝 ATR1.0 资产筛选Top10 | 1h | short_rejection | short | strict_approved_asset_filtered | Top10 | True | True | 219 | 10 | 49.3151 | 1.4348 | 0.2273 | 1.5031 | 0.2749 | 11.8513 | -- | -- |
| 1h 空头上影拒绝 ATR1.0 资产筛选Top10 | 1h | short_rejection | short | strict_approved_asset_filtered | Top10 | True | True | 219 | 10 | 49.3151 | 1.5112 | 0.2905 | 1.3785 | 0.2347 | 11.966 | -- | -- |
| 1h 空头上影拒绝 ATR1.0 资产筛选Top8 | 1h | short_rejection | short | strict_approved_asset_filtered | Top8 | True | True | 175 | 8 | 52.0 | 1.5545 | 0.2998 | 1.4233 | 0.2419 | 9.903 | -- | -- |
| 1h 空头上影拒绝 ATR1.2 资产筛选Top10 | 1h | short_rejection | short | strict_approved_asset_filtered | Top10 | True | True | 131 | 10 | 54.9618 | 1.685 | 0.2624 | 1.3186 | 0.1538 | 7.2055 | -- | -- |
| 1h 空头上影拒绝 ATR1.2 资产筛选Top8 | 1h | short_rejection | short | strict_approved_asset_filtered | Top8 | True | True | 219 | 8 | 48.8584 | 1.4175 | 0.2162 | 1.4174 | 0.2304 | 10.2656 | -- | -- |
| 1h 空头上影拒绝 ATR1.2 资产筛选Top8 | 1h | short_rejection | short | strict_approved_asset_filtered | Top8 | True | True | 227 | 8 | 48.8987 | 1.4043 | 0.2135 | 1.4374 | 0.2483 | 13.5327 | -- | -- |
| 1h 空头上影拒绝 ATR1.0 资产筛选Top10 | 1h | short_rejection | short | observation_candidate_asset_filtered | Top10 | False | True | 207 | 10 | 48.3092 | 1.3517 | 0.1843 | 1.4572 | 0.2499 | 13.8024 | validation_expectancy_too_negative | -- |
| 1h 空头上影拒绝 ATR1.0 资产筛选Top8 | 1h | short_rejection | short | strict_approved_asset_filtered | Top8 | True | True | 177 | 8 | 50.2825 | 1.4661 | 0.2585 | 1.3491 | 0.2031 | 9.0059 | -- | -- |
| 1h 空头上影拒绝 ATR1.0 资产筛选Top8 | 1h | short_rejection | short | strict_approved_asset_filtered | Top8 | True | True | 175 | 8 | 49.1429 | 1.5206 | 0.2967 | 1.287 | 0.1835 | 11.2594 | -- | -- |
| 1h 空头上影拒绝 ATR1.0 资产筛选Top10 | 1h | short_rejection | short | strict_approved_asset_filtered | Top10 | True | True | 289 | 10 | 45.6747 | 1.3082 | 0.1866 | 1.3096 | 0.1953 | 15.6427 | -- | -- |
| 1h 空头上影拒绝 ATR1.0 资产筛选Top10 | 1h | short_rejection | short | strict_approved_asset_filtered | Top10 | True | True | 289 | 10 | 46.7128 | 1.2935 | 0.1731 | 1.3552 | 0.2134 | 18.3355 | -- | -- |
| 1h 空头上影拒绝 ATR1.0 资产筛选Top10 | 1h | short_rejection | short | observation_candidate_asset_filtered | Top10 | False | True | 289 | 10 | 47.4048 | 1.2362 | 0.1316 | 1.4072 | 0.2263 | 18.3112 | validation_expectancy_too_negative | -- |
| 1h 空头上影拒绝 ATR1.2 | 1h | short_rejection | short | observation_candidate | -- | False | True | 473 | 44 | 44.8203 | 1.0056 | 0.0029 | 1.3016 | 0.142 | 27.5951 | total_profit_factor_lt_1_10 | -- |
| 1h 空头上影拒绝 ATR1.2 资产筛选Top10 | 1h | short_rejection | short | strict_approved_asset_filtered | Top10 | True | True | 153 | 10 | 52.9412 | 1.5006 | 0.2138 | 1.2224 | 0.1159 | 8.1074 | -- | -- |
| 1h 空头上影拒绝 ATR1.2 | 1h | short_rejection | short | observation_candidate | -- | False | True | 473 | 44 | 42.2833 | 1.0521 | 0.0302 | 1.1818 | 0.1022 | 22.9435 | total_profit_factor_lt_1_10 | -- |
| 1h 空头上影拒绝 ATR1.2 资产筛选Top10 | 1h | short_rejection | short | strict_approved_asset_filtered | Top10 | True | True | 278 | 10 | 46.4029 | 1.2928 | 0.1605 | 1.2956 | 0.1688 | 12.5212 | -- | -- |
| 1h 空头上影拒绝 ATR1.0 资产筛选Top10 | 1h | short_rejection | short | strict_approved_asset_filtered | Top10 | True | True | 222 | 10 | 48.1982 | 1.4182 | 0.2424 | 1.2033 | 0.1338 | 11.6703 | -- | -- |
| 1h 空头上影拒绝 ATR1.0 资产筛选Top8 | 1h | short_rejection | short | observation_candidate_asset_filtered | Top8 | False | True | 224 | 8 | 46.4286 | 1.2668 | 0.1598 | 1.3597 | 0.2132 | 16.2965 | validation_expectancy_too_negative | -- |
| 1h 空头上影拒绝 ATR1.2 资产筛选Top10 | 1h | short_rejection | short | observation_candidate_asset_filtered | Top10 | False | True | 130 | 10 | 50.7692 | 1.6949 | 0.3148 | 1.0249 | 0.0146 | 6.3441 | test_profit_factor_lt_1_05 | -- |
| 1h 空头上影拒绝 ATR1.0 资产筛选Top8 | 1h | short_rejection | short | strict_approved_asset_filtered | Top8 | True | True | 172 | 8 | 49.4186 | 1.529 | 0.2985 | 1.2258 | 0.1476 | 12.787 | -- | -- |
| 1h 空头上影拒绝 ATR1.2 | 1h | short_rejection | short | observation_candidate | -- | False | True | 453 | 44 | 44.5916 | 1.0021 | 0.0011 | 1.1954 | 0.0953 | 25.2311 | total_profit_factor_lt_1_10, validation_expectancy_too_negative | -- |
| 1h 空头上影拒绝 ATR1.2 资产筛选Top8 | 1h | short_rejection | short | strict_approved_asset_filtered | Top8 | True | True | 103 | 8 | 54.3689 | 1.6129 | 0.2475 | 1.1862 | 0.1026 | 8.2724 | -- | -- |
| 1h 空头上影拒绝 ATR1.2 资产筛选Top8 | 1h | short_rejection | short | strict_approved_asset_filtered | Top8 | True | True | 234 | 8 | 47.0085 | 1.3161 | 0.1839 | 1.1857 | 0.1218 | 13.2653 | -- | -- |
| 1h 空头上影拒绝 ATR1.0 资产筛选Top12 | 1h | short_rejection | short | strict_approved_asset_filtered | Top12 | True | True | 266 | 12 | 47.3684 | 1.3652 | 0.2154 | 1.1348 | 0.0911 | 14.8636 | -- | -- |

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
