# AlphaPilot V13.4.18 Dynamic Regime Pipeline Diagnosis

Status: diagnosis only.

No backtest was run. No strategy rule, probability threshold, bucket table,
regime router, module rule, liquidity rule, Dry-run setting, API key, account
read, position read, order creation, or auto-trading path was changed.

## Signal Funnel

- Rows evaluated: 119679
- Rows with required data: 119166
- Trend module candidates: 598
- Mean-reversion module candidates: 1775
- Probability lookup hits: 62352
- Probability lookup misses: 57327
- Probability score pass: 0
- Final entry signals: 0
- Actual trades: 0

## Probability Gate

- Lookup hit rate: 52.0994%
- Probability pass rate: 0.0%
- Score table buckets: 283
- Sufficient sample buckets: 2
- Research candidate buckets: 0
- Current-gate pass buckets: 0

Top missing bucket keys from the expanded report:

- avoid_low_low_30-45_below_ema20_lower_weak: rows=6447
- avoid_low_low_below30_below_ema20_lower_weak: rows=4341
- avoid_low_low_55-65_near_ema20_middle_weak: rows=3097
- avoid_low_low_30-45_near_ema20_lower_weak: rows=3079
- avoid_low_low_above65_above_ema20_upper_weak: rows=2025
- avoid_low_low_45-55_below_ema20_lower_weak: rows=2012
- avoid_medium_low_30-45_below_ema20_lower_weak: rows=1269
- avoid_low_low_below30_below_ema20_outside_weak: rows=1022
- avoid_low_low_above65_near_ema20_middle_weak: rows=985
- avoid_medium_low_below30_below_ema20_lower_weak: rows=959

## Bucket Key Consistency

- Score table rebuild mismatches: 0
- Expanded buckets checked: 50
- Lookup hit buckets: 30
- Lookup missing buckets: 20
- Format mismatch count: 0
- Diagnosis: Bucket key format appears consistent; missing buckets are more consistent with probability table coverage gaps.

## Regime Router

- Trend rows: 17330 (14.4804%)
- Mean-reversion rows: 25212 (21.0664%)
- Avoid rows: 69483 (58.0578%)
- Unknown rows: 7654 (6.3954%)
- Diagnosis: Regime router produced eligible trend and mean-reversion rows, so it is not the immediate zero-signal blocker.

## Module Candidates

- Trend module candidate rate within trend: 3.4507%
- Mean-reversion candidate rate within mean-reversion: 7.0403%
- Diagnosis: Module rules produced candidates, but downstream probability scoring reduced final entries to zero.

## Liquidity Gate

- Liquidity data available: False
- Fallback used rows: 119679
- Effective rows after probability gate: 0
- Diagnosis: Liquidity gate is not the immediate blocker because no rows reached it after the probability gate.

## Root Cause Hypotheses

- probability_table_insufficient_coverage: high - Score table has 0 current-gate pass buckets and 0 research_candidate buckets.
- probability_gate_too_strict: medium - V13.4.17 has lookup hits but probabilityScorePass remains zero.

## Recommended Next Step

- Version: V13.4.19
- Name: Probability Bucket Coarsening and Sample Coverage Expansion
- Reason: Current probability table coverage has no current-gate pass buckets.

## Safety Boundary

- dryRunApproved: false
- liveTradingApproved: false
- This report is research-only and must not be treated as a trading command.
