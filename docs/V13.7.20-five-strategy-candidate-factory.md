# AlphaPilot V13.7.20 Five Strategy Candidate Factory

This report searches deterministic low-frequency strategy candidates with a fixed 2R target.
It is research-only, not exchange Dry-run, not live trading, not an order, and not trading advice.

## Summary

- status: completed
- candidateCount: 120
- approvedCount: 5
- targetApprovedCount: 5
- availableTimeframes: 1d, 4h
- timerange: 20200101-
- paperObservationApprovedCount: 5
- dryRunApproved: False
- liveTradingApproved: False

## Approved Candidates

| Candidate | TF | Family | Approved | Trades | Win % | PF | Return % | DD % | Failed Checks |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| 1d trend breakout confirmation ATR2.0 | 1d | breakout | True | 319 | 45.4545 | 1.5035 | 80.2621 | 21.4697 | -- |
| 1d sideways oversold reclaim ATR1.2 | 1d | mean_reversion | True | 36 | 58.3333 | 2.4289 | 21.7981 | 6.8439 | -- |
| 1d sideways oversold reclaim ATR1.0 | 1d | mean_reversion | True | 38 | 55.2632 | 2.2125 | 21.0635 | 7.7808 | -- |
| 1d trend squeeze breakout ATR2.0 | 1d | squeeze_breakout | True | 207 | 43.4783 | 1.3856 | 40.6901 | 20.0035 | -- |
| 1d broad squeeze breakout ATR2.0 | 1d | squeeze_breakout | True | 220 | 42.2727 | 1.3152 | 36.4671 | 20.8539 | -- |

### 1d trend breakout confirmation ATR2.0

| Split | Trades | Win % | PF | Return % | DD % |
| --- | ---: | ---: | ---: | ---: | ---: |
| train_2020_2022 | 97 | 47.4227 | 1.5846 | 28.3034 | 10.6224 |
| validation_2023_2024 | 168 | 46.4286 | 1.6431 | 51.8745 | 17.2665 |
| test_2025_2026 | 54 | 38.8889 | 1.0028 | 0.0842 | 10.2557 |

### 1d sideways oversold reclaim ATR1.2

| Split | Trades | Win % | PF | Return % | DD % |
| --- | ---: | ---: | ---: | ---: | ---: |
| train_2020_2022 | 4 | 75.0 | 4.487 | 3.6068 | 0.9885 |
| validation_2023_2024 | 12 | 41.6667 | 1.1902 | 1.3575 | 5.1524 |
| test_2025_2026 | 20 | 65.0 | 3.3767 | 16.8338 | 5.1091 |

### 1d sideways oversold reclaim ATR1.0

| Split | Trades | Win % | PF | Return % | DD % |
| --- | ---: | ---: | ---: | ---: | ---: |
| train_2020_2022 | 4 | 75.0 | 5.6982 | 4.8928 | 0.9831 |
| validation_2023_2024 | 13 | 38.4615 | 1.0465 | 0.382 | 6.2321 |
| test_2025_2026 | 21 | 61.9048 | 2.9453 | 15.7887 | 6.1465 |

### 1d trend squeeze breakout ATR2.0

| Split | Trades | Win % | PF | Return % | DD % |
| --- | ---: | ---: | ---: | ---: | ---: |
| train_2020_2022 | 73 | 46.5753 | 1.486 | 17.556 | 8.0931 |
| validation_2023_2024 | 103 | 41.7476 | 1.3405 | 18.4432 | 15.3623 |
| test_2025_2026 | 31 | 41.9355 | 1.3078 | 4.6909 | 6.585 |

### 1d broad squeeze breakout ATR2.0

| Split | Trades | Win % | PF | Return % | DD % |
| --- | ---: | ---: | ---: | ---: | ---: |
| train_2020_2022 | 74 | 45.9459 | 1.4455 | 16.5425 | 8.8855 |
| validation_2023_2024 | 107 | 41.1215 | 1.3035 | 17.3632 | 15.4362 |
| test_2025_2026 | 39 | 38.4615 | 1.12 | 2.5615 | 6.585 |

## Top Watchlist Candidates

| Candidate | TF | Family | Approved | Trades | Win % | PF | Return % | DD % | Failed Checks |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| 4h trend recovery reclaim ATR1.5 | 4h | recovery_reclaim | False | 2746 | 38.638 | 1.1455 | 248.2638 | 42.1263 | minProfitFactor, maxDrawdownPct |
| 4h trend recovery reclaim ATR1.8 | 4h | recovery_reclaim | False | 2592 | 39.4676 | 1.1486 | 226.9873 | 40.0412 | minProfitFactor, maxDrawdownPct |
| 4h trend recovery reclaim ATR1.2 | 4h | recovery_reclaim | False | 2922 | 37.577 | 1.1016 | 192.9259 | 61.3446 | minProfitFactor, maxDrawdownPct |
| 4h broad recovery reclaim ATR1.5 | 4h | recovery_reclaim | False | 3504 | 37.5285 | 1.0866 | 192.9205 | 73.3904 | minProfitFactor, maxDrawdownPct |
| 4h broad recovery reclaim ATR1.8 | 4h | recovery_reclaim | False | 3309 | 38.2593 | 1.0802 | 160.7777 | 72.0455 | minProfitFactor, maxDrawdownPct |
| 1d broad momentum continuation ATR1.8 | 1d | continuation | False | 472 | 43.0085 | 1.3431 | 82.0748 | 18.4354 | testPositive |
| 1d trend momentum continuation ATR1.8 | 1d | continuation | False | 455 | 43.2967 | 1.353 | 80.7403 | 19.6036 | testPositive |
| 1d broad breakout confirmation ATR2.0 | 1d | breakout | False | 333 | 44.1441 | 1.4339 | 74.2158 | 23.9497 | testPositive |
| 1d trend conservative pullback ATR1.8 | 1d | trend_pullback | False | 167 | 46.1078 | 1.5067 | 41.6134 | 12.1697 | testPositive |
| 1d trend conservative pullback ATR1.5 | 1d | trend_pullback | False | 177 | 44.0678 | 1.4451 | 43.045 | 11.8457 | testPositive |
| 1d trend conservative pullback ATR1.2 | 1d | trend_pullback | False | 185 | 42.1622 | 1.4101 | 44.1235 | 12.9488 | testPositive |
| 1d broad conservative pullback ATR1.5 | 1d | trend_pullback | False | 182 | 43.956 | 1.4113 | 41.038 | 12.5517 | testPositive |
| 1d broad trend pullback confluence ATR1.2 | 1d | trend_pullback | False | 262 | 41.2214 | 1.3176 | 48.3559 | 17.1519 | testPositive |
| 1d broad conservative pullback ATR1.8 | 1d | trend_pullback | False | 173 | 45.6647 | 1.4456 | 38.4154 | 12.9766 | testPositive |
| 1d trend breakout confirmation ATR1.5 | 1d | breakout | False | 361 | 40.7202 | 1.2502 | 53.7094 | 22.8102 | testPositive |
| 1d broad conservative pullback ATR1.2 | 1d | trend_pullback | False | 191 | 40.8377 | 1.3336 | 37.956 | 14.0043 | testPositive |
| 1d trend trend pullback confluence ATR1.2 | 1d | trend_pullback | False | 252 | 40.873 | 1.3035 | 44.7937 | 20.1227 | testPositive |
| 1d broad breakout confirmation ATR1.5 | 1d | breakout | False | 375 | 40.2667 | 1.2281 | 51.3175 | 23.7209 | testPositive |
| 1d broad trend pullback confluence ATR1.8 | 1d | trend_pullback | False | 229 | 42.7948 | 1.3272 | 37.9033 | 17.1636 | testPositive |
| 1d trend momentum continuation ATR1.5 | 1d | continuation | False | 511 | 39.1389 | 1.1705 | 49.9169 | 24.1785 | testPositive |

## Safety Boundary

- realTradingEnabled: False
- exchangeDryRunApproved: False
- liveTradingApproved: False
- tradeApiEnabled: False
- withdrawApiEnabled: False
- apiKeyStorage: False
- realAccountReads: False
- realPositionReads: False
- orderCreation: False
- autoTrading: False

## Next Step

Move approved candidates into local paper-observation review only; exchange Dry-run remains blocked.
