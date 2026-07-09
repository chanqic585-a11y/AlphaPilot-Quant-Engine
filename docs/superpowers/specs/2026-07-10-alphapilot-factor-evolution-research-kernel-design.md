# AlphaPilot Factor Evolution Research Kernel 设计

## 状态

- 设计日期：2026-07-10
- 设计状态：用户已确认
- 实现仓库：`D:\Codex-Workspace\AlphaPilot-Quant-Engine`
- 运行控制仓库：`D:\Codex-Workspace\AlphaPilot-Control-Console`
- 手机控制台仓库：`D:\Codex-Workspace\trade-discipline-journal`
- 首阶段晋级边界：研究候选通过硬门槛后可自动进入 OKX Demo；任何实盘 release 仍必须由用户人工批准。

## 目标

在不推翻现有回测、因子研究、沙盒、Control Console 和手机端的前提下，在 Quant Engine 内建立统一策略进化内核。系统需要持续完成：

1. 注册 point-in-time 数据快照。
2. 生成和验证因子表达式。
3. 去除语义重复和高度相关候选。
4. 使用抗过拟合的 walk-forward 流程评价因子和策略。
5. 使用可解释机器学习为候选排序和组合。
6. 将通过硬门槛的不可变策略包自动推进到 OKX Demo。
7. 监控漂移、成本和风险，并自动暂停或回滚 Demo release。
8. 只在用户人工批准不可变 live release 和风险预算后允许未来实盘机械执行。

系统不得以“自我进化”为理由绕过数据质量、风险、审计或人工实盘批准。

## 非目标

本设计不包含：

- 自动把新模型或新策略推进到实盘。
- AI 生成任意 Python 并直接执行。
- 在 Demo 或实盘中在线修改模型权重。
- 使用未来数据、当前币种池回填历史或静默覆盖旧数据。
- 将报告摘要、因子面板或同源变体当成独立可交易策略。
- 在第一阶段重写全部历史报告生成器、Control Console 或手机 App。
- 保证胜率、收益或盈利。

## 参考仓库审计

参考仓库：`shu476891497-hash/worldquant-miner`

本地只读审计位置：

```text
D:\Codex-Workspace\third_party\worldquant-miner
```

审计 commit：

```text
e29b2b5a206f57ceb0b5c8065c149e26e51521e9
```

允许吸收的架构思想：

- 表达式 AST 和白名单 DSL。
- 表达式规范化、语义去重和相关性筛选。
- 受限遗传变异和研究搜索策略。
- Bandit 分配研究预算。
- 因子质量退化监控。
- 回测结果存储、聚类和复盘反馈。

明确排除：

- 凭据登录、自动提交和论坛抓取。
- AI 自生成可执行模块。
- 任意 `eval` / `exec` 代码路径。
- 直接复制来源授权不清晰的源码。

参考仓库根目录没有实际 LICENSE 文件，且部分核心 Python 文件含 null bytes，无法通过 `compileall`。该仓库只作为概念来源，不作为依赖或代码基线。

## 当前基线

审计时的 AlphaPilot 状态：

- Quant Engine 已有手工因子、Alpha101/Alpha191 安全子集、市场状态、动态币种池、成本模型、回测和简单 walk-forward 阈值学习。
- V13.4.22 评价 16 个因子、124111 条样本，正式候选因子为 0。
- V13.5.8 产生 7 个自适应候选池，进入 local paper watch 的数量为 0。
- Strategy Artifact Index 包含 60 个 artifacts，但混合报告摘要、因子资产、策略变体和同源重复项。
- Control Console V13.10.5 有 24 条本地生命周期记录、4 条活跃记录和 0 条闭合学习样本。
- 5 条主前向候选在 2026-07-10 复核窗口到达时，真实前向日志为 0、真实闭合样本为 0；历史虚拟重放不能替代真实前向证据。

这些数据证明研究资产已经很多，但缺少统一事实源、抗过拟合晋级和真实 Demo 反馈闭环。

## 仓库职责

### Quant Engine

Quant Engine 是研究和版本事实源，负责：

- 数据、因子、实验、模型、策略和 release 注册。
- Factor DSL 编译与验证。
- 因子生成、去重、评价和组合。
- Purged walk-forward、成本压力和多重检验。
- Champion/challenger 模型评价。
- 候选晋级、漂移和回滚判断。
- 生成不可变 Demo Candidate Package 和 Live Candidate Package。

### Control Console

Control Console 是运行控制面，负责：

- 展示候选证据和 release 状态。
- 加载已经获准的 Demo release。
- 市场扫描、策略冲突仲裁和运行风险检查。
- OKX Demo 下单、生命周期和审计。
- 暂停、kill switch 和回滚操作。

Control Console 不现场训练模型，也不修改因子、策略参数或晋级门槛。

### 手机端

手机端是精简控制台，负责：

- 查看当前策略、信号、Demo 持仓、盈亏、风险和漂移。
- 暂停 Demo 或停用候选。
- 查看 live candidate 证据。
- 对 live release 和风险预算执行二次人工确认。

AI 不得代替用户完成实盘批准。

## 总体数据流

```text
Public Market Data
  -> Point-in-time Data Registry
  -> Factor DSL / Factor Registry
  -> Experiment Engine
  -> Strategy Evolution Engine
  -> Promotion and Rollback Gate
  -> Immutable Demo Release
  -> Control Console
  -> OKX Demo
```

未来实盘路径：

```text
Demo Evidence
  -> Live Candidate Package
  -> User Manual Release Approval
  -> Fixed Live Risk Envelope
  -> Mechanical Execution
```

用户批准的是策略 release 和风险预算，不需要逐单票据确认。任何新模型、新参数或风险预算扩大都必须重新人工批准。

## 本地注册库

元数据事实源：

```text
data/evolution_registry.sqlite
```

Parquet/Feather 继续保存大规模行情、特征和因子矩阵。SQLite 只保存标识、路径、校验和、状态、关系和审计事件。

核心表：

```text
DataSnapshots
FactorDefinitions
FactorRuns
Experiments
Models
StrategyFamilies
StrategyCandidates
PromotionDecisions
DemoReleases
LiveCandidatePackages
DriftEvents
AuditEvents
```

所有关键表使用 append-only 事件或不可变版本。状态变化不得覆盖历史证据。

## 标识和血缘

### dataSnapshotId

由以下内容生成稳定哈希：

- 数据源和交易所。
- 市场类型和币种池成员快照。
- 时间周期和时间范围。
- point-in-time cutoff。
- 文件列表及 SHA-256。
- 采集或导入版本。

### factorDefinitionId

由以下内容生成：

- 规范化 AST。
- 输入字段和字段版本。
- 时间延迟规则。
- 参数和窗口。
- 输出类型。

### factorRunId

绑定：

```text
factorDefinitionId + dataSnapshotId + codeCommit + configHash
```

### experimentId

绑定：

```text
factorRuns + splitDefinition + costModel + randomSeed + parameterHash + codeCommit
```

### modelId

绑定：

```text
algorithm + featureIds + trainWindow + hyperparameters + modelArtifactHash
```

### strategyCandidateId

绑定：

```text
strategyFamily + signalRules + modelId + riskRules + exitRules + experimentEvidence
```

### demoReleaseId

Demo release 必须绑定完整候选、风险预算、模型文件、代码 commit、数据证据、批准决定和 release checksum。

## 现有资产迁移

现有 JSON 报告保持原样，只作为展示产物。迁移器将其导入为 `legacy_evidence`：

1. 解析来源、生成时间和指标。
2. 判断是否具有完整入场、退出和风险规则。
3. 关联或创建策略家族。
4. 计算语义、信号和收益指纹。
5. 合并报告摘要和同源变体。
6. 缺少完整规则的对象保持 research evidence，不创建 StrategyCandidate。
7. 历史高指标不能直接形成 Demo release。

## 三层去重

### AST 规范化

忽略变量命名、空白和等价参数格式，计算表达式规范哈希。

### 信号行为指纹

在同一锁定验证集上比较：

- 触发时间重合率。
- 方向一致率。
- 目标币种重合率。
- 持仓窗口重合率。

### 收益相关性

比较成本后收益序列。高度相关且无增量价值的候选归入同一策略家族，不重复占用 Demo 风险预算。

## Point-in-time 规则

- 动态币种池保存历史时点成员。
- 特征只能读取信号时点前已知数据。
- Funding、open interest 和 instrument metadata 保存可用时间。
- Forward label 只用于评价。
- 数据修订生成新快照，不覆盖旧快照。
- 最大持仓周期决定 purge 和 embargo 长度。
- 缺少 point-in-time 证据的旧数据只能用于探索，不能用于正式晋级。

## Factor DSL

允许的数据类别：

- OHLCV。
- Funding rate。
- Open interest。
- Mark/index basis。
- Liquidity 和成交成本代理。
- BTC 和市场状态。
- 动态币种池成员和时间特征。

首版白名单运算符：

```text
lag
delta
rolling_mean
rolling_std
rolling_min
rolling_max
rolling_rank
zscore
correlation
decay_linear
cross_sectional_rank
group_neutralize
safe_add
safe_subtract
safe_multiply
safe_divide
safe_log
safe_sqrt
where
```

验证器检查：

- 语法和类型。
- 字段存在性和 point-in-time 可用性。
- 窗口上限。
- 除零、对数和平方根定义域。
- 复杂度和嵌套深度。
- 禁止未来引用。
- 禁止任意 Python、文件、网络、进程和动态导入。

## 因子候选来源

1. 现有手工因子。
2. Alpha101/Alpha191 加密市场安全子集。
3. 基于市场机制的假设模板。
4. 已验证 AST 的受限参数变异。
5. 已验证因子之间的有限交叉。
6. ML 发现的可解释交互。

每轮搜索必须有固定预算，先去重再计算。候选生成量、通过量、淘汰原因和计算成本全部写入注册库。

## Research Bandit

Bandit 只选择下一批研究预算的分配：

- 因子家族。
- 运算符家族。
- 时间窗口。
- 市场状态。
- 策略方向。

奖励包含：

- 锁定 OOS 成本后表现。
- 稳定性。
- 新颖度。
- 数据覆盖率。
- 计算成本惩罚。
- 与现有策略相关性惩罚。

Bandit 不决定订单、仓位、杠杆或实盘晋级。

## 评价流水线

```text
Syntax and Data Validation
  -> Point-in-time Validation
  -> Semantic Deduplication
  -> IC / RankIC / Quantile Spread
  -> Purged Walk-forward with Embargo
  -> Transaction Cost Stress
  -> Multiple-testing Control
  -> Pair / Exchange / Regime Stability
  -> Strategy Assembly Backtest
  -> Locked Final Test
```

### 数据切分

- 使用 expanding 或 rolling walk-forward。
- 至少 3 个有效测试 fold。
- 标签窗口重叠的训练样本必须 purge。
- Embargo 至少覆盖最大持仓周期。
- 参数选择只使用训练和验证段。
- 最终锁定测试段在候选冻结前不可查看。
- 锁定测试段一旦用于决策，下一轮必须滚动到新测试期。

### 抗过拟合

正式晋级报告必须包含：

- Block bootstrap 置信区间。
- Benjamini-Hochberg FDR，默认 `q <= 0.10`。
- Deflated Sharpe，默认置信度不低于 `0.95`。
- PBO 类指标，默认不高于 `0.25`。
- 参数邻域稳定性。
- 跨币种、月份、交易所和 Regime 分解。

### 成本压力

至少运行：

- 基准手续费和滑点。
- 2 倍成本。
- 3 倍成本。
- 延迟一根 bar 或对应执行延迟。
- 极端跳空和连续亏损情景。

## 机器学习

首版模型：

- Logistic Regression baseline。
- Tree boosting challenger。
- 时间序列 walk-forward。
- 概率校准。

模型只输出候选触发质量或有效性评分，不预测精确价格，不决定杠杆和真实资金规模。

每次训练生成新 modelId。Challenger 必须在相同冻结输入上显著优于 champion，并通过成本、稳定性、校准和复杂度门槛，才可以申请替换 Demo 模型。

Demo 和实盘运行过程中不得在线修改模型。新数据进入下一轮离线训练并生成新版本。

## 自动淘汰

出现任意情况即淘汰或暂停：

- 未来函数或数据泄漏。
- 数据覆盖率或独立样本不足。
- 多重检验修正后不显著。
- 因子方向频繁反转。
- 结果集中于少数币种、月份或单一 Regime。
- 成本翻倍后失去正期望。
- 与现有策略高度相关且无增量价值。
- 锁定测试段失败。
- 数据、代码或模型哈希不一致。

## 生命周期

```text
draft
research_validated
shadow_observation
demo_eligible
demo_active
live_candidate
live_approved
```

终止或异常状态：

```text
paused
rejected
retired
rolled_back
```

状态转换写入 PromotionDecisions 和 AuditEvents，不覆盖旧记录。

## 自动进入 Demo 门槛

共同硬门槛：

- point-in-time、泄漏、FDR、Deflated Sharpe 和 PBO 检查通过。
- 至少 3 个有效 walk-forward 测试 fold。
- 锁定 OOS 成本后 PF 默认不低于 `1.25`。
- 2 倍成本下 PF 默认不低于 `1.05`。
- 最大回撤默认不超过 `20%`。
- 目标保持 `2R`；实际成本后盈亏比达到频率配置要求。
- 单一币种样本占比不超过 `25%`。
- 单一月份占比不超过 `20%`。
- 单一 Regime 占比不超过 `60%`。
- 已形成公共实时行情驱动的 Shadow 闭合观察样本。
- 所有输入版本冻结且校验和一致。

频率最低样本门槛：

| 策略频率 | 锁定 OOS 闭合样本 | Shadow 闭合样本 | Shadow 最短日历覆盖 |
| --- | ---: | ---: | ---: |
| 1h 以下短周期 | 200 | 50 | 14 天 |
| 1h 至 4h | 120 | 30 | 30 天 |
| 1d 及以上低频 | 60 | 20 | 60 天 |

当前 3 条日志和 1 条闭合样本门槛只保留为早期观察条件，不能用于自动 Demo 晋级。

## Demo 风险包

每个 Demo 测试账户初始权益：

```text
1000 USDT
```

默认风险参数：

- 单笔账户风险 `0.25%`。
- 全部未平仓风险最多 `1%`。
- 单笔名义价值最多 `250 USDT`。
- 同时持仓最多 3 个。
- 初始最大杠杆 2 倍。
- 系统硬上限不超过 5 倍。
- 单日亏损达到 2% 时停止当天新开仓。
- Demo 回撤达到 5% 时暂停策略。

策略仲裁器必须处理：

- 同币种多空冲突。
- 同策略家族重复信号。
- 高相关策略风险叠加。
- 数据过期、价差、流动性和执行延迟。
- 全局风险预算和冷却时间。

## Demo 自动执行

```text
Enable DemoRelease
  -> Scan Public Market
  -> Generate Candidate Signals
  -> Strategy Arbitration
  -> Data / Liquidity / Risk Gate
  -> OKX Demo Order
  -> Protective Exit Lifecycle
  -> Audit and Outcome Sample
  -> Drift Evaluation
```

启用 Demo release 后不需要逐单票据。每个候选、拦截、订单、成交、止盈止损和异常都必须具有幂等键并写入审计账本。

Demo 凭据不得进入 SQLite、Git、日志、聊天或报告。凭据只允许通过本机安全运行时注入，并要求最小权限、禁用提现和 IP 白名单。

## 自动暂停和回滚

自动暂停条件：

- ticker、K 线或 instrument metadata 过期。
- 交易所连接、时间同步或订单状态异常。
- 滑点显著超过研究假设。
- 连续亏损或滚动 PF 跌破门槛。
- 特征分布、概率校准或 Regime 表现漂移。
- 本地账本与交易所 Demo 持仓不一致。
- 策略、模型或数据哈希发生未批准变化。

回滚顺序：

1. 停止新开仓。
2. 按原 release 风险规则管理已有 Demo 持仓。
3. 保存异常证据和 DriftEvent。
4. 上一稳定 release 仍满足数据和风险条件时回滚。
5. 否则保持暂停，不自动选择其他策略顶替。

回滚只适用于 Demo。系统不得自动把任何版本回滚或晋级到实盘。

## 实盘候选边界

Demo 通过后只生成 LiveCandidatePackage。该包至少包含：

- 不可变策略和模型 checksum。
- Demo 交易、成本、回撤和异常记录。
- Regime、币种和时间稳定性。
- 拟议风险预算和最大损失。
- 回滚目标和 kill switch。
- 用户人工批准记录。

用户批准一个 live release 后，可以在固定风险包内机械执行，不逐单确认。任何模型、参数、币种范围、杠杆或风险预算变化都产生新 release，并重新人工批准。

## 模块结构

```text
alphapilot/evolution/
  registry/
    database.py
    migrations.py
    repositories.py
  data_lineage/
    snapshot_registry.py
    point_in_time_validator.py
  factor_dsl/
    ast.py
    parser.py
    validator.py
    canonicalizer.py
  factor_mining/
    generator.py
    semantic_deduplicator.py
    correlation_filter.py
    research_bandit.py
  evaluation/
    purged_walk_forward.py
    multiple_testing.py
    cost_stress.py
    robustness.py
  models/
    trainer.py
    calibrator.py
    model_registry.py
    champion_challenger.py
  strategies/
    candidate_builder.py
    family_registry.py
  promotion/
    gate.py
    demo_release.py
    drift_monitor.py
    rollback.py
  adapters/
    legacy_factor_adapter.py
    legacy_report_adapter.py
    control_console_contract.py
  orchestrator.py
```

新模块以单一职责为原则，目标单文件不超过 400 行；超过 500 行必须拆分。旧报告生成器仅在接入 adapter 时做必要修改，不进行无关重构。

## 错误处理

关键路径默认 fail closed：

- 数据校验失败：停止实验。
- 注册事务失败：不创建候选。
- 报告输出失败：注册状态不晋级。
- 模型 checksum 不一致：拒绝加载。
- Demo 下单状态不明：停止新订单并查询恢复。
- 本地账本和交易所状态不一致：触发 kill switch。
- 自动回滚失败：保持暂停。
- 单个候选失败：隔离该候选，不破坏其他实验。

任务必须支持 checkpoint、幂等重试和断点恢复。任何部分成功不得被误写为完整晋级。

## 测试体系

### 单元测试

- DSL lexer/parser/AST/canonicalizer。
- 类型、窗口和定义域检查。
- 数据快照哈希和注册事务。
- Purge、embargo 和 split 边界。
- FDR、Deflated Sharpe、PBO 和成本压力。
- 候选状态机、晋级和回滚。

### 属性和泄漏测试

- 注入未来列必须被拒绝。
- 增加未来数据不能改变过去因子值。
- 相同数据、代码、配置和 seed 必须得到相同 experimentId 和结果。
- 等价表达式必须得到同一规范哈希。

### 集成测试

- 现有 16 个因子完整注册和评价。
- Legacy artifacts 导入、去重和分类。
- Research 无法越级形成 live release。
- Demo release 从 Quant Engine 传到 Control Console。
- 重复信号和重复订单幂等。
- 服务重启后从 append-only 审计恢复。
- API 超时、拒单、部分成交和时钟偏差。
- kill switch、暂停和回滚。

### 现有仓库验证

- Quant Engine：`python -m compileall alphapilot`。
- Quant Engine：`python -m alphapilot.scripts.validate_config`。
- Quant Engine：`scripts/check_safety.ps1`。
- Control Console：Python compileall、smoke 和 API contract 测试。
- Mobile App：`pnpm run typecheck` 和 Expo public config。
- 所有仓库：`git diff --check`。

## 迁移阶段

### Phase 1：Registry Foundation

- 建立 evolution registry 和 migrations。
- 导入 legacy evidence。
- 生成语义去重和资产口径报告。
- 不改变现有策略行为和 Console UI。

### Phase 2：Factor Research Kernel

- 实现 DSL、AST 和 point-in-time validator。
- 接入现有 16 个因子。
- 实现 purged walk-forward、多重检验和成本压力。

### Phase 3：Evolution and ML

- 实现受限变异、相关性过滤和研究 Bandit。
- 实现 Logistic baseline、tree challenger 和概率校准。
- 候选最高进入 Shadow。

### Phase 4：Automatic Demo Promotion

- 生成不可变 Demo release。
- Control Console 接入 release contract 和 OKX Demo。
- 实现自动扫描、仲裁、风险、订单生命周期、暂停和回滚。

### Phase 5：Live Candidate Boundary

- 生成 LiveCandidatePackage。
- 实现用户人工批准和风险预算签署。
- 真实执行适配器另立规格和验收，不在前四阶段顺带实现。

每个阶段独立验收、提交和打 tag。上一阶段失败时不得跨阶段继续。

## 代码整理范围

本项目不做一次性全仓重构。整理顺序：

1. 新 evolution 模块保持小文件和明确接口。
2. 将当前因子、ML、市场状态和 execution reality 通过 adapter 接入。
3. 只拆分本阶段实际触及的超大报告生成器。
4. Control Console 后续把 importer、state_store、http_app 和 `web/app.js` 按领域拆分，但不与 Phase 1 混做。
5. 手机端后续拆分 `ControlConsoleScreen.tsx`，仅消费稳定 contract，不承载研究逻辑。
6. AlphaPilot-Docs 补齐 V13.8.3 之后的版本和本设计索引。

## 验收标准

完成本设计全部阶段前，至少满足：

1. 任意 Demo release 可追溯到数据文件 SHA-256、因子定义、实验、模型、策略和代码 commit。
2. 60 个 legacy artifacts 被明确区分为 evidence、factor asset、strategy candidate 或 duplicate family member。
3. 因子 DSL 不允许任意代码执行。
4. 未来数据注入测试会失败关闭。
5. 同输入实验可复现。
6. 正式候选通过 purged walk-forward、embargo、成本压力和多重检验。
7. Bandit 只能调度研究预算。
8. ML 只能产生新模型版本，不能在线修改运行模型。
9. 达标候选可以自动形成 Demo release。
10. Demo 使用 1000 USDT 测试权益和固定风险包。
11. Demo 不要求逐单票据，但所有订单和拦截可审计。
12. 漂移或异常会自动暂停。
13. Demo release 可以回滚，失败时保持暂停。
14. 新策略、新模型和风险预算不能自动进入实盘。
15. Live release 需要用户人工批准。
16. 不保存 raw API key，不启用 Withdraw API。
17. 现有 Quant、Console 和 App 验证继续通过。

## 最终产品方向

AlphaPilot 的长期目标是自动交易量化平台，但自动化必须分层：

```text
自动数据治理
自动因子研究
自动候选生成
自动抗过拟合评价
自动 Shadow
自动 Demo
人工批准 Live Release
固定风险包内自动机械执行
自动监控、暂停和回滚
```

策略进化来自版本化数据、离线训练、严格 OOS 证据和 Demo 结果，而不是让 AI 在实盘运行时自由改写策略。
