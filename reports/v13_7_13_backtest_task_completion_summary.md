# AlphaPilot V13.7.13 Backtest Task Completion Report

V13.7.13 completes the six V13.7.12 `needs_backtest` research tasks with local evidence.

This is still research-only. It does not approve paper observation, exchange Dry-run, live trading, API keys, account reads, positions, orders, or automation.

## Summary

- status: `completed`
- completedTaskCount: `6`
- executableStrategyBacktestCount: `3`
- factorResearchOnlyCount: `3`
- paperOrShadowApprovedCount: `0`
- failedOrNotReadyCount: `6`
- dryRunApproved: `False`
- liveTradingApproved: `False`

## Decision

- allSixTasksTestedOrAudited: `True`
- anyCandidateApprovedForPaperObservation: `False`
- anyCandidateApprovedForExchangeDryRun: `False`
- reason: 补测完成，但没有一条通过 AlphaPilot 观察/模拟盘门槛；继续研究，不进入执行。

## Task Results

### 因子研究观察策略 - 手工因子库

- taskId: `v13_4_21_manual_factor_library_report__report_summary`
- completionStatus: `completed_research_data_generation`
- result: `not_executable_factor_library`
- executableStrategyBacktest: `False`
- paperOrShadowApproved: `False`
- finding: 手工因子库和 1h 28 币因子面板已重建，但它是研究数据层，不是可直接回测的入场/出场策略。
- nextAction: 仅可作为策略特征输入；需要先定义具体信号、持仓、退出和风控规则后再进入 Freqtrade 回测。
- evidence:
  - `reports/v13_7_13_manual_factor_library_report.json`
  - `reports/v13_7_13_factor_panel_report.json`

### 因子研究观察策略 - 因子面板

- taskId: `v13_4_21_factor_panel_report__report_summary`
- completionStatus: `completed_factor_panel_rebuild`
- result: `factor_panel_ready_for_evaluation`
- executableStrategyBacktest: `False`
- paperOrShadowApproved: `False`
- finding: 因子面板补测完成，覆盖 1h 28 币和 597046 行样本；没有伪造缺失数据。
- nextAction: 该面板可继续服务因子评价和机器学习筛选，但不直接产生交易候选。
- evidence:
  - `reports/v13_7_13_factor_panel_report.json`
  - `reports/v13_7_13_factor_panel_summary.md`

### 因子研究观察策略 - forward label 因子评价

- taskId: `v13_4_22_factor_evaluation_report__report_summary`
- completionStatus: `completed_factor_evaluation_no_candidate`
- result: `no_factor_candidate_passed_research_gate`
- executableStrategyBacktest: `False`
- paperOrShadowApproved: `False`
- finding: 16 个因子已用 596374 个有效标签重评估，但 candidateFactors=0；不应进入观察或模拟盘。
- nextAction: 保留为因子质量研究结果，后续优先研究组合因子或 regime 条件，不要单因子直接交易。
- evidence:
  - `reports/v13_7_13_factor_evaluation_report.json`
  - `reports/v13_7_13_factor_candidates.json`

### 衍生品 ML-gated 策略研究

- taskId: `v13_5_derivatives_ml_strategy_report__report_summary`
- completionStatus: `completed_broad_universe_walk_forward_failed`
- result: `failed_55pct_winrate_2r_gate`
- executableStrategyBacktest: `True`
- paperOrShadowApproved: `False`
- finding: 1h/4h 宽币种 walk-forward 补测均未通过。1h 最佳 gated PF=0.7525，4h 最佳 gated PF=0.4602。
- nextAction: 不要进入模拟盘；若继续研究，只能作为失败样本输入策略工厂，优先改变事件定义而不是调参追胜率。
- evidence:
  - `reports/v13_7_13_derivatives_ml_strategy_1h_broad_report.json`
  - `reports/v13_7_13_derivatives_ml_strategy_4h_broad_report.json`

### Adaptive ML 因子候选

- taskId: `v13_5_8_adaptive_ml_factor_report__report_summary`
- completionStatus: `completed_adaptive_ml_failed_watch_gate`
- result: `adaptive_ml_no_watch_candidate_passed`
- executableStrategyBacktest: `True`
- paperOrShadowApproved: `False`
- finding: 自适应 ML 重新计算完成，但 localPaperWatchApproved=false；2R 目标未放松。
- nextAction: 继续作为离线学习层，暂不进入前向观察、Dry-run 或实盘。
- evidence:
  - `reports/v13_7_13_adaptive_ml_factor_report.json`
  - `reports/v13_7_13_adaptive_ml_candidates.json`

### Alpha191 因子观察策略

- taskId: `v13_5_22_alpha191_factor_extraction_report__report_summary`
- completionStatus: `completed_with_existing_alpha191_subset_replay_failed`
- result: `alpha191_subset_replay_failed_all_gates`
- executableStrategyBacktest: `True`
- paperOrShadowApproved: `False`
- finding: Alpha191 元数据已提取，且后续 crypto-safe subset 已有 replay；raw、exit-aware、local-paper 三层 gate 均失败。
- nextAction: 保留为因子灵感库，不替代当前主候选；下一步应只选少量组合因子做新规格，而不是直接上线 Alpha191 子集。
- evidence:
  - `reports/v13_5_22_alpha191_factor_extraction_report.json`
  - `reports/v13_5_22_alpha191_factor_candidate_catalog.json`
  - `reports/v13_5_23_alpha191_crypto_subset_replay_report.json`

## Safety Boundary

- Public local data only.
- No Trade API.
- No Withdraw API.
- No API key storage.
- No real account reads.
- No real position reads.
- No order creation.
- No exchange Dry-run execution.
- No automatic trading.

Next step: Do not start paper/Dry-run from these six tasks. Use the failures to design stricter, lower-frequency or regime-aware candidates.
