# AlphaPilot V13.7.40 Short-Cycle Parameter Search

This report searches short-cycle public-OHLCV research candidates with fixed 2R exits.
It is not exchange dry-run, not live trading, not an order, and not trading advice.

## Summary

- status: completed
- candidateCount: 970
- approvedCount: 19
- observationCandidateCount: 51
- selectedCount: 5
- approvedSelectedCount: 5
- observationSelectedCount: 0
- targetR: 2.0
- feeRate: 0.0005
- slippageRate: 0.0005
- timerange: 20200101-

## Data Coverage

- 1h: 17 pairs

## Selected Candidates

| Candidate | TF | Family | Direction | Tier | Asset Filter | Strict | Observation | Trades | Pairs | Win % | PF | Exp R | Test PF | Test Exp R | DD R | Failed Checks | Observation Checks |
| --- | --- | --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| 1h 空头上影拒绝 ATR1.2 资产筛选Top8 | 1h | short_rejection | short | strict_approved_asset_filtered | Top8 | True | True | 169 | 8 | 50.8876 | 1.5181 | 0.2701 | 1.24 | 0.1438 | 11.967 | -- | -- |
| 1h 空头上影拒绝 ATR1.0 资产筛选Top10 | 1h | short_rejection | short | strict_approved_asset_filtered | Top10 | True | True | 272 | 10 | 47.7941 | 1.3407 | 0.2042 | 1.1939 | 0.1242 | 11.6368 | -- | -- |
| 1h 空头上影拒绝 ATR1.2 资产筛选Top8 | 1h | short_rejection | short | strict_approved_asset_filtered | Top8 | True | True | 169 | 8 | 50.8876 | 1.5643 | 0.2725 | 1.2212 | 0.1267 | 11.3028 | -- | -- |
| 1h 空头上影拒绝 ATR1.0 资产筛选Top8 | 1h | short_rejection | short | strict_approved_asset_filtered | Top8 | True | True | 211 | 8 | 47.8673 | 1.365 | 0.2189 | 1.1817 | 0.1161 | 13.4216 | -- | -- |
| 1h 空头上影拒绝 ATR1.0 | 1h | short_rejection | short | strict_approved | -- | True | True | 339 | 17 | 44.2478 | 1.1702 | 0.1074 | 1.1658 | 0.1099 | 19.9766 | -- | -- |

### 1h 空头上影拒绝 ATR1.2 资产筛选Top8

- candidateId: `v13_7_40_1h_short_rejection_2153_asset_filter_top8`
- approved: True
- observationCandidate: True
- approvalTier: strict_approved_asset_filtered
- params: `{"upper_buffer": 0.006, "trend_tolerance": 1.0, "rsi_high": 60, "volume_min": 1.2, "stop_atr": 1.2, "max_hold": 16}`
- assetFilter: `{"enabled": true, "selectionMethod": "train_segment_positive_pair_filter", "selectedPairCount": 8, "selectedPairs": ["APE/USDT:USDT", "CRO/USDT:USDT", "DOGE/USDT:USDT", "GALA/USDT:USDT", "LTC/USDT:USDT", "SAND/USDT:USDT", "TRX/USDT:USDT", "ZRX/USDT:USDT"], "minTrainTradesPerPair": 3, "minTrainProfitFactor": 1.05, "requiresPositiveTrainExpectancy": true, "note": "Pairs are selected from the train segment only; validation and test remain out of selection."}`

#### Walk-Forward

| Split | Trades | Pairs | Win % | PF | Exp R | Total R | DD R |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| train | 68 | 8 | 58.8235 | 2.0434 | 0.4502 | 30.6111 | 3.8541 |
| validation | 56 | 8 | 46.4286 | 1.2692 | 0.1529 | 8.561 | 8.2368 |
| test | 45 | 8 | 44.4444 | 1.24 | 0.1438 | 6.4714 | 11.967 |

#### Top Pair Breakdown

| Pair | Trades | Win % | PF | Exp R | Total R |
| --- | ---: | ---: | ---: | ---: | ---: |
| GALA/USDT:USDT | 27 | 66.6667 | 2.584 | 0.5844 | 15.7783 |
| CRO/USDT:USDT | 18 | 61.1111 | 2.2539 | 0.5312 | 9.5608 |
| LTC/USDT:USDT | 26 | 53.8462 | 1.6711 | 0.3399 | 8.8363 |
| TRX/USDT:USDT | 16 | 50.0 | 1.494 | 0.269 | 4.3038 |
| DOGE/USDT:USDT | 25 | 48.0 | 1.2473 | 0.1185 | 2.9637 |
| SAND/USDT:USDT | 17 | 47.0588 | 1.2262 | 0.1338 | 2.2741 |
| ZRX/USDT:USDT | 18 | 38.8889 | 1.0818 | 0.0555 | 0.9994 |
| APE/USDT:USDT | 22 | 36.3636 | 1.0645 | 0.0421 | 0.9271 |

### 1h 空头上影拒绝 ATR1.0 资产筛选Top10

- candidateId: `v13_7_40_1h_short_rejection_2069_asset_filter_top10`
- approved: True
- observationCandidate: True
- approvalTier: strict_approved_asset_filtered
- params: `{"upper_buffer": 0.003, "trend_tolerance": 1.0, "rsi_high": 60, "volume_min": 1.0, "stop_atr": 1.0, "max_hold": 16}`
- assetFilter: `{"enabled": true, "selectionMethod": "train_segment_positive_pair_filter", "selectedPairCount": 10, "selectedPairs": ["APE/USDT:USDT", "APT/USDT:USDT", "CRO/USDT:USDT", "GALA/USDT:USDT", "LTC/USDT:USDT", "MANA/USDT:USDT", "SAND/USDT:USDT", "SOL/USDT:USDT", "TRX/USDT:USDT", "ZRX/USDT:USDT"], "minTrainTradesPerPair": 3, "minTrainProfitFactor": 1.05, "requiresPositiveTrainExpectancy": true, "note": "Pairs are selected from the train segment only; validation and test remain out of selection."}`

#### Walk-Forward

| Split | Trades | Pairs | Win % | PF | Exp R | Total R | DD R |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| train | 105 | 10 | 52.381 | 1.6368 | 0.3394 | 35.6376 | 4.7166 |
| validation | 80 | 10 | 45.0 | 1.1773 | 0.1138 | 9.1039 | 11.6368 |
| test | 87 | 10 | 44.8276 | 1.1939 | 0.1242 | 10.806 | 11.2874 |

#### Top Pair Breakdown

| Pair | Trades | Win % | PF | Exp R | Total R |
| --- | ---: | ---: | ---: | ---: | ---: |
| GALA/USDT:USDT | 31 | 70.9677 | 3.6662 | 0.8687 | 26.9287 |
| MANA/USDT:USDT | 30 | 50.0 | 1.427 | 0.239 | 7.1701 |
| LTC/USDT:USDT | 33 | 48.4848 | 1.348 | 0.2068 | 6.8253 |
| TRX/USDT:USDT | 26 | 50.0 | 1.2809 | 0.1797 | 4.672 |
| APT/USDT:USDT | 21 | 47.619 | 1.3656 | 0.2158 | 4.5327 |
| ZRX/USDT:USDT | 20 | 45.0 | 1.3555 | 0.2211 | 4.423 |
| SOL/USDT:USDT | 31 | 45.1613 | 1.1108 | 0.0703 | 2.1792 |
| SAND/USDT:USDT | 22 | 45.4545 | 1.1384 | 0.0849 | 1.8672 |

### 1h 空头上影拒绝 ATR1.2 资产筛选Top8

- candidateId: `v13_7_40_1h_short_rejection_2152_asset_filter_top8`
- approved: True
- observationCandidate: True
- approvalTier: strict_approved_asset_filtered
- params: `{"upper_buffer": 0.006, "trend_tolerance": 1.0, "rsi_high": 60, "volume_min": 1.2, "stop_atr": 1.2, "max_hold": 12}`
- assetFilter: `{"enabled": true, "selectionMethod": "train_segment_positive_pair_filter", "selectedPairCount": 8, "selectedPairs": ["APE/USDT:USDT", "CRO/USDT:USDT", "DOGE/USDT:USDT", "GALA/USDT:USDT", "LTC/USDT:USDT", "SAND/USDT:USDT", "TRX/USDT:USDT", "ZRX/USDT:USDT"], "minTrainTradesPerPair": 3, "minTrainProfitFactor": 1.05, "requiresPositiveTrainExpectancy": true, "note": "Pairs are selected from the train segment only; validation and test remain out of selection."}`

#### Walk-Forward

| Split | Trades | Pairs | Win % | PF | Exp R | Total R | DD R |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| train | 68 | 8 | 61.7647 | 2.2741 | 0.499 | 33.9346 | 4.4238 |
| validation | 56 | 8 | 44.6429 | 1.2198 | 0.1146 | 6.42 | 10.256 |
| test | 45 | 8 | 42.2222 | 1.2212 | 0.1267 | 5.6999 | 11.3029 |

#### Top Pair Breakdown

| Pair | Trades | Win % | PF | Exp R | Total R |
| --- | ---: | ---: | ---: | ---: | ---: |
| GALA/USDT:USDT | 27 | 70.3704 | 3.3947 | 0.6413 | 17.3146 |
| CRO/USDT:USDT | 18 | 55.5556 | 2.1239 | 0.4789 | 8.6209 |
| LTC/USDT:USDT | 26 | 50.0 | 1.4101 | 0.2147 | 5.5829 |
| APE/USDT:USDT | 22 | 50.0 | 1.4216 | 0.2099 | 4.6171 |
| TRX/USDT:USDT | 16 | 43.75 | 1.3933 | 0.2194 | 3.5099 |
| DOGE/USDT:USDT | 25 | 44.0 | 1.2572 | 0.1253 | 3.1333 |
| SAND/USDT:USDT | 17 | 47.0588 | 1.2776 | 0.1543 | 2.6233 |
| ZRX/USDT:USDT | 18 | 38.8889 | 1.0563 | 0.0363 | 0.6525 |

### 1h 空头上影拒绝 ATR1.0 资产筛选Top8

- candidateId: `v13_7_40_1h_short_rejection_2069_asset_filter_top8`
- approved: True
- observationCandidate: True
- approvalTier: strict_approved_asset_filtered
- params: `{"upper_buffer": 0.003, "trend_tolerance": 1.0, "rsi_high": 60, "volume_min": 1.0, "stop_atr": 1.0, "max_hold": 16}`
- assetFilter: `{"enabled": true, "selectionMethod": "train_segment_positive_pair_filter", "selectedPairCount": 8, "selectedPairs": ["APE/USDT:USDT", "APT/USDT:USDT", "CRO/USDT:USDT", "GALA/USDT:USDT", "LTC/USDT:USDT", "SAND/USDT:USDT", "TRX/USDT:USDT", "ZRX/USDT:USDT"], "minTrainTradesPerPair": 3, "minTrainProfitFactor": 1.05, "requiresPositiveTrainExpectancy": true, "note": "Pairs are selected from the train segment only; validation and test remain out of selection."}`

#### Walk-Forward

| Split | Trades | Pairs | Win % | PF | Exp R | Total R | DD R |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| train | 77 | 8 | 53.2468 | 1.7495 | 0.3931 | 30.2655 | 4.7166 |
| validation | 63 | 8 | 44.4444 | 1.1884 | 0.122 | 7.6878 | 10.4405 |
| test | 71 | 8 | 45.0704 | 1.1817 | 0.1161 | 8.245 | 13.4216 |

#### Top Pair Breakdown

| Pair | Trades | Win % | PF | Exp R | Total R |
| --- | ---: | ---: | ---: | ---: | ---: |
| GALA/USDT:USDT | 31 | 70.9677 | 3.6662 | 0.8687 | 26.9287 |
| LTC/USDT:USDT | 33 | 48.4848 | 1.348 | 0.2068 | 6.8253 |
| TRX/USDT:USDT | 26 | 50.0 | 1.2809 | 0.1797 | 4.672 |
| APT/USDT:USDT | 21 | 47.619 | 1.3656 | 0.2158 | 4.5327 |
| ZRX/USDT:USDT | 20 | 45.0 | 1.3555 | 0.2211 | 4.423 |
| SAND/USDT:USDT | 22 | 45.4545 | 1.1384 | 0.0849 | 1.8672 |
| CRO/USDT:USDT | 24 | 41.6667 | 1.0931 | 0.064 | 1.5369 |
| APE/USDT:USDT | 34 | 32.3529 | 0.8193 | -0.1349 | -4.5875 |

### 1h 空头上影拒绝 ATR1.0

- candidateId: `v13_7_40_1h_short_rejection_2078`
- approved: True
- observationCandidate: True
- approvalTier: strict_approved
- params: `{"upper_buffer": 0.003, "trend_tolerance": 1.0, "rsi_high": 60, "volume_min": 1.2, "stop_atr": 1.0, "max_hold": 16}`

#### Walk-Forward

| Split | Trades | Pairs | Win % | PF | Exp R | Total R | DD R |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| train | 140 | 15 | 48.5714 | 1.3835 | 0.215 | 30.0997 | 13.9479 |
| validation | 108 | 17 | 39.8148 | 0.951 | -0.0341 | -3.6822 | 12.9926 |
| test | 91 | 17 | 42.8571 | 1.1658 | 0.1099 | 10.0 | 19.9766 |

#### Top Pair Breakdown

| Pair | Trades | Win % | PF | Exp R | Total R |
| --- | ---: | ---: | ---: | ---: | ---: |
| GALA/USDT:USDT | 26 | 65.3846 | 2.8906 | 0.7344 | 19.0953 |
| LTC/USDT:USDT | 26 | 53.8462 | 1.6692 | 0.3513 | 9.1332 |
| APT/USDT:USDT | 16 | 56.25 | 2.1232 | 0.5479 | 8.7668 |
| TRX/USDT:USDT | 16 | 56.25 | 1.6685 | 0.3644 | 5.8305 |
| CRO/USDT:USDT | 16 | 50.0 | 1.5221 | 0.3107 | 4.972 |
| ADA/USDT:USDT | 20 | 50.0 | 1.4401 | 0.2483 | 4.9661 |
| MANA/USDT:USDT | 22 | 50.0 | 1.3308 | 0.1862 | 4.0954 |
| SAND/USDT:USDT | 16 | 50.0 | 1.3628 | 0.2048 | 3.2764 |

## Top 25 Candidates

| Candidate | TF | Family | Direction | Tier | Asset Filter | Strict | Observation | Trades | Pairs | Win % | PF | Exp R | Test PF | Test Exp R | DD R | Failed Checks | Observation Checks |
| --- | --- | --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| 1h 空头上影拒绝 ATR1.0 资产筛选Top8 | 1h | short_rejection | short | observation_candidate_asset_filtered | Top8 | False | True | 158 | 8 | 48.1013 | 1.4111 | 0.2103 | 1.4871 | 0.2574 | 10.4354 | validation_expectancy_too_negative | -- |
| 1h 空头上影拒绝 ATR1.2 资产筛选Top8 | 1h | short_rejection | short | strict_approved_asset_filtered | Top8 | True | True | 169 | 8 | 50.8876 | 1.5181 | 0.2701 | 1.24 | 0.1438 | 11.967 | -- | -- |
| 1h 空头上影拒绝 ATR1.2 | 1h | short_rejection | short | observation_candidate | -- | False | True | 178 | 17 | 53.3708 | 1.6295 | 0.2873 | 1.0257 | 0.0151 | 11.3165 | test_profit_factor_lt_1_05 | -- |
| 1h 空头上影拒绝 ATR1.2 | 1h | short_rejection | short | observation_candidate | -- | False | True | 166 | 17 | 53.012 | 1.5987 | 0.2719 | 1.049 | 0.028 | 11.3165 | test_profit_factor_lt_1_05 | -- |
| 1h 空头上影拒绝 ATR1.0 资产筛选Top10 | 1h | short_rejection | short | strict_approved_asset_filtered | Top10 | True | True | 272 | 10 | 47.7941 | 1.3407 | 0.2042 | 1.1939 | 0.1242 | 11.6368 | -- | -- |
| 1h 空头上影拒绝 ATR1.2 资产筛选Top8 | 1h | short_rejection | short | strict_approved_asset_filtered | Top8 | True | True | 169 | 8 | 50.8876 | 1.5643 | 0.2725 | 1.2212 | 0.1267 | 11.3028 | -- | -- |
| 1h 空头上影拒绝 ATR1.6 | 1h | short_rejection | short | rejected | -- | False | False | 164 | 17 | 54.2683 | 1.5554 | 0.2202 | 0.9957 | -0.0022 | 9.8597 | test_profit_factor_lt_1_05, test_expectancy_not_positive | observation_test_profit_factor_lt_1_00, observation_test_expectancy_not_positive |
| 1h 空头上影拒绝 ATR1.0 资产筛选Top8 | 1h | short_rejection | short | strict_approved_asset_filtered | Top8 | True | True | 211 | 8 | 47.8673 | 1.365 | 0.2189 | 1.1817 | 0.1161 | 13.4216 | -- | -- |
| 1h 空头上影拒绝 ATR1.6 | 1h | short_rejection | short | rejected | -- | False | False | 175 | 17 | 54.2857 | 1.5297 | 0.2138 | 0.98 | -0.0105 | 11.0686 | test_profit_factor_lt_1_05, test_expectancy_not_positive | observation_test_profit_factor_lt_1_00, observation_test_expectancy_not_positive |
| 1h 空头上影拒绝 ATR1.2 | 1h | short_rejection | short | observation_candidate | -- | False | True | 178 | 17 | 53.3708 | 1.4133 | 0.178 | 1.0332 | 0.0185 | 10.823 | test_profit_factor_lt_1_05 | -- |
| 1h 空头上影拒绝 ATR1.0 | 1h | short_rejection | short | strict_approved | -- | True | True | 339 | 17 | 44.2478 | 1.1702 | 0.1074 | 1.1658 | 0.1099 | 19.9766 | -- | -- |
| 1h 空头上影拒绝 ATR1.0 资产筛选Top10 | 1h | short_rejection | short | strict_approved_asset_filtered | Top10 | True | True | 272 | 10 | 47.7941 | 1.3008 | 0.1775 | 1.1476 | 0.0945 | 13.5768 | -- | -- |
| 1h 空头上影拒绝 ATR1.2 | 1h | short_rejection | short | rejected | -- | False | False | 207 | 17 | 50.7246 | 1.4195 | 0.2093 | 0.9827 | -0.0107 | 13.8026 | test_profit_factor_lt_1_05, test_expectancy_not_positive | observation_test_profit_factor_lt_1_00, observation_test_expectancy_not_positive |
| 1h 空头上影拒绝 ATR1.0 资产筛选Top8 | 1h | short_rejection | short | strict_approved_asset_filtered | Top8 | True | True | 211 | 8 | 47.8673 | 1.3381 | 0.1988 | 1.1385 | 0.0885 | 15.0045 | -- | -- |
| 1h 空头上影拒绝 ATR1.0 资产筛选Top8 | 1h | short_rejection | short | observation_candidate_asset_filtered | Top8 | False | True | 168 | 8 | 46.4286 | 1.2982 | 0.1576 | 1.2575 | 0.1435 | 13.8143 | validation_expectancy_too_negative | -- |
| 1h 空头上影拒绝 ATR1.2 资产筛选Top8 | 1h | short_rejection | short | observation_candidate_asset_filtered | Top8 | False | True | 161 | 8 | 50.9317 | 1.3796 | 0.1677 | 1.2443 | 0.1225 | 10.2949 | validation_expectancy_too_negative | -- |
| 1h 空头上影拒绝 ATR1.0 | 1h | short_rejection | short | observation_candidate | -- | False | True | 339 | 17 | 45.4277 | 1.1535 | 0.0941 | 1.1457 | 0.0925 | 19.625 | validation_expectancy_too_negative | -- |
| 1h 空头上影拒绝 ATR1.2 | 1h | short_rejection | short | observation_candidate | -- | False | True | 166 | 17 | 53.012 | 1.3941 | 0.1711 | 1.0032 | 0.0018 | 10.823 | test_profit_factor_lt_1_05 | -- |
| 1h 空头上影拒绝 ATR1.0 | 1h | short_rejection | short | strict_approved | -- | True | True | 356 | 17 | 43.8202 | 1.1549 | 0.0981 | 1.1059 | 0.0712 | 21.9958 | -- | -- |
| 1h 空头上影拒绝 ATR1.2 | 1h | short_rejection | short | observation_candidate | -- | False | True | 207 | 17 | 50.7246 | 1.2691 | 0.1251 | 1.0202 | 0.0115 | 12.0591 | test_profit_factor_lt_1_05 | -- |
| 1h 空头上影拒绝 ATR1.2 资产筛选Top8 | 1h | short_rejection | short | strict_approved_asset_filtered | Top8 | True | True | 170 | 8 | 50.5882 | 1.3648 | 0.1622 | 1.1514 | 0.0789 | 11.3479 | -- | -- |
| 1h 空头上影拒绝 ATR1.0 资产筛选Top8 | 1h | short_rejection | short | strict_approved_asset_filtered | Top8 | True | True | 171 | 8 | 50.2924 | 1.4138 | 0.2321 | 1.1154 | 0.0748 | 13.2186 | -- | -- |
| 1h 空头上影拒绝 ATR1.6 | 1h | short_rejection | short | rejected | -- | False | False | 204 | 17 | 51.9608 | 1.3424 | 0.1506 | 0.944 | -0.0311 | 13.7658 | test_profit_factor_lt_1_05, test_expectancy_not_positive | observation_test_profit_factor_lt_1_00, observation_test_expectancy_not_positive |
| 1h 空头上影拒绝 ATR1.4 | 1h | short_rejection | short | strict_approved | -- | True | True | 336 | 17 | 44.6429 | 1.1076 | 0.0625 | 1.09 | 0.0563 | 18.66 | -- | -- |
| 1h 空头上影拒绝 ATR1.4 | 1h | short_rejection | short | observation_candidate | -- | False | True | 460 | 17 | 44.7826 | 1.0678 | 0.0396 | 1.1204 | 0.0703 | 20.989 | total_profit_factor_lt_1_10, validation_expectancy_too_negative | -- |

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
