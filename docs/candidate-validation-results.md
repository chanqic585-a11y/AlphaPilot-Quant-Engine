# Candidate Validation Results

## 结论

- 候选版本：8
- 去重后策略家族：7
- 重复版本：1
- 硬通过：0
- 继续归档：7
- 新版本建议：0

当前风险模型候选全部继续归档。停止从旧归档库复活策略。下一步转向新的、独立且可证伪的数据假设，或只继续积累真正未查看的本地前向样本。

## 家族结果

| 队列 | 候选 | 结论 | 关键原因 |
| --- | --- | --- | --- |
| A | 1H 深弱势扫低收回，因子后继 ATR1.2 | 锁定样本不可用 | 诊断信号、成本和主风险模型通过，但稳定性失败，锁定区已被选择流程查看 |
| A | 1D 广谱压缩释放 ATR2.0 | 锁定样本不可用 | 信号和稳定性失败；有效锁定样本不足；无 point-in-time 宇宙 |
| A | 1D 趋势压缩释放 ATR2.0 | 锁定样本不可用 | 信号、锁定表现和稳定性失败；有效锁定样本不足 |
| A | 1D 趋势突破回踩 ATR2.0 | 锁定样本不可用 | 锁定 PF 约 0.39、平均净 R 约 -0.45；无干净锁定样本 |
| B | 1H 突破回踩 BTC 顺势确认，因子后继 ATR1.2 | 锁定样本不可用 | 1.5x 成本、锁定表现和稳定性失败 |
| C | 15m 假突破弱趋势反转，因子后继 ATR1.2 | 预筛选停止 | 历史 PF/平均净 R 未达到 C 级预筛条件 |
| C | 1D 超卖扫低收回 ATR1.2 影子 | 预筛选停止 | 历史 PF/平均净 R 未达到 C 级预筛条件 |

表现最接近的 1H 深弱势扫低收回候选，在非锁定信号层 PF 约 1.35、平均净 R 约 0.20，1.5x 成本 PF 约 1.28，主风险模型最大回撤约 8.57%。但其锁定诊断 PF 仅约 1.003、平均净 R 约 0.002，且缺少真正未查看的 point-in-time 锁定证据，因此不能晋级。

## 审计产物

- 主报告：`reports/candidate_evidence_closure_report.json`
- 摘要：`reports/candidate_evidence_closure_summary.md`
- 排行表：`reports/candidate_evidence_closure_leaderboard.csv`
- 数据清单：`reports/candidate_validation_data_manifest.json`
- 逐笔证据：`reports/generated/candidate_validation_trade_rows.jsonl`
- Monte Carlo 抽样：`reports/generated/candidate_validation_monte_carlo_samples.jsonl`

大体积 JSONL 默认不进 Git；其哈希、行数和样本保存在数据清单中。该结果不是执行批准，未进入 Dry-run、Demo 或实盘。
