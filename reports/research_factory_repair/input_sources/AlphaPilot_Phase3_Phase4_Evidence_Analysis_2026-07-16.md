# AlphaPilot 第三、第四阶段证据分析报告

## 一、执行结论

本轮研究流程在“失败关闭、预注册、有限预算、成本压力、五折验证、零 Release 安全路径”方面是成功的，但在“数据层完整性、正式 Holdout 判定、真实 Freqtrade 全链路、因子研究覆盖度”方面仍有明显缺口。

最终结论不是“策略研究已经穷尽”，而是：

> 当前冻结数据与当前 3 个市场机制、6 个方向变体、8 个 Alpha191 种子因子的首轮有限 Campaign，没有发现可正式晋级的策略。

本轮只产生了两个值得作为新假设线索的方向：

1. 4h 特异性下跌冲击后的做多回归；
2. 4h 极端负 Funding 后的做多反转。

它们都不能恢复原候选，也不能直接进入 Demo。下一轮必须使用更完整的同交易所 Funding、OI、Basis、清算、PIT 币池和新的锁定数据，形成实质不同的新假设。

---

## 二、证据完整性与仓库状态

### 已完成的可信部分

- Campaign、数据快照、因子清单和预注册均具有 Hash。
- 结果运行声明为离线。
- Holdout 在最终评估前访问次数为 0。
- 五个 Walk-forward Fold 已生成。
- 试验预算未超限。
- 没有强制生成赢家。
- 第四阶段在零正式通过情况下生成 0 Release、0 批准、0 订单并保持 Runtime 未 ARM。
- 工程烟测与策略成绩保持隔离。

### 尚未真正收口的部分

- Quant 与 Console 阶段工作仍位于远端 Feature Branch，并未显示已合并到 main。
- 两个阶段分支头均无 Tag。
- Docs 仍停留在此前的 `v13.27.1.9-docs`。
- Quant main 与 Console main 仍有任务开始前的独立状态。
- 证据包没有包含 pytest、compileall、安全扫描和 git diff 检查日志。
- 证据包没有包含外部参考审计、Alpha191 公式注册、公式冲突、数值交叉验证等阶段 3A 文件。
- 没有原始事件级结果、逐笔完整回测文件或 Freqtrade ZIP，因此无法从证据包独立重算全部指标。

在下一轮 Campaign 前，应先合并或冻结 Feature Branch，并为 Quant、Console、Docs 建立明确的研究里程碑 Tag。

---

## 三、数据层分析

### 当前冻结数据

- 数据集：32
- 币种：8
  - BTC
  - ETH
  - XRP
  - LTC
  - BCH
  - ETC
  - ADA
  - LINK
- 周期：1h、4h、1d
- OHLCV：大致覆盖 2020 年至 2026 年 5 月
- Funding：Binance 公共 Funding，覆盖约 2020 年至 2026 年 7 月

### 数据质量限制

| 数据维度 | 当前状态 | 影响 |
|---|---|---|
| OHLCV | 交易所来源未独立验证，标记为代理 | 不能视为完全正式的同交易所数据 |
| Funding | Binance 真实公共历史 | 可研究 Funding，但与 OHLCV 可能跨交易所 |
| Open Interest | 不可用 | 无法验证真正的仓位拥挤与新资金趋势 |
| Basis | 不可用 | 无法研究永续—现货偏离和 Carry |
| 真实清算 | 不可用 | 只能使用范围/成交量代理 |
| PIT 币池 | diagnostic proxy | 横截面结论只能诊断，不能正式晋级 |
| Spread / Depth | OHLCV 代理 | 短周期执行成本可信度有限 |
| Market Breadth | 固定冻结币池派生 | 存在幸存者与历史可交易状态风险 |

因此，这一轮并没有真正测试完整的：

- Funding + OI 拥挤；
- Price + OI 趋势；
- Basis 偏离；
- 真实清算耗竭；
- 正式 PIT 横截面策略。

实际只测试了：

1. 纯 OHLCV 波动压缩突破；
2. 纯 OHLCV/BTC 基准的特异性冲击回归；
3. Funding + 价格代理的反转。

### 数据就绪门过于宽松

阶段 3B 出口门判定为通过，但正式使用的 OHLCV 仍是来源未验证代理，PIT 仍是诊断代理。建议下一版增加两级数据资格：

- `diagnostic_ready`：允许事件研究；
- `formal_ready`：才允许正式 Gate 和 Release。

正式资格至少要求：

- 同交易所、来源可验证；
- 机制必需数据真实可用；
- 横截面策略有历史 PIT；
- Funding、价格、OI、Basis 时间对齐；
- 数据覆盖至新的锁定边界。

---

## 四、Alpha191 因子实验室分析

### 实际范围

- 种子因子：8
- 正式 Trial：32
- 周期：仅 1d
- Forward Horizon：1 日与 5 日
- 方向：原方向与反方向
- 合格因子：0

本轮只测试了少量基础价量因子，不能解释为“Alpha191 全部无效”。

### 两个最值得注意的因子线索

#### Alpha088：20 日收益/动量

5 日 Horizon 原方向：

- 基础成本后 Spread：约 +1.10%
- 1.5 倍成本后 Spread：约 +1.09%
- 正 Fold：3/5
- 单币贡献：约 33.7%
- FDR：约 0.439，未通过

判断：

- 经济幅度看起来较强；
- 统计支持不足；
- 只有 8 个币，横截面太小；
- 值得在 30–50 个历史 PIT 高流动性币种上重新研究；
- 不能直接生成策略。

#### Alpha191 反方向、1 日 Horizon

- RankIC：约 +0.0318
- FDR：约 0.00493
- 正 Fold：4/5
- 基础成本后 Spread：约 +0.0149%
- 1.5 倍成本后 Spread：约 -0.0207%
- 单币正收益贡献：约 45.7%

判断：

- 有统计关系；
- 实际经济优势过薄；
- 成本压力后消失；
- 币种集中超限；
- 只适合以后作为低权重确认或否决特征。

### 因子报告的结构问题

1. `fdrDiscoveryCount=2` 实际来自同一个 Alpha191 因子、同一 Horizon 的正反两个方向，不是两个独立发现。
2. 方向正反应当作为一个双侧假设或在开发集决定符号，不应作为两份独立发现计票。
3. 三个币种池分割中 `split_2` 为空，不能视为完整的三组币种交叉验证。
4. 因子 Shortlist 为 0，因此阶段 3C 的 6 个候选没有使用任何因子确认、排序或否决。
5. 当前结果只说明 8 个因子配置未获得“研究特征资格”，不说明 Alpha191 整体无效。

---

## 五、阶段 3C 候选结果

| 候选 | 开发 PF / 平均 R | Walk-forward PF / 平均 R | 正 Fold | Holdout PF / 平均 R | 1.5x PF | 判断 |
|---|---:|---:|---:|---:|---:|---|
| 1h 波动压缩突破做多 | 0.820 / -0.142 | 0.702 / -0.251 | 0/5 | 未访问 | 0.608 | 明确否决 |
| 1h 波动压缩突破做空 | 0.978 / -0.016 | 0.898 / -0.079 | 2/5 | 未访问 | 0.782 | 否决 |
| 4h 特异性冲击回归做多 | 1.303 / +0.161 | 1.152 / +0.081 | 3/5 | 0.945 / -0.031 | 1.032 | 最接近，但正式失败 |
| 4h 特异性冲击回归做空 | 0.708 / -0.193 | 0.719 / -0.185 | 1/5 | 未访问 | 0.682 | 明确否决 |
| 4h Funding 拥挤反转做多 | 0.973 / -0.017 | 1.149 / +0.085 | 2/5 | 未访问 | 1.076 | 时间状态分化，仅作线索 |
| 4h Funding 拥挤反转做空 | 0.837 / -0.108 | 0.826 / -0.117 | 2/5 | 未访问 | 0.821 | 明确否决 |

### 明确否决路线

- 对称的波动压缩突破；
- 特异性冲击后的做空回归；
- 正 Funding 拥挤后的对称做空反转；
- 用相同规则同时做多和做空。

### 最接近通过的候选

`idiosyncratic_shock_reversion_4h_long_v1`

它的数值层表现：

- 开发 PF：1.303
- Walk-forward PF：1.152
- Walk-forward 平均净 R：+0.081
- 3/5 Fold 为正
- Holdout PF：0.945
- Holdout 平均净 R：-0.031
- Holdout 交易：51
- 1.5 倍成本合并 PF：1.032

它说明：

- 特异性下跌冲击后的做多回归可能存在局部优势；
- 优势没有在最终 Holdout 延续；
- 不能恢复当前版本；
- 下一版必须加入真实 OI、清算、市场宽度、上市状态和流动性信息，形成实质不同的新机制。

### Funding 做多线索

`funding_crowding_reversal_4h_long_v1`

- 开发区间略为负；
- Walk-forward PF 约 1.149；
- 1.5 倍成本 PF 约 1.076；
- 2 倍成本 PF 约 1.009；
- 仅 2/5 Fold 为正；
- 没有进入 Holdout。

它只能说明：

- 极端负 Funding 后的做多反转可能在某些时期有效；
- 当前“拥挤”定义缺 OI 和 Basis；
- Binance Funding 与未验证来源 OHLCV 存在跨交易所偏差；
- 不得根据 OOS 好看而复活当前参数。

---

## 六、关键方法学问题

### 1. 最终 Holdout 没有独立进入正式 Gate

当前正式 Gate 使用 `oosMetrics`，而最接近候选的：

```text
oosMetrics = Walk-forward 147 笔 + Holdout 51 笔
```

这会把负 Holdout 被正 Walk-forward 稀释：

- Walk-forward PF：1.152
- Holdout PF：0.945
- 合并 OOS PF：1.097

正式 Gate 只要求 Holdout 在最终前未访问，却没有单独要求：

- Holdout PF > 1；
- Holdout 平均净 R > 0；
- Holdout 总净 R > 0；
- Holdout 最低样本。

下一版必须改成：

```text
基础 Gate = 只看 Walk-forward
正式 Gate = 单独看 Holdout
禁止将两者合并后判定正式通过
```

### 2. “完整回测”并非真实 Freqtrade

唯一预筛幸存者显示：

```text
fullBacktestExecuted = true
fullBacktestEngine = causal_event_replay_reference
freqtradeTranslationPassed = false
```

因此：

- 事件回放已执行；
- Freqtrade 翻译与逐笔一致性未执行；
- `fullBacktestCount=1` 容易误导。

应拆分为：

```text
fullEventReplayExecuted
freqtradeBacktestExecuted
translationParityPassed
```

在下一轮正式候选通过前，必须证明：

```text
事件 ID
时间
币种
方向
入场
止损
目标
退出
净 R
```

与 Freqtrade 一致。

### 3. Base Pass 字段内部不一致

最接近候选的：

```text
gates.basePassed = true
candidate_results.basePassed = false
```

推测顶层状态额外包含 Freqtrade Translation，但当前命名没有区分。

建议：

```text
numericBaseGatesPassed
implementationParityPassed
overallBasePassed
```

### 4. 正式数据来源 Gate 不足

当前正式 Gate 没有明确阻止：

- 来源未验证的 OHLCV；
- 跨交易所 Funding/价格；
- diagnostic PIT；
- 代理 Spread/清算。

即使本轮没有候选通过，未来也可能产生错误资格。应增加：

```text
formalDataProvenancePassed
sameExchangeAlignmentPassed
pitRequirementPassed
mechanismRequiredDataPassed
```

### 5. 缺少 MFE / MAE 与退出几何证据

证据包没有提供：

- MFE；
- MAE；
- 到达 0.5R / 1R / 1.5R / 2R 比例；
- 止损后恢复比例；
- 盈利后回落止损比例。

因此不能从本轮证明：

- 2R 目标太高；
- 止损太窄；
- 放宽止损能够改善策略。

---

## 七、关于固定 2R 和止损

本轮所有候选均使用 2R 或 2.2R，导致“信号机制”和“退出几何”被绑定，无法独立判断。

建议下一版改变原则：

> 初始止损在入场前冻结，入场后禁止放宽；退出逻辑必须与市场机制匹配，不再要求所有策略统一使用固定 2R。

机制匹配退出建议：

| 机制 | 更自然的退出 |
|---|---|
| 趋势 / 突破 | 1.5–2R、部分止盈、趋势尾仓 |
| 冲击回归 | 残差回归均值、时间退出、1–1.5R 分批 |
| Funding / Basis | Funding/Basis 正常化、时间窗口、结构失效 |
| 横截面组合 | 固定再平衡、排名跌出、Beta/组合风险退出 |

这不是降低门槛，而是修正“所有机制统一一个退出模型”的不合理假设。

---

## 八、第四阶段分析

第四阶段安全行为正确：

- 正式通过：0
- Release：0
- 导入：0
- 批准：0
- Runtime ARM：false
- 订单、成交、持仓、闭合交易：全部 0
- Live：false
- Withdraw：false
- 工程烟测未计入策略统计

它证明了：

```text
零 Release 安全关闭路径有效
```

但尚未证明：

```text
真实正式 Release
→ 导入
→ 批准
→ ARM
→ 策略 Demo 委托
→ 成交
→ 持仓
→ 退出
→ 对账
```

正向路径只能在未来出现正式通过策略后验证。

建议将当前 `strategyValidationDemo.status=collecting` 改成：

```text
idle_no_formal_release
```

更准确。

---

## 九、这次“0 个正式通过”真正说明什么

它说明：

```text
当前 8 币种
× 当前代理 OHLCV
× Binance Funding
× 3 个市场机制
× 6 个方向变体
× 固定 2R 退出
```

没有产生可正式晋级的策略。

它不说明：

```text
所有 Alpha191 因子无效
所有 Funding/OI/Basis 策略无效
所有横截面策略无效
所有加密市场 Alpha 不存在
```

因为：

- OI 未测试；
- Basis 未测试；
- 真实清算未测试；
- 正式 PIT 横截面未测试；
- 只有 8 个 Alpha191 因子；
- 因子没有进入策略候选；
- 只有 3 个机制；
- 没有真实 Freqtrade 翻译回测；
- 固定 2R 与机制绑定。

---

## 十、下一轮最值得研究的三个方向

### 方向一：4h 特异性抛售耗竭回归做多

不是复活当前版本，而是新机制：

```text
资产相对 BTC / 市场宽度出现极端负残差
+ OI 明显下降
+ 多头清算或清算代理达到极值
+ Funding / Basis 显示恐慌而非新增空头趋势
+ 价格重新收回事件区间
```

只做多，不做对称做空。

退出：

```text
残差回归中性
或 1R 部分止盈 + 时间退出
```

### 方向二：Funding + OI + Basis 空头拥挤解除做多

```text
极端负 Funding
+ OI 先扩张后收缩
+ 永续贴水
+ 价格停止创新低并回收
```

只做多。

当前 Funding-only 结果只是线索，必须使用同交易所数据重新建立。

### 方向三：PIT 高流动性横截面中期动量

以 Alpha088 作为研究种子，而不是直接策略：

```text
30–50 个历史 PIT 高流动性合约
按 20 日或等效经济时间动量排序
做多强势组
做空弱势组或控制 BTC Beta
固定周期再平衡
控制换手、Funding 和相关簇风险
```

退出使用再平衡和排名，不使用单币固定 2R。

### 后备方向：Basis / Funding 市场中性 Carry

只有 Basis 和真实费用数据就绪后再启用。

---

## 十一、下一步之前必须修复

1. 将 Feature Branch 合并或冻结 Tag。
2. 补充阶段 3A 外部参考与公式证据包。
3. 增加真实 Freqtrade Translation Parity。
4. 将 Walk-forward 与 Holdout 完全分开判定。
5. 增加 Holdout PF、平均净 R、总净 R、最低样本 Gate。
6. 增加正式数据来源和同交易所 Gate。
7. 获取 OI、Basis、真实或可靠清算、正式 PIT。
8. 扩大横截面至至少 30 个历史可交易币种。
9. 修复空的 universe split。
10. 把 FDR 正反方向合并为一个底层统计假设。
11. 增加 MFE / MAE 和退出几何报告。
12. 将机制匹配退出替代统一固定 2R。

---

## 十二、推荐下一任务

建议下一版不是直接“批量造更多策略”，而是：

```text
AlphaPilot 研究工厂方法修复、衍生品数据扩展与三方向新假设 Campaign
```

执行顺序：

```text
方法学修复
→ 同交易所 OI/Basis/清算/PIT 数据冻结
→ 三个新方向预注册
→ 事件路径与退出几何预筛
→ Freqtrade 一致性回测
→ 5 折
→ 独立 Holdout
→ 正式 Gate
```

这一轮最多三个家族，每个家族最多两个变体，不允许继续扩大搜索空间。
