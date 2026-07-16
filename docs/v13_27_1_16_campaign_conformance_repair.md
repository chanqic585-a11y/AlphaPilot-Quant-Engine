# AlphaPilot V13.27.1.16 实现一致性修复与纠错预筛

## 结论

V13.27.1.16 只修复实现一致性，不修改 V13.27.1.15 的候选、参数、Gate、代表币池、成本或退出政策。纠错后一级预筛得到 1 条幸存者，但本版本不进入 Walk-forward、Locked OOS、Release、Demo ARM 或订单阶段。

权威 Campaign：

```text
advisory_r_v16_correction_8ec939e8f7ce17a3d259c72c134d02
```

权威预注册：

```text
research/preregistrations/advisory_r_v16_correction_8ec939e8f7ce17a3d259c72c134d02.json
```

权威报告目录：

```text
reports/advisory_r_campaign/advisory_r_v16_correction_8ec939e8f7ce17a3d259c72c134d02/
```

## 执行补充约束

1. V15 的预注册、Snapshot 和报告在运行前后必须保持哈希不变。
2. 实现修复与参数优化严格分离；策略、参数、Gate、币池和成本差异必须为 0。
3. `candidate_events.parquet` 必须与正式 replay 事件做独立 parity。
4. 简单基准必须由独立路径计算，不能复用候选策略 PnL。
5. Funding 数据不可用时保持 `null`，不能补零或伪造。
6. 2R 只保留为 Advisory-R，不作为硬门槛；`minimumTargetR=null`。
7. 一级幸存者只能路由到下一版本正式阶段，本版本不得读取 Locked OOS 或生成 Release。
8. 失败归档、仅诊断候选和实现阻塞必须分开统计。

## 主要修复

- 统一使用正式 ExitPolicy Engine，移除 Campaign 内第二套退出计算语义。
- 修正 trailing、partial weighted R、gap stop、stop-first 和 next-bar-open。
- 完成 S01-S10 的冻结字段执行，包括 lead-lag、confirmation、双腿成本、相关性恢复、prior bars、组合分位与 rebalance。
- 为 pair/portfolio candidate 增加独立 replay。
- 增加独立 simple benchmark、event schema、exit-leg parity 和 implementation parity。
- 修正 `failure_attribution.nextAction`，使其根据 survivor 数量生成。

## 最终结果

| 指标 | 结果 |
| --- | ---: |
| 候选 | 10 |
| 家族 | 8 |
| 事件 | 38,738 |
| 一级幸存 | 1 |
| 归档 | 8 |
| 仅诊断 | 1 |
| 实现阻塞 | 0 |
| 实现一致性通过 | 10/10 |
| 事件 parity 缺失/额外/变化 | 0 / 0 / 0 |
| Exit legs | 43,854 |
| Exit-leg parity 失败 | 0 |
| V15 哈希错配 | 0 |
| V15 原文件修改 | 0 |

一级幸存者：

```text
s01_bear_idiosyncratic_selloff_recovery_4h
```

核心指标：442 个事件，PF 1.4475，平均净 R 0.1189，最大回撤 25.154%。它只能在下一版本进入正式统计阶段。

仅诊断候选 `s10_orthogonal_weak_signal_matrix_4h` 的 PF 为 1.0418、平均净 R 为 0.0240，但最大回撤为 253.094%，且它本来就是 diagnostic-only，不能晋级。

## 路由与安全边界

```text
route=formal_stage_deferred_to_future_version
lockedOosAccessCount=0
formalEvidenceCount=0
releaseCount=0
demoArm=false
orderCount=0
```

本版本没有 Trade API、Withdraw API、API Key、真实账户、真实持仓或真实订单副作用。

## 审计轨迹

- `advisory_r_v16_correction_67188df690f3c9d41e2f6946b0992e`：在报告生成前发现 S06 独立基准缺失，未形成权威 Campaign。
- `advisory_r_v16_correction_6ef0be804a7edb8ea28748ec469e86`：计算结果正确，但发现 `failure_attribution.nextAction` 固定文案错误，因此不作为最终交付。

最终权威 Campaign 绑定代码 commit `b32cabc`，预注册在结果读取前完成并推送。

## 已知问题

- Pandas 在 regime map 的 `concat` 处发出未来默认排序警告；当前结果确定，不在冻结后修改实现。下一版本可在新预注册前显式指定 `sort=False`。
- 全量测试中存在一个与本版本无关的既有失败：12 个 `reports/derivatives_data/*.json.sha256` sidecar 与其已提交 JSON 不一致。本版本未重写历史 sidecar。
- 默认 pytest 收集会遇到旧测试目录中的同名模块，验证时使用 `--import-mode=importlib`。

## 下一步

下一版本只对 S01 执行预注册的正式统计阶段：Purged Walk-forward、资本竞争、Newey-West、BH、DSR、PBO、White Reality Check 和 SPA。不得把本次结果直接升级为 Release 或 Demo 策略。
