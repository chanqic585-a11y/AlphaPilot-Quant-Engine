# AlphaPilot Factor Evolution Research Kernel 实施计划

## 目标

按照已确认的设计，在现有 Quant Engine 内建立统一策略进化内核，并分阶段接入 Control Console 和手机端。每个阶段必须独立验证、提交、推送和打 tag；前一阶段失败时不得跨阶段继续。

设计规格：

```text
docs/superpowers/specs/2026-07-10-alphapilot-factor-evolution-research-kernel-design.md
```

## 通用执行规则

1. 使用 bundled Python、Git、Node 和 pnpm。
2. 新 Python 测试使用标准库 `unittest`，避免依赖当前未安装的 pytest。
3. 先写失败测试，再实现最小代码让测试通过。
4. 数据库、报告和状态 smoke 必须使用临时目录，不能污染用户真实研究记录。
5. 缺失数据保持缺失，不伪造指标。
6. Phase 1 至 Phase 3 不调用交易所私有接口，不保存凭据，不创建订单。
7. Phase 4 仅允许 OKX Demo，凭据只通过本机运行时注入，不进入 Git、SQLite、报告或日志。
8. Phase 5 只完成 LiveCandidatePackage 和人工批准边界，不顺带实现真实交易适配器。

## 每阶段固定验证

Quant Engine：

```powershell
python -m unittest discover -s tests -p "test_*.py"
python -m compileall alphapilot
python -m alphapilot.scripts.validate_config
powershell -ExecutionPolicy Bypass -File scripts/check_safety.ps1
git diff --check
```

涉及 Control Console 时追加：

```powershell
python -m unittest discover -s tests -p "test_*.py"
python -m compileall alphapilot_control_console
python -m alphapilot_control_console.http_app --smoke
git diff --check
```

涉及手机端时追加：

```powershell
pnpm run typecheck
pnpm exec expo config --type public
git diff --check
```

---

# Phase 1：Registry Foundation

阶段目标：建立不可变本地注册库、稳定哈希、数据快照注册和 legacy evidence 导入，不改变现有策略行为。

建议 tag：

```text
v13.11.0
```

## Task 1.1：建立测试基础和 evolution 包

新增：

```text
tests/__init__.py
tests/evolution/__init__.py
alphapilot/evolution/__init__.py
alphapilot/evolution/registry/__init__.py
alphapilot/evolution/data_lineage/__init__.py
```

测试：

```text
tests/evolution/test_registry_database.py
```

步骤：

1. 写一个导入测试，确认 evolution 包和 registry 模块可加载。
2. 运行 unittest，确认因模块不存在而失败。
3. 新增最小包结构。
4. 运行测试，确认通过。

## Task 1.2：实现稳定 JSON 和 SHA-256 哈希

新增：

```text
alphapilot/evolution/registry/hashing.py
tests/evolution/test_hashing.py
```

接口：

```python
canonical_json(value) -> str
stable_hash(value, prefix=None) -> str
sha256_file(path) -> str
```

测试覆盖：

- 字典键顺序不影响哈希。
- list 顺序会影响哈希。
- NaN/Infinity 被拒绝。
- 同一文件哈希稳定。
- 文件内容变化导致哈希变化。
- 可选前缀形成可读 ID。

## Task 1.3：实现 SQLite schema 和 migration runner

新增：

```text
alphapilot/evolution/registry/database.py
alphapilot/evolution/registry/migrations.py
tests/evolution/test_registry_migrations.py
```

首版表：

```text
RegistryMigrations
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
LegacyEvidence
```

要求：

- `CREATE TABLE IF NOT EXISTS`。
- migration 可重复执行。
- 事务失败整体回滚。
- 默认路径 `data/evolution_registry.sqlite`。
- 测试只使用 `TemporaryDirectory`。
- 不修改现有 SQLite 或报告数据。

## Task 1.4：实现 typed registry records 和 repositories

新增：

```text
alphapilot/evolution/registry/types.py
alphapilot/evolution/registry/repositories.py
tests/evolution/test_registry_repositories.py
```

首版 CRUD：

```python
create_data_snapshot
get_data_snapshot
create_factor_definition
get_factor_definition
create_legacy_evidence
list_legacy_evidence
create_strategy_family
create_strategy_candidate
append_audit_event
```

要求：

- 创建函数幂等。
- 相同 stable ID 和相同内容返回已有记录。
- 相同 stable ID 但内容冲突时失败关闭。
- AuditEvents append-only。
- 所有 JSON 字段 canonical serialization。

## Task 1.5：实现数据快照清单

新增：

```text
alphapilot/evolution/data_lineage/snapshot_registry.py
tests/evolution/test_snapshot_registry.py
```

接口：

```python
build_data_snapshot_manifest(...)
register_data_snapshot(...)
verify_data_snapshot(...)
```

清单至少包含：

```text
source
exchange
marketType
timeframe
startTime
endTime
pointInTimeCutoff
universeMembers
files[path, size, sha256]
metadata
```

验证：

- 文件缺失、大小变化或哈希变化时失败。
- 成员顺序规范化。
- 不读取文件内容中的未来数据；本任务只负责文件级血缘。

## Task 1.6：实现 legacy evidence 分类与语义去重

新增：

```text
alphapilot/evolution/adapters/__init__.py
alphapilot/evolution/adapters/legacy_report_adapter.py
alphapilot/evolution/registry/legacy_importer.py
tests/evolution/test_legacy_importer.py
```

分类：

```text
report_summary
factor_asset
strategy_candidate_evidence
duplicate_family_member
incomplete_evidence
```

首版去重：

- 来源文件 SHA-256。
- strategyId / candidateId 规范化。
- 交易规则、方向、周期、退出和风险字段指纹。
- 同源 report summary 与派生报告归入同一 family。

禁止：

- 因历史高 PF 自动创建 DemoRelease。
- 缺少交易规则的因子报告变成 StrategyCandidate。

## Task 1.7：生成 Phase 1 注册与去重报告

新增：

```text
alphapilot/reports/generate_evolution_registry_foundation_report.py
scripts/build_evolution_registry_foundation.ps1
tests/evolution/test_registry_foundation_report.py
docs/V13.11.0-evolution-registry-foundation.md
```

输出：

```text
reports/evolution_registry_foundation_report.json
reports/evolution_registry_foundation_summary.md
```

报告至少包含：

- 扫描报告数量。
- 导入 evidence 数量。
- 各分类数量。
- 独立策略家族数量。
- 可形成候选与不可形成候选的原因。
- 重复 family 成员。
- 错误和跳过文件。
- 明确 safety boundary。

## Task 1.8：Phase 1 文档、验证和发布

修改：

```text
README.md
```

验证全部固定命令。确认只新增注册层和报告，没有策略行为变化。

提交：

```text
Build V13.11.0 evolution registry foundation
```

Tag：

```text
v13.11.0
```

---

# Phase 2：Factor Research Kernel

阶段目标：实现白名单 DSL、AST、point-in-time 检查、purged walk-forward、多重检验和成本压力。

建议 tag：

```text
v13.12.0
```

## Task 2.1：Factor DSL lexer/parser/AST

新增：

```text
alphapilot/evolution/factor_dsl/ast.py
alphapilot/evolution/factor_dsl/lexer.py
alphapilot/evolution/factor_dsl/parser.py
tests/evolution/test_factor_dsl_parser.py
```

先测试：

- 合法字段、数字、函数和嵌套表达式。
- 非法 token、未知函数和括号错误。
- 禁止属性访问、import、字符串代码和任意函数调用。

## Task 2.2：Factor DSL 类型和安全验证

新增：

```text
alphapilot/evolution/factor_dsl/operators.py
alphapilot/evolution/factor_dsl/validator.py
tests/evolution/test_factor_dsl_validator.py
```

覆盖：

- 字段类型。
- 窗口范围。
- 嵌套深度。
- 除零、log、sqrt 定义域元数据。
- lag 必须非负。
- 禁止未来偏移。

## Task 2.3：AST 规范化和表达式 ID

新增：

```text
alphapilot/evolution/factor_dsl/canonicalizer.py
tests/evolution/test_factor_canonicalizer.py
```

覆盖等价表达式、交换律、参数格式和字段别名。

## Task 2.4：Point-in-time validator

新增：

```text
alphapilot/evolution/data_lineage/point_in_time_validator.py
tests/evolution/test_point_in_time_validator.py
```

要求：

- 字段带 `availableAt` 或明确延迟规则。
- 动态 universe 使用历史 snapshot。
- Forward label 永远不属于 factor input。
- 注入未来列测试必须失败。

## Task 2.5：Purged walk-forward 和 embargo

新增：

```text
alphapilot/evolution/evaluation/purged_walk_forward.py
tests/evolution/test_purged_walk_forward.py
```

要求：

- expanding 和 rolling 模式。
- purge 重叠 label window。
- embargo 覆盖最大持仓周期。
- 输出可复现 fold manifest。

## Task 2.6：多重检验和稳健性

新增：

```text
alphapilot/evolution/evaluation/multiple_testing.py
alphapilot/evolution/evaluation/robustness.py
tests/evolution/test_multiple_testing.py
tests/evolution/test_robustness.py
```

实现：

- Benjamini-Hochberg FDR。
- Deflated Sharpe 输入与结果容器。
- PBO 类分区评价。
- Block bootstrap 置信区间。
- 参数邻域、币种、月份、交易所和 Regime 稳定性。

## Task 2.7：成本压力

新增：

```text
alphapilot/evolution/evaluation/cost_stress.py
tests/evolution/test_cost_stress.py
```

场景：基准、2 倍成本、3 倍成本、延迟和跳空。

## Task 2.8：接入现有 16 个因子并生成报告

新增：

```text
alphapilot/evolution/adapters/legacy_factor_adapter.py
alphapilot/reports/generate_factor_research_kernel_baseline.py
scripts/run_factor_research_kernel_baseline.ps1
tests/evolution/test_legacy_factor_adapter.py
docs/V13.12.0-factor-research-kernel.md
```

要求：现有因子值不被静默修改；新报告展示新门槛下的差异。

发布 tag：`v13.12.0`。

---

# Phase 3：Evolution and ML

阶段目标：自动生成受限候选、去重、分配研究预算并建立可解释 champion/challenger 模型。

建议 tag：`v13.13.0`。

## Task 3.1：受限因子生成器

新增：

```text
alphapilot/evolution/factor_mining/generator.py
tests/evolution/test_factor_generator.py
```

只允许从已验证 AST 进行有限参数变异、字段替换和安全交叉。

## Task 3.2：语义与相关性过滤

新增：

```text
alphapilot/evolution/factor_mining/semantic_deduplicator.py
alphapilot/evolution/factor_mining/correlation_filter.py
tests/evolution/test_semantic_deduplicator.py
tests/evolution/test_correlation_filter.py
```

## Task 3.3：Research Bandit

新增：

```text
alphapilot/evolution/factor_mining/research_bandit.py
tests/evolution/test_research_bandit.py
```

Bandit 只能返回 research allocation，不包含 symbol order、position size 或 execution action。

## Task 3.4：Model trainer 和概率校准

新增：

```text
alphapilot/evolution/models/trainer.py
alphapilot/evolution/models/calibrator.py
tests/evolution/test_model_trainer.py
tests/evolution/test_model_calibrator.py
```

首版使用 Logistic Regression baseline 和 tree boosting challenger。训练数据只来自注册的 FactorRun 和 fold manifest。

## Task 3.5：Model registry 和 champion/challenger

新增：

```text
alphapilot/evolution/models/model_registry.py
alphapilot/evolution/models/champion_challenger.py
tests/evolution/test_model_registry.py
tests/evolution/test_champion_challenger.py
```

新模型只能申请 Shadow，不自动替换 Demo champion。

## Task 3.6：Strategy candidate builder 和 family registry

新增：

```text
alphapilot/evolution/strategies/candidate_builder.py
alphapilot/evolution/strategies/family_registry.py
tests/evolution/test_candidate_builder.py
```

候选必须具备完整入场、方向、退出、风险和适用市场定义。

## Task 3.7：Evolution orchestrator 和报告

新增：

```text
alphapilot/evolution/orchestrator.py
alphapilot/reports/generate_evolution_cycle_report.py
scripts/run_evolution_cycle.ps1
tests/evolution/test_evolution_orchestrator.py
docs/V13.13.0-evolution-and-ml.md
```

首版运行仅到 Shadow，禁止生成 Demo 或 Live order。

发布 tag：`v13.13.0`。

---

# Phase 4：Automatic Demo Promotion

阶段目标：通过硬门槛的候选自动形成 Demo release，并由 Control Console 在 OKX Demo 中机械执行。

建议 tag：

```text
Quant Engine: v13.14.0
Control Console: v13.14.0-console
```

## Task 4.1：Promotion gate 和不可变 Demo release

Quant Engine 新增：

```text
alphapilot/evolution/promotion/gate.py
alphapilot/evolution/promotion/demo_release.py
tests/evolution/test_promotion_gate.py
tests/evolution/test_demo_release.py
```

覆盖设计中所有 OOS、成本、集中度、Shadow 样本和 checksum 门槛。

## Task 4.2：Drift monitor 和 rollback decision

Quant Engine 新增：

```text
alphapilot/evolution/promotion/drift_monitor.py
alphapilot/evolution/promotion/rollback.py
tests/evolution/test_drift_monitor.py
tests/evolution/test_rollback.py
```

## Task 4.3：Control Console release contract

Quant Engine 新增：

```text
alphapilot/evolution/adapters/control_console_contract.py
tests/evolution/test_control_console_contract.py
```

Contract 不包含 raw credential，只包含 release、策略规则、风险包和 checksum。

## Task 4.4：官方 OKX Demo API 核对

实现前只使用 OKX 官方文档核对：

- Demo Trading 请求头和环境标识。
- API 权限和 IP 白名单。
- 下单、查询、撤单和持仓接口。
- 客户端订单 ID 和幂等行为。
- 止盈止损和部分成交语义。
- 频率限制、时间同步和错误码。

核对结果写入：

```text
AlphaPilot-Control-Console/docs/V13.14.0-okx-demo-api-contract.md
```

## Task 4.5：凭据隔离和 Demo connector

Control Console 新增：

```text
alphapilot_control_console/exchange_connectors/okx_demo_client.py
alphapilot_control_console/credential_runtime.py
tests/test_okx_demo_client.py
tests/test_credential_runtime.py
```

要求：

- 凭据只从当前进程安全输入/环境读取。
- 日志、异常和 HTTP 响应全部脱敏。
- Withdraw 权限和 endpoint 硬禁用。
- 测试使用 fake transport，不联系真实交易所。

## Task 4.6：Demo strategy arbitrator 和 risk envelope

Control Console 新增：

```text
alphapilot_control_console/demo_arbitrator.py
alphapilot_control_console/demo_risk_envelope.py
tests/test_demo_arbitrator.py
tests/test_demo_risk_envelope.py
```

默认权益和风险使用已确认的 1000 USDT 包。

## Task 4.7：幂等 Demo 生命周期

Control Console 新增：

```text
alphapilot_control_console/demo_execution_engine.py
alphapilot_control_console/demo_execution_store.py
tests/test_demo_execution_engine.py
tests/test_demo_execution_store.py
```

覆盖扫描、仲裁、下单、查询、部分成交、保护退出、重启恢复、暂停和 kill switch。

## Task 4.8：Console UI 和 API

修改：

```text
alphapilot_control_console/http_app.py
web/app.js
web/styles.css
README.md
```

UI 明确区分 Research、Shadow、OKX Demo 和 Live Locked。

## Task 4.9：Demo sandbox 演练与发布

先使用 fake connector 和记录回放，通过后才允许用户本机注入 OKX Demo 凭据。禁止把 smoke 产生的订单写到真实账户。

发布对应 tags。

---

# Phase 5：Live Candidate Boundary

阶段目标：形成实盘候选包和人工批准状态机，不实现真实下单适配器。

建议 tag：

```text
Quant Engine: v13.15.0
Control Console: v13.15.0-console
Mobile App: v13.15.0-mobile
```

## Task 5.1：LiveCandidatePackage

新增：

```text
alphapilot/evolution/promotion/live_candidate.py
tests/evolution/test_live_candidate.py
```

## Task 5.2：人工批准和风险预算签署

Control Console 新增本地批准状态机。批准记录绑定 release checksum、风险预算、用户确认时间和撤销状态。

## Task 5.3：手机端精简批准视图

手机端只展示证据、风险预算和批准/撤销操作；不得保存交易所凭据或直接调用交易所。

## Task 5.4：最终安全验证

证明：

- 新候选不能自动进入 Live。
- AI、Bandit 和 ML 不能写入 live approval。
- release checksum 变化会使批准失效。
- Withdraw 始终关闭。
- 真实执行适配器不存在或保持锁定。

发布对应 tags。

## 完成定义

只有以下条件全部满足，整个计划才算完成：

1. Registry、DSL、评价、ML、Demo promotion、drift 和 rollback 均有自动化测试。
2. 现有研究资产被导入且口径去重。
3. 任何 Demo release 可追溯到数据、因子、实验、模型、策略和 commit。
4. 自动晋级最高到 OKX Demo。
5. 实盘 release 必须人工批准。
6. 所有仓库工作区干净，阶段 commit/tag/push 可核对。
7. README、设计、实施和运行文档一致。
