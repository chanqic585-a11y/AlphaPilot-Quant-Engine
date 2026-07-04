# AlphaPilot V13.4.19 Probability Bucket Coarsening Summary

Status: research-only analysis.

No backtest was run. The original probability table and strategy code were not
modified. Coarsened tables are not wired to strategy entry, Dry-run, or live
execution.

## Original Probability Table

- sourceProbabilityTable: reports\v13_4_14_probability_score_table.json
- sourceDiagnosis: reports\v13_4_18_dynamic_regime_pipeline_diagnosis_report.json
- currentGatePassBucketCount: 0
- researchGatePassBucketCount: 0
- exploratoryGatePassBucketCount: 2

## Coarsening Schemes

- coarse_a_remove_time: buckets=283, sufficient=2, current=0, research=0, exploratory=2
- coarse_b_merge_rsi_ema_bb: buckets=145, sufficient=5, current=0, research=0, exploratory=6
- coarse_c_regime_liquidity_btc: buckets=27, sufficient=10, current=0, research=2, exploratory=8
- coarse_d_regime_module_volatility: buckets=22, sufficient=7, current=0, research=2, exploratory=5

## Top Research Buckets

- coarse_c_regime_liquidity_btc / trend_medium_safe: samples=79, pf=45.972475, expectancy=0.004643, tpProb=0.151899
- coarse_c_regime_liquidity_btc / avoid_low_weak: samples=57, pf=1.392737, expectancy=0.00198279, tpProb=0.087719
- coarse_d_regime_module_volatility / trend_trend_module_low_safe: samples=216, pf=17.370149, expectancy=0.00260509, tpProb=0.087963
- coarse_d_regime_module_volatility / unknown_no_entry_module_low_safe: samples=104, pf=2.16282, expectancy=0.00136352, tpProb=0.038462

## Root Cause Conclusion

A. probability_table_too_sparse

Evidence:

- Original current gate pass buckets: 0.
- Coarsened research gate pass buckets across schemes: 4.
- Coarsening reveals research candidates, so the original table is likely too fragmented.

## Recommended Next Step

V13.4.20 - Probability Gate Candidate Wiring and Backtest Plan

## Safety Boundary

- dryRunApproved: false
- liveTradingApproved: false
- researchGate is not used for trading.
- exploratoryGate is for analysis only.
- Do not connect coarsened tables to strategy entry without a separate backtest plan.
