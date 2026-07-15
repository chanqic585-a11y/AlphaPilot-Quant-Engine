# 候选证据闭环锁定验证预注册

- 预注册哈希：`f869efb60ec4aedd20777b3dd3939b03aec10d8232c2220cf78a96d69c956f9b`
- 候选版本：8
- 去重后家族：7
- 主验收风险模型：模型一（单笔账户风险 0.25%）
- 模型二、模型三：仅敏感性观察，不能挽救主模型失败
- 研究边界：不恢复归档版本，不授予执行资格，不创建订单

## 候选队列

- A：1H 深弱势扫低收回，因子后继 ATR1.2 (`strategy_version_05c158de451321444bd1ef4485305b239a0d1bdb67b369f08f95a53295bd4d8e`)
- A：1D 广谱压缩释放 ATR2.0 (`strategy_version_0dc7701b4b48a6d2d3eaf727bfec274b5ca93016a5ea9aa862ffcc7f3ebe9b1b`)
- A：1D 趋势压缩释放 ATR2.0 (`strategy_version_a80c785eebf379a311de35b1697e39956849177a157f2d789aaeed433f3a80e3`)
- A：1D 趋势突破回踩 ATR2.0 (`strategy_version_c0afa97d531616a24d020e2aad5acd5df1168b41e7acbccab330549821aaa7d8`)
- B：1H 突破回踩 BTC 顺势确认，因子后继 ATR1.2 (`strategy_version_a2c0736f1f1de60ef2e571761970cbf64c35688ebc4631c55c2dc6570a557778`)
- C：15m 假突破弱趋势反转，因子后继 ATR1.2 (`strategy_version_5f27f24019c5fff46eaf083dc5a57c78029afb8f3c8fe3bab4f3dbe3093a8785`)
- C：1D 超卖扫低收回 ATR1.2 影子 (`strategy_version_c308c66aeb070009e17ff1eaeb63177d4c17647c6679ca13d8dd49a011d84085`)

## 锁定规则

- 信号定义、方向、周期、阈值、成本模型、风险模型和门槛在查看结果前冻结。
- 1D 需要至少 365 天且有效交易数不少于 50；30–49 笔仅探索。
- 缺少无污染锁定样本或 point-in-time 宇宙证据时只能诊断，不能通过。
- Bootstrap 和 Monte Carlo 正式运行均为 5,000 次，使用登记种子。
- NoTrade 与简单方向基线只用于比较，不能授予通过。
