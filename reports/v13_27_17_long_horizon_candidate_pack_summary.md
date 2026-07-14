# AlphaPilot V13.27.17 Long-Horizon Candidate Pack

本报告为研究筛选，不代表盈利承诺，不创建 Demo/Live Release，也不下单。
候选数量与正式资格严格分开；锁定段只报告，不参与选择。

## Summary

- selectedCandidateCount: 15
- selectedByTimeframe: {'1h': 5, '4h': 5, '1d': 5}
- researchEligibleByTimeframe: {'1h': 1, '4h': 5, '1d': 3}
- shadowOnlyByTimeframe: {'1h': 1, '4h': 0, '1d': 2}
- rejectedByTimeframe: {'1h': 3, '4h': 0, '1d': 0}
- targetR: 2.0

## 1H Candidates

| Candidate | Tier | PF | Trades | Failed checks | Correlation group |
| --- | --- | ---: | ---: | --- | --- |
| 1H 深弱势扫低收回 因子后继 ATR1.2 | research_eligible | 1.3396 | 249 | -- | 1h_windowed_liquidity_sweep_reclaim_long |
| 1H 突破回踩 BTC 顺势确认 因子后继 ATR1.2 | shadow_only | 1.0163 | 540 | symbol_holdback_positive_pair_share_below_50pct | 1h_windowed_breakout_retest_long |
| 1H 弱势回抽窗口失败 影子候选 ATR1.2 | rejected | 0.8166 | 19208 | derivation_train_expectancy_not_positive, derivation_train_profit_factor_not_above_one, derivation_train_positive_pair_share_below_50pct, derivation_validation_expectancy_not_positive, derivation_validation_profit_factor_not_above_one, derivation_validation_positive_pair_share_below_50pct, symbol_holdback_expectancy_not_positive, symbol_holdback_profit_factor_not_above_one, symbol_holdback_positive_pair_share_below_50pct | 1h_windowed_failed_reclaim_short |
| 1H 趋势回踩分步确认 影子候选 ATR1.2 | rejected | 0.7519 | 16496 | derivation_train_expectancy_not_positive, derivation_train_profit_factor_not_above_one, derivation_train_positive_pair_share_below_50pct, derivation_validation_expectancy_not_positive, derivation_validation_profit_factor_not_above_one, derivation_validation_positive_pair_share_below_50pct, symbol_holdback_expectancy_not_positive, symbol_holdback_profit_factor_not_above_one, symbol_holdback_positive_pair_share_below_50pct | 1h_windowed_trend_reclaim_long |
| 1H 假突破事件窗口反转 影子候选 ATR1.2 | rejected | 0.7142 | 4423 | derivation_train_expectancy_not_positive, derivation_train_profit_factor_not_above_one, derivation_train_positive_pair_share_below_50pct, derivation_validation_expectancy_not_positive, derivation_validation_profit_factor_not_above_one, derivation_validation_positive_pair_share_below_50pct, symbol_holdback_expectancy_not_positive, symbol_holdback_profit_factor_not_above_one, symbol_holdback_positive_pair_share_below_50pct | 1h_windowed_failed_breakout_short |

## 4H Candidates

| Candidate | Tier | PF | Trades | Failed checks | Correlation group |
| --- | --- | ---: | ---: | --- | --- |
| 4H 牛市回踩收回 ATR1.8 持有24 | research_eligible | 1.2509 | 1764 | -- | 4h_btc_bull_recovery_reclaim |
| 4H 牛市回踩收回 ATR2.0 持有24 | research_eligible | 1.2614 | 1723 | -- | 4h_btc_bull_recovery_reclaim |
| 4H 牛市回踩收回 ATR2.0 持有36 | research_eligible | 1.2382 | 1655 | -- | 4h_btc_bull_recovery_reclaim |
| 4H 牛市回踩收回 ATR1.5 持有24 | research_eligible | 1.1947 | 1870 | -- | 4h_btc_bull_recovery_reclaim |
| 4H 牛市回踩收回 ATR2.0 持有30 | research_eligible | 1.2263 | 1687 | -- | 4h_btc_bull_recovery_reclaim |

## 1D Candidates

| Candidate | Tier | PF | Trades | Failed checks | Correlation group |
| --- | --- | ---: | ---: | --- | --- |
| 1D 趋势突破确认 ATR2.0 | research_eligible | 1.6211 | 265 | -- | 1d_trend_breakout |
| 1D 趋势压缩突破 ATR2.0 | research_eligible | 1.3988 | 176 | -- | 1d_squeeze_breakout |
| 1D 广谱压缩突破 ATR2.0 | research_eligible | 1.3594 | 181 | -- | 1d_squeeze_breakout |
| 1D 震荡超卖收回 ATR1.2 | shadow_only | 1.6075 | 16 | selectionTradeCount | 1d_oversold_reclaim |
| 1D 震荡超卖收回 ATR1.0 | shadow_only | 1.5699 | 17 | developmentSymbolsPositive, selectionTradeCount | 1d_oversold_reclaim |

## Interpretation

- 1H 候选采用事件窗口、可选确认计分和透明市场状态因子，避免把所有条件硬塞进同一根 K 线。
- 1H 表格中的 PF/样本来自候选自身的直接三段预筛；未通过者保持影子或拒绝，不借用旧家族指标。
- 4H 候选隔离 BTC 牛市状态下的回踩收回结构；同组参数变体高度相关，不能视为五种独立风险来源。
- 1D 候选复核既有低频定义；即使 research_eligible，也仍需独立前向与 Demo 证据才能晋级。
