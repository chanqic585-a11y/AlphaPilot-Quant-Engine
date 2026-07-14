# AlphaPilot V13.27.18 Cross-Timeframe Executable Candidate Pack

本报告把既有开发筛选证据绑定到当前可执行定义。每周期 5 条是研究库存，
不代表全部通过正式回测；影子候选不得冒充正式通过。

## Summary

- candidateCount: 25
- candidateCountByTimeframe: {'5m': 5, '15m': 5, '1h': 5, '4h': 5, '1d': 5}
- researchEligibleCount: 13
- shadowOnlyCount: 12
- rejectedCount: 0
- executableResearchEligibleCount: 13
- researchEligibleByTimeframe: {'5m': 0, '15m': 4, '1h': 1, '4h': 5, '1d': 3}

## 5M

| Candidate | Tier | Trades | PF | Expectancy R | Formal data plan |
| --- | --- | ---: | ---: | ---: | --- |
| 5m 趋势回踩事件确认 学习版 ATR2.2 | shadow_only | 250 | 1.1023 | 0.067577 | 5m/5m/-- |
| 5m 突破回踩环境确认 学习版 ATR1.8 | shadow_only | 178 | 0.7758 | -0.172854 | 5m/5m/-- |
| 5m 扫低收回环境确认 学习版 ATR2.2 | shadow_only | 461 | 0.6103 | -0.278679 | 5m/5m/-- |
| 5m 假突破反转环境确认 学习版 ATR2.2 | shadow_only | 158 | 1.1363 | 0.090873 | 5m/5m/-- |
| 5m 弱势回抽结构确认 学习版 ATR2.2 | shadow_only | 391 | 0.9143 | -0.061792 | 5m/5m/-- |

## 15M

| Candidate | Tier | Trades | PF | Expectancy R | Formal data plan |
| --- | --- | ---: | ---: | ---: | --- |
| 15m 趋势回踩双趋势确认 因子后继 ATR1.2 | research_eligible | 142 | 1.1362 | 0.090261 | 15m/5m/-- |
| 15m 趋势回踩波动环境确认 因子后继 ATR1.2 | research_eligible | 95 | 1.0438 | 0.03006 | 15m/5m/-- |
| 15m 假突破弱趋势反转 因子后继 ATR1.2 | research_eligible | 114 | 1.2845 | 0.1795 | 15m/5m/-- |
| 15m 弱势回抽市场斜率确认 因子后继 ATR1.2 | research_eligible | 101 | 1.4252 | 0.258481 | 15m/5m/-- |
| 15m 弱势回抽区间衰竭 影子候选 ATR1.2 | shadow_only | 243 | 0.7054 | -0.24164 | 15m/5m/-- |

## 1H

| Candidate | Tier | Trades | PF | Expectancy R | Formal data plan |
| --- | --- | ---: | ---: | ---: | --- |
| 1H 突破回踩 BTC 顺势确认 因子后继 ATR1.2 | shadow_only | 540 | 1.0163 | 0.011041 | 1h/5m/15m |
| 1H 深弱势扫低收回 因子后继 ATR1.2 | research_eligible | 249 | 1.3396 | 0.194421 | 1h/5m/15m |
| 1H 假突破事件窗口反转 影子候选 ATR1.2 | shadow_only | 4423 | 0.7142 | -0.214683 | 1h/5m/15m |
| 1H 弱势回抽窗口失败 影子候选 ATR1.2 | shadow_only | 19208 | 0.8166 | -0.132898 | 1h/5m/15m |
| 1H 趋势回踩分步确认 影子候选 ATR1.2 | shadow_only | 16496 | 0.7519 | -0.183319 | 1h/5m/15m |

## 4H

| Candidate | Tier | Trades | PF | Expectancy R | Formal data plan |
| --- | --- | ---: | ---: | ---: | --- |
| 4H 牛市恢复收回 ATR1.5 持有24 | research_eligible | 1870 | 1.1947 | 0.11548567 | 4h/15m/1h |
| 4H 牛市恢复收回 ATR1.8 持有24 | research_eligible | 1764 | 1.2509 | 0.13573447 | 4h/15m/1h |
| 4H 牛市恢复收回 ATR2.0 持有24 | research_eligible | 1723 | 1.2614 | 0.13571039 | 4h/15m/1h |
| 4H 牛市恢复收回 ATR2.0 持有30 | research_eligible | 1687 | 1.2263 | 0.12497024 | 4h/15m/1h |
| 4H 牛市恢复收回 ATR2.0 持有36 | research_eligible | 1655 | 1.2382 | 0.13556526 | 4h/15m/1h |

## 1D

| Candidate | Tier | Trades | PF | Expectancy R | Formal data plan |
| --- | --- | ---: | ---: | ---: | --- |
| 1D 趋势突破回踩 ATR2.0 | research_eligible | 265 | 1.6211 | 0.30255811 | 1d/1h/4h |
| 1D 趋势压缩释放 ATR2.0 | research_eligible | 176 | 1.3988 | 0.20454091 | 1d/1h/4h |
| 1D 广谱压缩释放 ATR2.0 | research_eligible | 181 | 1.3594 | 0.18732431 | 1d/1h/4h |
| 1D 超卖扫低收回 ATR1.2 影子 | shadow_only | 16 | 1.6075 | 0.31026875 | 1d/1h/4h |
| 1D 超卖扫低收回 ATR1.0 影子 | shadow_only | 17 | 1.5699 | 0.31028235 | 1d/1h/4h |

## Boundaries

- targetR 固定不低于 2R；手续费、滑点和压力测试保持不变。
- 选择只使用开发、时间验证和符号留出证据；锁定样本不参与选择。
- 4H 正式数据计划复用 15m/1h，1D 复用 1h/4h，避免重复下载。
- 正式候选池只包含 OKX instCategory=1 加密 USDT 永续，并按 24H 报价成交额排序。
- 当前 Top50 是采集时点快照，不是历史逐时点成分；幸存者与上市偏差仍需单独稳健性验证。
- 研究筛选不会创建 Demo 或 Live Release，也不会调用交易接口。
