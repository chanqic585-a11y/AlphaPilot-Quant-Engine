# 归档失败策略归因摘要

生成时间：`2026-07-14T23:36:19.048078+00:00`

## 结论

- 共分析 **13** 条失败、拒绝或负向研究记录，来自 **3** 个策略家族。
- Dry-run 获批：**0**；实盘获批：**0**。
- 本报告只读取已有证据；没有修改策略、调参、启动回测、访问交易所或改变 Demo/实盘状态。
- 缺失指标保持 `null`。归因是证据分类，不代表证明了唯一因果关系。

## 跨策略模式

| 失败类型 | 角色 | 策略数 |
| --- | --- | ---: |
| signal_edge_failure | primary | 12 |
| rejected_risk_design | primary | 1 |
| data_evidence_gap | secondary | 13 |
| cost_amplification | secondary | 10 |
| risk_model_failure | secondary | 10 |
| overtrading | secondary | 9 |

## 严重失败记录

- `alpha_short_rejection_1h_v01`: signal_edge_failure
- `alpha_volume_rebound_v01`: signal_edge_failure
- `alpha_volume_rebound_v02_b_volume_quality`: signal_edge_failure
- `alpha_volume_rebound_v02_c_exit_cleanup`: signal_edge_failure
- `alpha_volume_rebound_v02_e_pair_risk_watchlist`: signal_edge_failure
- `benchmark_bollinger_rebound`: signal_edge_failure
- `benchmark_ema_trend`: signal_edge_failure
- `benchmark_macd_volume`: signal_edge_failure
- `benchmark_rsi_mean_reversion`: signal_edge_failure
- `benchmark_td9_exhaustion`: signal_edge_failure
- `rejected_benchmark_martingale`: rejected_risk_design

## 研究边界

1. 归档策略只能作为负向研究资产，不能直接恢复为可执行候选。
2. 结构性信号失败必须创建新版本和新假设，不能靠小幅调参覆盖。
3. 信号层与账户/风险层必须分别通过。
4. 任何复活候选都要重新经过成本压力、留出集和 Walk-forward 证据。

## 输出

- `reports/archived_failed_strategy_inventory.json`
- `reports/archived_failed_strategy_metrics_matrix.json`
- `reports/archived_failed_strategy_failure_attribution.json`
- `reports/archived_failed_strategy_negative_rules.json`
- `reports/archived_failed_strategy_reusable_components.json`
- `reports/archived_failed_strategy_revival_candidates.json`
- `reports/archived_failed_strategy_metrics_matrix.csv`
- `reports/archived_failed_strategy_failure_attribution.csv`
