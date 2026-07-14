# AlphaPilot V13.27.17 Cross-Timeframe Candidate Inventory

本报告只做研究筛选。每周期 5 条是候选库存，不代表 5 条全部通过。
所有候选保持目标不低于 2R；锁定样本不参与选择，不创建 Demo/Live Release。

## Summary

- candidateCount: 25
- candidateCountByTimeframe: {'5m': 5, '15m': 5, '1h': 5, '4h': 5, '1d': 5}
- researchEligibleCount: 15
- executableResearchEligibleCount: 7
- shadowOnlyCount: 3
- rejectedCount: 7
- researchEligibleByTimeframe: {'5m': 2, '15m': 4, '1h': 1, '4h': 5, '1d': 3}

## 5M Candidates

| Candidate | Tier | PF floor | Expectancy floor | Trades | Failed checks |
| --- | --- | ---: | ---: | ---: | --- |
| 5m 趋势回踩事件确认 学习版 ATR2.2 | research_eligible | 1.1023 | 0.067577 | 250 | -- |
| 5m 突破回踩环境确认 学习版 ATR1.8 | rejected | 0.7758 | -0.172854 | 178 | derivation_validation_expectancy_not_positive, derivation_validation_profit_factor_not_above_one, symbol_holdback_expectancy_not_positive, symbol_holdback_profit_factor_not_above_one |
| 5m 扫低收回环境确认 学习版 ATR2.2 | rejected | 0.6103 | -0.278679 | 461 | symbol_holdback_expectancy_not_positive, symbol_holdback_profit_factor_not_above_one |
| 5m 假突破反转环境确认 学习版 ATR2.2 | research_eligible | 1.1363 | 0.090873 | 158 | -- |
| 5m 弱势回抽结构确认 学习版 ATR2.2 | rejected | 0.9143 | -0.061792 | 391 | derivation_train_expectancy_not_positive, derivation_train_profit_factor_not_above_one, symbol_holdback_expectancy_not_positive, symbol_holdback_profit_factor_not_above_one |

## 15M Candidates

| Candidate | Tier | PF floor | Expectancy floor | Trades | Failed checks |
| --- | --- | ---: | ---: | ---: | --- |
| 15m 趋势回踩双趋势确认 因子后继 ATR1.2 | research_eligible | 1.1362 | 0.090261 | 142 | -- |
| 15m 趋势回踩波动环境确认 因子后继 ATR1.2 | research_eligible | 1.0438 | 0.03006 | 95 | -- |
| 15m 假突破弱趋势反转 因子后继 ATR1.2 | research_eligible | 1.2845 | 0.1795 | 114 | -- |
| 15m 弱势回抽市场斜率确认 因子后继 ATR1.2 | research_eligible | 1.4252 | 0.258481 | 101 | -- |
| 15m 弱势回抽区间衰竭 影子候选 ATR1.2 | rejected | 0.7054 | -0.24164 | 243 | derivation_train_positive_pair_share_below_50pct, derivation_validation_positive_pair_share_below_50pct, symbol_holdback_expectancy_not_positive, symbol_holdback_profit_factor_not_above_one, symbol_holdback_positive_pair_share_below_50pct |

## 1H Candidates

| Candidate | Tier | PF floor | Expectancy floor | Trades | Failed checks |
| --- | --- | ---: | ---: | ---: | --- |
| 1H 深弱势扫低收回 因子后继 ATR1.2 | research_eligible | 1.3396 | 0.194421 | 249 | -- |
| 1H 突破回踩 BTC 顺势确认 因子后继 ATR1.2 | shadow_only | 1.0163 | 0.011041 | 540 | symbol_holdback_positive_pair_share_below_50pct |
| 1H 弱势回抽窗口失败 影子候选 ATR1.2 | rejected | 0.8166 | -0.132898 | 19208 | derivation_train_expectancy_not_positive, derivation_train_profit_factor_not_above_one, derivation_train_positive_pair_share_below_50pct, derivation_validation_expectancy_not_positive, derivation_validation_profit_factor_not_above_one, derivation_validation_positive_pair_share_below_50pct, symbol_holdback_expectancy_not_positive, symbol_holdback_profit_factor_not_above_one, symbol_holdback_positive_pair_share_below_50pct |
| 1H 趋势回踩分步确认 影子候选 ATR1.2 | rejected | 0.7519 | -0.183319 | 16496 | derivation_train_expectancy_not_positive, derivation_train_profit_factor_not_above_one, derivation_train_positive_pair_share_below_50pct, derivation_validation_expectancy_not_positive, derivation_validation_profit_factor_not_above_one, derivation_validation_positive_pair_share_below_50pct, symbol_holdback_expectancy_not_positive, symbol_holdback_profit_factor_not_above_one, symbol_holdback_positive_pair_share_below_50pct |
| 1H 假突破事件窗口反转 影子候选 ATR1.2 | rejected | 0.7142 | -0.214683 | 4423 | derivation_train_expectancy_not_positive, derivation_train_profit_factor_not_above_one, derivation_train_positive_pair_share_below_50pct, derivation_validation_expectancy_not_positive, derivation_validation_profit_factor_not_above_one, derivation_validation_positive_pair_share_below_50pct, symbol_holdback_expectancy_not_positive, symbol_holdback_profit_factor_not_above_one, symbol_holdback_positive_pair_share_below_50pct |

## 4H Candidates

| Candidate | Tier | PF floor | Expectancy floor | Trades | Failed checks |
| --- | --- | ---: | ---: | ---: | --- |
| 4H 牛市回踩收回 ATR1.8 持有24 | research_eligible | 1.2509 | 0.13573447 | 1764 | -- |
| 4H 牛市回踩收回 ATR2.0 持有24 | research_eligible | 1.2614 | 0.13571039 | 1723 | -- |
| 4H 牛市回踩收回 ATR2.0 持有36 | research_eligible | 1.2382 | 0.13556526 | 1655 | -- |
| 4H 牛市回踩收回 ATR1.5 持有24 | research_eligible | 1.1947 | 0.11548567 | 1870 | -- |
| 4H 牛市回踩收回 ATR2.0 持有30 | research_eligible | 1.2263 | 0.12497024 | 1687 | -- |

## 1D Candidates

| Candidate | Tier | PF floor | Expectancy floor | Trades | Failed checks |
| --- | --- | ---: | ---: | ---: | --- |
| 1D 趋势突破确认 ATR2.0 | research_eligible | 1.6211 | 0.30255811 | 265 | -- |
| 1D 趋势压缩突破 ATR2.0 | research_eligible | 1.3988 | 0.20454091 | 176 | -- |
| 1D 广谱压缩突破 ATR2.0 | research_eligible | 1.3594 | 0.18732431 | 181 | -- |
| 1D 震荡超卖收回 ATR1.2 | shadow_only | 1.6075 | 0.31026875 | 16 | selectionTradeCount |
| 1D 震荡超卖收回 ATR1.0 | shadow_only | 1.5699 | 0.31028235 | 17 | developmentSymbolsPositive, selectionTradeCount |

## Interpretation

- research_eligible 只表示通过当前研究预筛，仍不是正式回测、本地前向或 Demo 晋级结论。
- shadow_only 表示证据方向有价值但仍有明确缺项，只允许继续观察。
- rejected 表示当前定义不应继续晋级；不能为了补足数量而强制放行。
- 同家族参数变体可能高度相关，候选数量不能当作独立风险来源数量。
