# AlphaPilot V46
# OKX Demo Engineering Smoke 明确批准指令
## 直接交给 Codex

我明确批准执行 **一次隔离的 OKX Demo Engineering Smoke**。

本批准只针对工程烟测，不构成：

```text
策略 Release 批准
Provisional Research Demo ARM 批准
Formal Pass
Live 批准
Withdraw 批准
```

## 一、批准绑定身份

```text
Release ID:
provisional_research_demo_v46_a3669d95101ba65f68fa89b1

Release Hash:
provisional_demo_release_c1e28ecf59fb7fcc2b4876eec5e6fd04c50002bef28c69c03bedf164af7cd225

Risk Overlay Hash:
risk_overlay_7221d23144dcd0a357136f6e9587a505d81c86439e223457d2d7393d287b8218

Execution Intersection Hash:
demo_execution_intersection_1bcd5f70a24d1d2527a29965d95d1c47473f0e85a442dfda744354d95e0bd514

Engineering Smoke Request Evidence Hash:
engineering_smoke_evidence_3347652ed144d6b9be81f16b860c1a2fc190c0ab109a24d820c4f13969779eca

Environment:
OKX Demo only
```

本批准只在上述身份全部保持一致时有效。

## 二、烟测合约

在第一笔订单之前，必须生成不可变的：

```text
engineering_smoke_contract.json
engineeringSmokeContractHash
engineering_smoke_approval_overlay.json
```

该合约必须严格满足：

```text
requestType = engineering_smoke_only
strategyQualification = false
formalPass = false
forwardEvidenceEligible = false
livePromotionEligible = false

instrumentId = BTC-USDT-SWAP
size = 当前认证 Demo instrument response 的精确 minSz
size 必须按 lotSz 舍入
price 必须按 tickSz 舍入

maximumConcurrentPositions = 1
maximumOpenPositions = 1
noAdding = true
noAveraging = true
noMartingale = true
```

不得：

```text
自动切换到其他合约
增加订单数量
修改账户模式
修改持仓模式
修改杠杆设置
使用 Live 凭据
启用 Withdraw
```

如果 BTC-USDT-SWAP 在订单前的最新私有读取中不再：

```text
present
state=live
tradable=true
USDT SWAP
```

则必须 fail closed，并请求新的烟测批准；不得自动换成 DOGE、ETH、SOL 或 XRP。

## 三、私有请求边界

所有私有请求必须：

```text
保留 x-simulated-trading: 1
使用现有 OkxDemoClient
使用当前已验证的 Demo account
凭据只在进程或 Windows Credential Manager 中使用
不写入文件、SQLite、日志、报告或 UI
```

订单前重新确认：

```text
server time
account config
account instruments
balance
positions
pending orders
recent fills
```

如果存在未知挂单、未知持仓、账户模式不兼容或交集 Hash 变化：

```text
停止，不下单。
```

## 四、允许执行的烟测路径

### Path A：挂单—查询—撤单

```text
BTC-USDT-SWAP
精确 minSz
post-only limit
确定性 clOrdId
```

执行：

```text
submit
→ REST query
→ 订单事件/状态确认
→ cancel request
→ REST 或私有 WS 确认最终状态为 canceled
```

撤单请求被接受不等于已完成撤单；必须确认最终状态。

如果订单意外部分或全部成交：

```text
禁止重复开仓；
按实际 filled size 进入 Path B 的关闭流程。
```

### Path B：最小成交—持仓—归零

只允许一笔最小规模开仓：

```text
size = minSz
maximum position count = 1
```

执行：

```text
submit
→ 确认 fill / partial fill
→ 读取 positions
→ 使用实际 filled size 执行 reduce-only 或现有安全 close 路径
→ 确认 position = 0
```

不得把：

```text
order request success
cancel request success
close request success
```

当作最终状态。

## 五、恢复、对账和 Kill Switch

完成：

```text
订单状态恢复
重启恢复
REST order/fill/position reconciliation
私有 WebSocket（现有实现支持时）
Kill Switch
```

硬要求：

```text
duplicateOrderCount = 0
orphanOrderCount = 0
orphanPositionCount = 0
unknownStateCount = 0
finalPositionCount = 0
```

任何不一致：

```text
blocked_execution_integrity
```

不得继续执行策略 Release。

## 六、证据隔离

所有订单和成交只能写入：

```text
engineering-smoke ledger
```

必须保持：

```text
strategyOrderCount = 0
strategyClosedTradeCount = 0
forwardEvidenceDelta = 0
formalEvidenceDelta = 0
```

工程烟测不能增加：

```text
PF
胜率
净 R
Demo 前向样本
Release 资格
Live 资格
```

## 七、完成后的机械路线

只有以下全部通过：

```text
privateReadVerified = true
authenticatedUniverseNonEmpty = true
cancelPathCompleted = true
fillClosePathCompleted = true
positionReturnedToZero = true
restartRecoveryPassed = true
reconciliationPassed = true
duplicate/orphan/unknown = 0
strategyEvidenceDelta = 0
credentialsPersisted = false
```

才允许写：

```text
engineeringSmokeReady = true
```

随后：

```text
重新生成 provisional_demo_pre_arm_readiness
重新生成策略 Demo Approval Request
再次停在 blocked_waiting_exact_release_approval
```

不得自动：

```text
批准 Provisional Release
ARM 策略 Demo
创建策略订单
启用 Live
启用 Withdraw
```

## 八、必须输出

```text
engineering_smoke_contract.json
engineering_smoke_contract_hash_audit.json
engineering_smoke_approval_overlay.json

engineering_smoke_private_preflight.json
engineering_smoke_cancel_audit.json
engineering_smoke_fill_close_audit.json

engineering_smoke_order_ledger.jsonl
engineering_smoke_fill_ledger.jsonl
engineering_smoke_position_ledger.jsonl

engineering_smoke_restart_recovery_audit.json
engineering_smoke_rest_reconciliation_audit.json
engineering_smoke_private_websocket_audit.json
engineering_smoke_kill_switch_audit.json
engineering_smoke_strategy_evidence_isolation_audit.json

updated_provisional_demo_pre_arm_readiness.json
updated_provisional_demo_pre_arm_readiness.md

engineering_smoke_final_self_check.json
engineering_smoke_artifact_manifest.json
```

## 九、完成回复

```text
V46 OKX Demo Engineering Smoke 已完成

Approval Identity:
- request evidence hash:
- Release Hash:
- Risk Overlay Hash:
- Smoke Contract Hash:

Instrument:
- instId:
- tickSz:
- lotSz:
- minSz:
- account mode:
- position mode:

Path A:
- submitted:
- queried:
- cancel requested:
- final canceled:

Path B:
- submitted:
- filled:
- position observed:
- close submitted:
- final position zero:

Recovery:
- restart:
- REST reconciliation:
- private WS:
- Kill Switch:

Integrity:
- duplicate orders:
- orphan orders:
- orphan positions:
- unknown states:
- strategy evidence delta:
- credentials persisted:

Updated Readiness:
- engineeringSmokeReady:
- approvalReady:
- approved:
- Demo ARM:
- strategy orders:
- Live:
- Withdraw:
- route:

[Smoke Evidence](...)
[Updated Pre-ARM Readiness](...)
[Strategy Demo Approval Request](...)
```

本消息明确批准的只是本文件约束下的 OKX Demo 工程烟测。
