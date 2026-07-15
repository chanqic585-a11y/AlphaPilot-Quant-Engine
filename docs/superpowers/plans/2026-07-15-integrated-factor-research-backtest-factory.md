# AlphaPilot 第三阶段更新版：外部研究资产、加密因子实验室与回测优先工厂

> **执行状态前提**：阶段 1「OKX Demo 可交易币池与工程烟测」和阶段 2「完整本地模拟退役与无盈亏影子观察」已经完成、提交、推送并通过各自退出门。
> **本文件替代**：`docs/superpowers/plans/2026-07-15-backtest-first-research-factory.md`。旧文件保留为历史记录，在文件头部标记 `supersededBy`，不得删除。
> **执行方式**：建议使用 `superpowers:subagent-driven-development` 或 `superpowers:executing-plans`，按复选框逐项完成。
> **核心目标**：把 Vibe-Trading、Alpha191 因子手册、`yydhYYDH/alpha101` 的可复用研究思想，与 AlphaPilot 自己的 Funding、Open Interest、Basis、清算、Point-in-Time 币池、真实成本、预注册、Purged Walk-forward 和锁定留出体系结合，完成一次有限预算、可复现、不会强制制造赢家的正式研究 Campaign。

---

## 1. 阶段定位

第三阶段内部重构为三个子阶段：

```text
阶段 3A：外部研究资产审计与安全因子基础设施
阶段 3B：加密数据就绪、单因子验证、去重与冻结
阶段 3C：市场机制 + 精选因子的正式回测 Campaign
```

原第三阶段的核心原则继续保留：

```text
真实数据先于绩效
预注册先于结果
事件预筛先于完整回测
5 折 Purged Walk-forward
Embargo
最终锁定 Holdout
基础 / 1.5 倍 / 2 倍成本压力
多重试验校正
有限预算
正式通过数为 0 也是有效结果
```

本阶段不是：

```text
把 191 个因子变成 191 条策略
把遗传搜索当作赢家制造器
把外部仓库整库合并进 AlphaPilot
恢复旧归档策略
进入 Demo 或实盘
```

---

## 2. 与已完成阶段的接口

阶段 3 不重新实现阶段 1、阶段 2。

执行前只验证以下只读契约仍然成立：

```text
阶段 1：
- 已有经过认证的 OKX Demo 可交易合约交集服务
- 已有隔离的工程烟测 Release 与工程烟测账本
- 工程烟测不参与策略成绩

阶段 2：
- 完整本地模拟已永久停用
- 历史本地模拟数据只读保留
- 当前旧 Release 已标记为 legacy_diagnostic
- 已有无持仓、无虚拟权益、无 PnL 的轻量影子观察
```

如果接口不存在或状态与已完成报告不一致：

```text
statusZh = 前置阶段契约不一致
停止第三阶段
不得暗中重新开启本地模拟
```

---

## 3. 仓库与目录

主要执行仓库：

```text
D:\Codex-Workspace\AlphaPilot-Quant-Engine
```

研究数据根目录：

```text
D:\Codex-Workspace\回测数据
```

文档归档仓库：

```text
D:\Codex-Workspace\AlphaPilot-Docs
```

外部只读参考目录建议：

```text
D:\Codex-Workspace\external\Vibe-Trading
D:\Codex-Workspace\external\alpha101
```

只读检查、不修改业务逻辑：

```text
D:\Codex-Workspace\AlphaPilot-Control-Console
D:\Codex-Workspace\trade-discipline-journal
```

---

## 4. 必须读取的 AlphaPilot 资料

```text
README.md
AGENTS.md / 仓库规则
规矩文档
D:\Codex-Workspace\踩坑日志.txt
```

历史研究基线：

```text
reports/full_archived_strategy_analysis_summary.md
reports/full_archived_strategy_cross_strategy_patterns.json
reports/full_archived_strategy_negative_rules.json
reports/full_archived_strategy_prohibited_routes.json
reports/candidate_evidence_closure_summary.md
reports/candidate_evidence_closure_report.json
reports/candidate_evidence_closure_leaderboard.csv
```

策略准则：

```text
D:\Codex-Workspace\AlphaPilot-Docs\architecture\AlphaPilot_Strategy_Generation_Core_Principles.md
```

旧阶段计划：

```text
docs/superpowers/plans/2026-07-15-backtest-first-research-factory.md
```

任务开始前已有未提交文件，尤其：

```text
reports/archived_failed_strategy_failure_attribution_summary.md
```

必须记录为 `preExistingChanges`，不覆盖、不 stage、不 reset、不混入提交。

---

## 5. 外部研究资料

### 5.1 Vibe-Trading

来源：

```text
HKUDS/Vibe-Trading
```

实施时必须：

```text
1. 查询实际审计时的 Git Commit。
2. 固定 SHA，不跟随 main 自动更新。
3. 记录 License。
4. 只读审计，不作为运行时依赖。
```

允许选择性适配：

```text
因子算子接口
Alpha Zoo 元数据思想
IC / RankIC / IR
分层净值
因子相似度和衰减诊断
Monte Carlo / Bootstrap
生成策略代码的 AST 安全检查思想
```

参考后重写：

```text
GTJA Alpha191 公式实现
加密回测成本接口
OKX 公共数据 Loader
Funding / Basis 研究模板
```

拒绝采用：

```text
完整 Agent Runtime
MCP 总体框架
Shadow Account
实盘连接
默认策略晋级门槛
整库前端
```

### 5.2 Alpha191 因子公式手册

输入文件：

```text
Alpha191因子公式小白学习手册.pdf
```

归档建议：

```text
D:\Codex-Workspace\AlphaPilot-Docs\references\Alpha191因子公式小白学习手册.pdf
```

手册用途：

```text
公式词典
字段和算子解释
因子分类
实现风险提醒
人工校对依据
```

手册不是：

```text
直接交易方向
现成策略清单
Funding / OI / Basis 的替代品
```

必须特别审查：

```text
BANCHMARKINDEX / BENCHMARKINDEX
COVIANCE / COVARIANCE
SMA
WMA
SMEAN
REGBETA
REGRESI
条件表达式
分母为零
窗口初值
```

公式存在歧义时：

```text
保持 unresolved
不得猜测实现
不得进入首批因子
```

### 5.3 yydhYYDH/alpha101

来源：

```text
yydhYYDH/alpha101
```

审计时固定实际 Commit。

有价值的参考：

```text
加密宽表数据面板
Alpha101 风格表达式 AST
算子注册与复杂度控制
时间 Fold 与币种池分割
IC / ICIR / 换手 / 回撤
多空横截面组合
因子相关性聚类
因子暴露分析
```

禁止直接采用：

```text
Python eval 表达式运行时
今天的 TopN 币池作为历史 PIT
无限遗传搜索
未经澄清的源代码复制
```

许可证处理：

```text
如果仓库声明和实际 License 文件不一致，
状态标记 license_ambiguous。
只允许依据数学公式和接口思想重新实现，
不得直接复制代码或设为运行时依赖。
```

遗传搜索默认：

```text
关闭
```

后续若单独批准，只能进入新的探索 Campaign，不能在本轮正式 Holdout 上搜索。

### 5.4 CryptoAgentPro.beta

第三阶段只记录为外部采用矩阵中的：

```text
阶段 4 工程参考
```

第三阶段拒绝采用：

```text
其自有回测引擎
Paper Account
AI 在线热调参
策略自动切换
马丁策略
止损放宽逻辑
```

---

## 6. 全局安全和研究边界

本阶段禁止：

```text
访问 Demo API Key
保存任何 API Key
接 Trade API
接 Withdraw API
读取账户或持仓
创建订单
执行 exchange Dry-run
自动交易
修改 App
重新启用完整本地模拟
```

研究硬规则：

```text
缺失值保持 null / unavailable
不静默 fillna(0)
不静默 forward-fill 长缺口
不使用未来数据
不使用今日币池回填历史
不在 Holdout 选因子
不在 Holdout 选阈值
不事后删除亏损币
不降低门槛制造通过
不无限组合因子
不把参数变体伪装成独立家族
同 K 线止盈止损冲突采用止损优先
风险统一用 R 表示
初始目标原则上至少 2R
初始止损不得放宽
```

---

# 阶段 3A：外部研究资产审计与安全因子基础设施

## 3A-1 冻结外部参考

建议新增：

```text
alphapilot/external_research/reference_manifest.py
scripts/audit_external_research.ps1
tests/external_research/test_reference_manifest.py
```

生成：

```text
reports/external_research/vibe_trading_reference_manifest.json
reports/external_research/alpha101_reference_manifest.json
reports/external_research/alpha191_manual_reference_manifest.json
```

字段：

```text
referenceId
sourceType
repositoryOrFile
commitOrHash
licenseStatus
retrievedAt
readOnly
sourcePath
```

验收：

- [ ] Vibe-Trading 固定 Commit。
- [ ] alpha101 固定 Commit。
- [ ] Alpha191 PDF 计算 SHA-256。
- [ ] 外部参考只读。
- [ ] Hash 变化必须创建新 Reference ID。
- [ ] 不将外部仓库放入 AlphaPilot 运行时依赖。

---

## 3A-2 外部采用矩阵

建议新增：

```text
alphapilot/external_research/adoption_matrix.py
tests/external_research/test_adoption_matrix.py
```

状态：

```text
适配采用
参考后重写
仅文档参考
阶段 4 参考
拒绝采用
许可证阻塞
等待审查
```

生成：

```text
reports/external_research/external_adoption_matrix.json
reports/external_research/external_adoption_summary.md
THIRD_PARTY_NOTICES.md
```

每项记录：

```text
来源
固定 SHA
原模块
目标 AlphaPilot 模块
是否复制代码
License
采用理由
拒绝理由
测试计划
```

---

## 3A-3 安全因子算子层

建议新增：

```text
alphapilot/factor_lab/operators.py
alphapilot/factor_lab/operator_contract.py
tests/factor_lab/test_operators.py
tests/factor_lab/test_operator_contract.py
```

首批算子：

```text
rank
zscore
scale
winsorize
delay
delta
ts_rank
ts_corr
ts_cov
ts_mean
ts_std
ts_sum
ts_product
ts_min
ts_max
ts_argmin
ts_argmax
ts_ema
ts_slope
decay_linear
safe_div
signed_power
count
sum_if
rolling_beta
rolling_residual
conditional_select
```

硬规则：

```text
NaN 传播
禁止 +/-inf
分母为 0 返回 NaN
delay / delta 只能访问过去
禁止负 shift
滚动窗口必须声明 min_periods
截面 rank 使用当时 PIT 币池
输出排序确定性
```

---

## 3A-4 白名单表达式解释器

禁止把外部 `eval()` 运行时带入 AlphaPilot。

建议新增：

```text
alphapilot/factor_lab/expression_ast.py
alphapilot/factor_lab/expression_parser.py
alphapilot/factor_lab/expression_runtime.py
alphapilot/factor_lab/generated_code_guard.py
tests/factor_lab/test_expression_runtime.py
tests/factor_lab/test_generated_code_guard.py
```

允许：

```text
字面量
字段引用
白名单算子
四则运算
比较
条件表达式
显式临时变量
```

拒绝：

```text
eval
exec
__import__
属性访问
任意下标
动态函数
网络
subprocess
环境变量
任意文件读写
动态 import
类级可执行语句
```

复杂度限制：

```text
默认最大深度 <= 4
默认最大算子数 <= 8
禁止 rank(rank(...))
禁止 ts_mean(ts_mean(...))
禁止 ts_corr(ts_corr(...))
禁止无解释的重复嵌套
```

---

## 3A-5 Alpha191 公式注册表

建议新增：

```text
alphapilot/factor_lab/alpha191/schema.py
alphapilot/factor_lab/alpha191/registry.py
alphapilot/factor_lab/alpha191/manual_reference.py
alphapilot/factor_lab/alpha191/external_crosscheck.py
tests/factor_lab/alpha191/test_registry.py
```

每个因子记录：

```text
factorId
displayNameZh
categoryZh
manualPage
manualFormula
vibeReference
alpha101Reference
canonicalFormula
requiredColumns
requiredOperators
windows
crossSectional
timeSeries
requiresBenchmark
formulaStatus
cryptoAdaptationStatus
implementationHash
notesZh
```

公式状态：

```text
一致
排版差异
语义替换
平台口径差异
公式冲突
手册歧义
股票专属
待人工确认
```

---

## 3A-6 加密适配规则

股票概念映射：

| 股票概念 | 加密适配 |
|---|---|
| 股票池 | Point-in-Time 可交易永续合约池 |
| 指数 | BTC、ETH 或 PIT 等权市场基准 |
| 行业 | 币种类别或相关性簇 |
| 市值 | 流通市值、成交额或 OI 分层 |
| 停牌 | 暂停、下架、不可交易状态 |
| 日成交额 | 永续与现货成交额 |
| Beta | BTC Beta / ETH Beta |
| 日频窗口 | 按经济时间跨度重新映射，不按 K 线数量机械替换 |

禁止：

```text
把 20 日直接替换成 20 根 5m K 线
缺失 Benchmark 时静默使用截面均值
未知 SMEAN 时自行猜实现
```

---

## 3A-7 首批因子种子冻结

注册全部 191 个因子元数据，但第一轮最多预注册：

```text
32 个种子因子
```

类别配额建议：

| 类别 | 上限 |
|---|---:|
| 量价相关 / 协同 | 6 |
| 成交量 / 资金活跃 | 5 |
| 波动振幅 / 日内结构 | 5 |
| 排序位置 / 相对强弱 | 4 |
| 市场联动 / 回归 | 4 |
| 动量反转 / 均值回复 | 4 |
| 条件统计 / 规则触发 | 2 |
| 综合价格形态 | 2 |

选择依据只允许：

```text
公式无歧义
字段可用
算子已测试
无股票专属硬依赖
无静默近似
加密解释清楚
```

不得依据：

```text
收益
IC
Sharpe
回测排名
```

生成：

```text
research/factor_preregistrations/alpha191_seed_v1.json
```

必须在计算绩效前 Commit。

---

## 3A-8 数值交叉验证

对种子因子使用：

```text
合成宽表
固定随机种子
NaN
常数列
分母为零
短窗口
完整窗口
极值
```

对比：

```text
AlphaPilot 实现
Vibe-Trading 固定参考实现
alpha101 固定参考实现
手工小样本计算
```

Vibe 和 alpha101 只作为参考，不是绝对真值。

输出状态：

```text
exact_match
tolerance_match
known_semantic_deviation
formula_conflict
unexpected_mismatch
```

公式冲突未解决：

```text
停止该因子
```

---

## 3A 退出门

必须同时满足：

```text
外部 Commit/PDF Hash 已冻结
License 与来源完整
采用矩阵完成
安全算子测试通过
白名单表达式解释器通过
Alpha191 元数据注册完成
歧义公式未静默实现
种子因子 <= 32
种子选择未使用绩效
数值交叉验证有完整报告
```

不通过：

```text
阶段 3B 不启动
```

---

# 阶段 3B：加密数据就绪、单因子验证、去重与冻结

## 3B-1 数据目录与身份

数据目录：

```text
D:\Codex-Workspace\回测数据\raw
D:\Codex-Workspace\回测数据\normalized
D:\Codex-Workspace\回测数据\derived
D:\Codex-Workspace\回测数据\manifests
D:\Codex-Workspace\回测数据\snapshots
```

每个数据集必须拥有：

```text
datasetId
dataType
provider
exchange
marketType
symbols
timeframe
startTime
endTime
rowCount
timezone
schemaVersion
contentHash
isPointInTime
isProxy
licenseOrUsageNote
```

原始文件只读，标准化和派生文件不可覆盖原始数据。

---

## 3B-2 数据源注册

必须审计：

```text
OHLCV
VWAP / Amount
永续成交量
Funding
Open Interest
现货价格
永续价格
Basis
真实清算
清算代理
价差 / 滑点 / 深度代理
Point-in-Time 币池
上市 / 下架 / 暂停状态
市场宽度
BTC / ETH 基准
类别或相关性簇
```

真实与代理分开。

缺失保持：

```text
null / unavailable
```

---

## 3B-3 数据准备与结果运行隔离

显式数据准备：

```powershell
scripts\prepare_research_data.ps1 -AuditOnly
scripts\prepare_research_data.ps1 -Collect
scripts\prepare_research_data.ps1 -Normalize -BuildDerived -FreezeSnapshot
```

正式因子和策略运行：

```text
禁止联网
禁止静默下载
禁止替换缺失数据
禁止更新 PIT 历史币池
```

---

## 3B-4 时间对齐与防未来泄漏

统一主键：

```text
timestampUtc
exchange
marketType
instrumentId
```

要求：

```text
只允许 backward as-of join
记录 sourceTimestamp
记录 ageSeconds
超过阈值标记 stale
禁止 nearest 命中未来
Funding 使用当时已公开信息
Basis 现货/永续时间差受限
PIT 币池使用当时快照
```

---

## 3B-5 Point-in-Time 币池

正式横截面研究必须使用当时：

```text
可交易
已上市达到最短时间
未暂停或下架
数据完整
流动性合格
```

的合约。

字段：

```text
snapshotTimeUtc
instrumentId
listedAt
delistedAt
tradingState
quoteVolume24h
openInterestQuote
spreadProxyBps
included
reasonZh
```

历史 PIT 不完整：

```text
横截面结果只能标记为诊断
不能单独获得正式资格
```

---

## 3B-6 统一 FactorDataPanel

建议新增：

```text
alphapilot/factor_lab/panel_schema.py
alphapilot/factor_lab/panel_builder.py
tests/factor_lab/test_panel_builder.py
```

宽表：

```text
index = timestampUtc
columns = instrumentId
```

面板字段：

```text
open
high
low
close
volume
amount
vwap
returns
funding
open_interest
basis
liquidation
spread_proxy
btc_return
eth_return
market_return
market_breadth
cap_or_liquidity_proxy
```

NaN 保留。

---

## 3B-7 研究周期

首批主周期：

```text
1h
4h
1d
```

15m：

```text
只有价差和滑点数据覆盖充分时启用
```

5m：

```text
首批 Alpha191 Campaign 默认禁用
```

理由：

```text
短周期微观结构和成本占主导，
纯 OHLCV 因子不应先于盘口数据验证。
```

---

## 3B-8 因子评估

每个因子、方向、周期输出：

```text
coverage
missingRate
IC
RankIC
IC mean
IC std
ICIR
IC positive ratio
Top-Bottom Spread
分层单调性
换手率
基础成本后 Spread
1.5 倍成本后 Spread
最大回撤
按 Fold
按年份
按月份
按市场状态
按币种池分割
暴露：Beta、动量、波动、流动性、反转、Funding
```

原方向与反方向都可评估，但每个方向计入试验账本。

---

## 3B-9 因子试验预算

建议上限：

```text
种子因子 <= 32
每个因子正式周期 <= 2
每周期 Forward Horizon <= 2
每个方向都计入 Trial
总正式因子 Trial <= 192
```

所有 Trial 必须预注册并进入：

```text
factor_trial_ledger.json
```

必须报告：

```text
Benjamini-Hochberg FDR
```

条件允许时：

```text
Deflated Sharpe
PBO
```

---

## 3B-10 时间与币种池交叉验证

至少：

```text
5 个 Purged 时间 Fold
3 个确定性 PIT 币种池分割
Embargo
```

不能直接照搬外部仓库的简单时间切分；以 AlphaPilot 的 Split Policy 为准。

Forward Horizon 重叠时：

```text
标记为 horizon_sensitivity
不能与单步结果直接比较 Sharpe
```

---

## 3B-11 因子去重与聚类

至少计算：

```text
因子值 Spearman 相关
RankIC 时间序列相关
Top 组成员重合率
Bottom 组成员重合率
因子 PnL 相关
事件重合率
方向一致率
换手相关性
```

标签：

```text
|相关性| >= 0.97：高度重复
|相关性| >= 0.90：同源因子簇
```

每簇最多保留：

```text
1 个主代表
1 个备选代表
```

同源变体不得当作独立 Alpha 计票。

---

## 3B-12 正向与负向控制

正向控制：

```text
在合成宽表中植入可检测的横截面正优势
```

负向控制：

```text
随机因子
时间打乱因子
随机方向因子
```

验收：

```text
正向控制应被识别
负向控制不得获得因子资格
```

控制组永远不能进入真实候选清单。

---

## 3B-13 因子资格门

因子获得“研究特征资格”至少要求：

```text
覆盖达到门槛
公式无未解决歧义
RankIC / Spread 方向在至少 3/5 Fold 一致
FDR 校正后仍有支持
Top-Bottom Spread 基础成本后 > 0
1.5 倍成本后不为负
换手和回撤受控
不由单一币种主导
不由单一月份主导
不属于高度重复因子
```

通过只表示：

```text
eligibleResearchFeature=true
```

不表示：

```text
strategyQualified
demoApproved
executionEligible
```

---

## 3B-14 市场机制与因子用途矩阵

生成：

```text
reports/factor_lab/factor_market_mechanism_matrix.json
```

规则：

```text
每条策略一个核心市场机制
最多 2 个合格因子
因子只能承担：
- 确认
- 排序
- 否决
- 风险上下文
```

示例：

| 核心机制 | 因子用途 |
|---|---|
| Funding / OI 拥挤 | 量价背离、波动耗竭确认 |
| 价格 / OI 趋势 | 相对强弱排序、量价协同确认 |
| 清算耗竭 | 日内结构、影线回收确认 |
| Basis 偏离 | 相对弱势、成交活跃下降确认 |
| 市场宽度 | 横截面强弱构建组合 |
| 特异性冲击 | 回归残差、短期反转 |

---

## 3B-15 数据与因子冻结

生成：

```text
research/data_snapshots/<snapshotId>.json
research/factor_shortlists/<factorShortlistId>.json
```

记录：

```text
dataManifestHash
dataSnapshotHash
externalReferenceManifestHash
factorRegistryHash
factorImplementationHashes
factorTrialLedgerHash
factorClusterHash
eligibleFactors
rejectedFactors
createdAt
GitCommit
```

---

## 3B 退出门

必须满足：

```text
数据 Manifest 可验证
正式数据全部有 Hash
数据准备与结果运行隔离
PIT 状态明确
正向控制通过
负向控制未放行
因子 Trial Ledger 完整
FDR 完成
因子聚类完成
因子 Shortlist 已冻结，允许为空
至少 3 个独立市场机制家族数据就绪
至少 1 个家族使用非纯 OHLCV 数据
```

如果合格因子为 0，但市场机制家族 >=3：

```text
允许 3C 运行纯市场机制 Campaign
```

如果数据就绪家族 <3：

```text
停止，不进入 3C
```

---

# 阶段 3C：市场机制 + 精选因子的正式回测 Campaign

## 3C-1 Campaign 合约

保留预算：

```python
@dataclass(frozen=True)
class ExperimentBudget:
    maximumFamilies: int = 8
    maximumInitialVariantsPerFamily: int = 2
    maximumInitialCandidates: int = 16
    maximumStructuralRevisionsPerFamily: int = 1
    maximumFullBacktests: int = 48
```

数据分割：

```text
开发：55%
Purged Walk-forward：25%
最终锁定 Holdout：20%
Fold 数：5
必须有 Embargo
```

---

## 3C-2 候选市场机制

只能从数据就绪矩阵选择：

```text
Funding / OI 拥挤反转
价格 / OI 趋势延续
清算耗竭
Basis 偏离均值回归
市场宽度状态变化
高流动性横截面动量
特异性冲击回归
OI / 成交量确认的波动压缩突破
```

最多允许：

```text
2 个纯因子横截面家族
```

纯因子家族必须：

```text
因子已通过 3B
PIT 可用
组合 Beta 模型明确
成本和换手模型明确
```

---

## 3C-3 假设规格

每个候选必须包含：

```text
marketMechanismId
因果或结构性理由
方向
周期
事件定义
失效条件
初始止损
目标 >= 2R
最大持有期
必需数据
factorConfirmations
factorRanking
factorVetoes
预期失败市场状态
```

禁止：

```text
Alpha001 高就买
Alpha043 低就卖
多个因子直接求和
传统指标堆叠伪装新机制
```

---

## 3C-4 不可变预注册

生成：

```text
research/preregistrations/<campaignId>.json
```

必须包含：

```text
externalReferenceManifestHash
dataSnapshotHash
factorShortlistHash
假设与变体
因子用途
币池策略
55/25/20 边界
5 个 Fold
Embargo
Holdout Hash
样本门槛
事件预筛门槛
基础 / 正式门槛
基础 / 1.5x / 2x 成本
预算
停止规则
同 K 线规则
```

必须先 Commit、Push，再运行结果。

---

## 3C-5 事件级预筛

事件字段：

```text
hypothesisId
familyId
variantId
timestamp
symbol
direction
timeframe
coreMechanism
factorDefinitionHashes
factorRoles
entryReference
stopReference
targetReference
maximumHoldBars
split
foldId
dataHash
grossR
feesR
slippageR
fundingR
spreadProxyR
netR
```

预筛门槛：

```text
开发区间基础成本 PF >= 1.08
开发区间平均净 R >= 0.03
正开发月份 >= 60%
最低样本和覆盖通过
```

最低样本：

```text
15m：>=300 事件，>=12 个月
1h：>=150 事件，>=12 个月
4h：>=80 事件，>=18 个月
1d：>=40 事件，>=24 个月
```

5m 默认不进入首轮 Campaign。

未通过：

```text
停止，不生成完整 Freqtrade 策略
```

---

## 3C-6 完整 Freqtrade 回测

只有预筛幸存者进入。

必须验证：

```text
事件定义 Hash == 策略定义 Hash
止损、目标、持有期一致
因子定义 Hash 一致
因子用途一致
PIT 币池一致
方向一致
```

完整回测 Runner：

```text
禁止联网
禁止下载
禁止替换数据
```

---

## 3C-7 成本场景

```text
base：
手续费 + 滑点 + Funding + Spread Proxy

stress_1_5x：
可变执行成本 × 1.5

stress_2x：
可变执行成本 × 2.0
```

真实成本缺失时：

```text
保持 null
可另给预注册保守代理
真实与代理分开报告
```

---

## 3C-8 多重试验与稳健性

必须报告：

```text
原始 p 值
FDR 调整值
Fold 离散度
市场状态覆盖
样本量
数据完整度
币种贡献集中度
月份贡献集中度
```

条件满足时：

```text
Deflated Sharpe
PBO
```

否则：

```text
null + 原因
```

---

## 3C-9 基础和正式门槛

基础回测通过：

```text
OOS PF >= 1.05
OOS 平均净 R > 0
OOS 总净 R > 0
最大回撤 <= 25%
至少 3/5 Fold 平均净 R > 0
基础成本已计入
最低样本和覆盖通过
无未来函数
```

正式回测通过：

```text
OOS PF >= 1.15
OOS 平均净 R >= 0.05
OOS 总净 R > 0
最大回撤 <= 20%
至少 4/5 Fold 平均净 R > 0
1.5x 成本 PF >= 1.05
1.5x 成本平均净 R > 0
单一币种正收益贡献 <= 35%
单一月份正收益贡献 <= 35%
Holdout 在最终评估前未被访问
```

每个 Gate 返回：

```text
passed
observed
required
evidenceHash
reasonZh
```

---

## 3C-10 因子发现探索支线

`alpha101` 遗传表达式搜索默认关闭。

如用户以后单独批准：

```text
1. 创建新的 Factor Discovery Campaign ID。
2. 使用与正式 Campaign 不同的开发数据。
3. 不得访问本轮 Holdout。
4. 初始表达式 <=30。
5. 代数 <=3。
6. 最大深度 <=4。
7. 最大算子 <=8。
8. 所有表达式计入 Trial Ledger。
9. 发现结果只能进入下一轮 3B 因子验证。
10. 不得在同一 Campaign 直接正式通过。
```

---

## 3C-11 失败归因

状态至少包括：

```text
外部参考不可验证
许可证阻塞
公式不可复现
数据不足
PIT 不足
因子无效
因子高度重复
市场机制预筛失败
Freqtrade 翻译不一致
样本外失败
成本失败
Walk-forward 失败
集中度失败
Holdout 失败
多重检验失败
正式通过
```

---

## 3C-12 结果产物

外部参考：

```text
reports/external_research/*
THIRD_PARTY_NOTICES.md
```

因子层：

```text
reports/factor_lab/alpha191_formula_registry.json
reports/factor_lab/alpha191_formula_conflicts.json
reports/factor_lab/alpha191_crypto_adaptation_matrix.json
reports/factor_lab/alpha191_numeric_cross_validation.json
reports/factor_lab/factor_benchmark_report.json
reports/factor_lab/factor_trial_ledger.json
reports/factor_lab/factor_clusters.json
reports/factor_lab/factor_shortlist.json
reports/factor_lab/factor_market_mechanism_matrix.json
```

数据层：

```text
reports/backtest_screening/data_readiness/*
research/data_snapshots/<snapshotId>.json
```

Campaign：

```text
research/preregistrations/<campaignId>.json
reports/backtest_screening/<campaignId>/campaign_summary.json
reports/backtest_screening/<campaignId>/campaign_summary.md
reports/backtest_screening/<campaignId>/candidate_results.parquet
reports/backtest_screening/<campaignId>/gate_matrix.json
reports/backtest_screening/<campaignId>/failure_attribution.json
reports/backtest_screening/<campaignId>/experiment_budget.json
reports/backtest_screening/<campaignId>/artifact_manifest.json
reports/backtest_screening/<campaignId>/console_projection.json
reports/backtest_screening/<campaignId>/formal_pass_evidence/*.json
```

Formal evidence 额外包含：

```text
externalReferenceManifestHash
factorRegistryHash
factorShortlistHash
factorDefinitionHashes
factorRoles
marketMechanismId
dataSnapshotHash
```

---

## 7. 建议代码结构

```text
alphapilot/external_research/
alphapilot/factor_lab/
alphapilot/factor_lab/alpha191/
alphapilot/research_screening/
```

建议脚本：

```text
scripts/audit_external_research.ps1
scripts/build_alpha191_registry.ps1
scripts/prepare_research_data.ps1
scripts/run_factor_benchmark.ps1
scripts/run_backtest_screening.ps1
```

默认只打印计划，显式 `-Run` 或 `-RunAll` 才执行。

---

## 8. 提交顺序

至少六个独立提交：

```text
1. Audit external research references
2. Build safe factor operators and formula registry
3. Preregister curated crypto factor seed
4. Record data-ready factor benchmark and shortlist
5. Preregister factor-enriched market hypothesis campaign
6. Record bounded backtest-first campaign results
```

每一步：

```text
测试
Commit
Push
确认工作区
再进入下一步
```

---

## 9. 验证命令

```powershell
cd D:\Codex-Workspace\AlphaPilot-Quant-Engine

python -m pytest tests/external_research -q
python -m pytest tests/factor_lab -q
python -m pytest tests/research_screening -q
python -m pytest tests -q

python -m compileall alphapilot
python -m alphapilot.scripts.validate_config
powershell -ExecutionPolicy Bypass -File scripts\check_safety.ps1
git diff --check
```

必须扫描：

```text
eval / exec
动态网络下载
Holdout 指标进入选择代码
无界循环
动态降低门槛
Trade API
Withdraw API
Demo 凭证访问
Live 激活
```

---

## 10. 阶段 3 最终退出门

第三阶段只有在以下全部满足时完成：

```text
外部参考与 License 已审计
公式注册和冲突报告完成
因子运行时不使用 eval
首批种子因子在结果前冻结
数据下载与结果运行隔离
PIT 状态明确
正向控制通过
负向控制未被放行
因子 Trial、FDR、聚类、去重完成
因子 Shortlist 已冻结，允许为空
至少 3 个独立市场机制数据就绪
至少 1 个家族使用非纯 OHLCV 数据
Campaign 已预注册并 Commit
事件预筛真实运行
完整回测只运行幸存者
5 个真实 Purged Fold 完整
Embargo 生效
Holdout 隔离
基础 / 1.5x / 2x 成本完整
预算未超限
所有失败保留
报告 Hash 可复现
没有 Demo / Live / Withdraw / Order 能力
```

最终状态：

```text
正式通过 = 0：
第三阶段仍然完成；
第四阶段生成 0 条策略验证 Release。

正式通过 > 0：
只输出正式通过 Evidence Bundle；
不得在第三阶段启动 Demo。
```

---

## 11. Codex 最终自检

必须输出：

```text
外部参考 Commit / PDF Hash
License 状态
采用矩阵
公式注册数量
公式冲突和歧义数量
种子因子数量
种子预注册 Hash
数值交叉验证结果
数据源覆盖
PIT 覆盖
Factor Panel 规模
因子 Trial 数
FDR 结果
因子簇数量
合格因子数量
因子 Shortlist Hash
正向 / 负向控制
数据 Snapshot ID / Hash / Commit
可测试市场机制家族数
Campaign ID
预注册 Hash / Commit
事件预筛通过数
完整回测数
5 折完整性
Holdout 访问次数
基础 / 1.5x / 2x 成本
基础通过数
正式通过数
最佳候选
失败归因
预算使用
是否使用 eval
是否运行全部 191 为策略
是否运行遗传搜索
是否结果运行时下载数据
是否访问 Demo 凭证
是否创建订单
全部测试和安全检查
Commit / Push / Tag
已知问题
下一步建议
```

---

## 12. 最终原则

```text
Vibe-Trading = 研究工程参考
Alpha191 手册 = 公式与人工校对依据
alpha101 = 加密因子面板和验证流程参考
AlphaPilot = 唯一权威实现
```

并坚持：

```text
市场机制是核心
因子只负责确认、排序、否决或风险上下文
因子通过不等于策略通过
回测通过不等于 Demo 批准
正式通过为 0 也是完整结果
```
