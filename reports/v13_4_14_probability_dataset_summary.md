# V13.4.14 Probability Score Dataset Summary

## Build Status

- status: success
- inputUniverseSnapshots: reports\v13_4_13_dynamic_universe_snapshots.json
- snapshotCount: 155
- sampleCount: 1540
- labeledSampleCount: 1540
- insufficientDataCount: 10
- windows: 8, 12, 24
- primaryWindow: 12
- TP: 0.05
- SL: 0.025

## Probability Gate Summary

- totalBuckets: 283
- researchPromisingBuckets: 0
- observeOnlyBuckets: 2
- insufficientSampleBuckets: 281
- minimumSampleThreshold: 50
- passCriteria:
  - sampleCount: >= 50
  - hitTpBeforeSlProbability: >= 0.45
  - profitFactor: >= 1.2
  - expectancy: > 0
- decisionPolicy: insufficient samples remain observe_only and cannot approve Dry-run.

## Top Positive Buckets

- trend_medium_low_55-65_near_ema20_upper_weak: samples=2, tpProb=1.0, pf=None, expectancy=0.05
- avoid_high_low_55-65_near_ema20_middle_crash: samples=1, tpProb=1.0, pf=None, expectancy=0.05
- avoid_low_low_45-55_above_ema20_upper_weak: samples=1, tpProb=1.0, pf=None, expectancy=0.05
- avoid_low_low_45-55_near_ema20_lower_crash: samples=1, tpProb=1.0, pf=None, expectancy=0.05
- avoid_low_low_45-55_near_ema20_middle_crash: samples=1, tpProb=1.0, pf=None, expectancy=0.05
- avoid_low_medium_45-55_near_ema20_upper_weak: samples=1, tpProb=1.0, pf=None, expectancy=0.05
- avoid_medium_extreme_30-45_below_ema20_lower_safe: samples=1, tpProb=1.0, pf=None, expectancy=0.05
- trend_low_high_above65_extended_above_ema20_upper_safe: samples=1, tpProb=1.0, pf=None, expectancy=0.05
- trend_low_medium_55-65_above_ema20_upper_weak: samples=1, tpProb=1.0, pf=None, expectancy=0.05
- trend_low_medium_55-65_extended_above_ema20_upper_weak: samples=1, tpProb=1.0, pf=None, expectancy=0.05

## Top Negative Buckets

- mean_reversion_medium_low_below30_below_ema20_outside_weak: samples=3, tpProb=0.0, pf=0.0, expectancy=-0.025
- trend_medium_medium_55-65_above_ema20_middle_safe: samples=3, tpProb=0.0, pf=0.0, expectancy=-0.025
- avoid_high_low_55-65_above_ema20_middle_weak: samples=2, tpProb=0.0, pf=0.0, expectancy=-0.025
- avoid_medium_medium_45-55_below_ema20_lower_crash: samples=2, tpProb=0.0, pf=0.0, expectancy=-0.025
- avoid_medium_medium_55-65_above_ema20_middle_weak: samples=2, tpProb=0.0, pf=0.0, expectancy=-0.025
- unknown_low_medium_55-65_above_ema20_upper_weak: samples=2, tpProb=0.0, pf=0.0, expectancy=-0.025
- avoid_high_extreme_above65_extended_above_ema20_upper_safe: samples=1, tpProb=0.0, pf=0.0, expectancy=-0.025
- avoid_high_low_30-45_below_ema20_lower_crash: samples=1, tpProb=0.0, pf=0.0, expectancy=-0.025
- avoid_high_medium_45-55_near_ema20_middle_weak: samples=1, tpProb=0.0, pf=0.0, expectancy=-0.025
- avoid_low_medium_55-65_above_ema20_upper_weak: samples=1, tpProb=0.0, pf=0.0, expectancy=-0.025

## Insufficient Sample Buckets

- mean_reversion_high_low_30-45_below_ema20_lower_weak: samples=47
- mean_reversion_low_low_45-55_near_ema20_lower_weak: samples=36
- mean_reversion_low_low_30-45_below_ema20_lower_safe: samples=31
- avoid_medium_low_45-55_near_ema20_middle_weak: samples=30
- mean_reversion_low_low_45-55_near_ema20_lower_safe: samples=30
- mean_reversion_medium_low_45-55_near_ema20_lower_weak: samples=30
- trend_high_low_55-65_near_ema20_middle_safe: samples=30
- avoid_low_low_45-55_near_ema20_middle_weak: samples=29
- mean_reversion_medium_medium_30-45_below_ema20_lower_weak: samples=28
- mean_reversion_medium_low_30-45_below_ema20_lower_safe: samples=27

## No-Lookahead Rules

- Universe snapshots are read from V13.4.13 and were built with candles closed before snapshotDate 00:00 UTC.
- Sample features use only the current candle and rolling indicators calculated from current and prior candles.
- Forward windows are used only for labels: hitTpBeforeSl, hitSlBeforeTp, MFE, MAE, and future return.
- Forward label values are not written back into feature buckets.
- Missing current or future candles are counted as insufficient data instead of being filled with fake values.

## Outputs

- report: reports\v13_4_14_probability_dataset_report.json
- probabilityScoreTable: reports\v13_4_14_probability_score_table.json
- sampleDataset: reports\v13_4_14_probability_sample_dataset.json
- bucketRows: 283

## Warnings

- ADA/USDT:USDT: insufficient_future_window: 1
- BCH/USDT:USDT: insufficient_future_window: 1
- BTC/USDT:USDT: insufficient_future_window: 1
- DOGE/USDT:USDT: insufficient_future_window: 1
- ETH/USDT:USDT: insufficient_future_window: 1
- NEAR/USDT:USDT: insufficient_future_window: 1
- PEPE/USDT:USDT: insufficient_future_window: 1
- SOL/USDT:USDT: insufficient_future_window: 1
- SUI/USDT:USDT: insufficient_future_window: 1
- XRP/USDT:USDT: insufficient_future_window: 1

## Safety

V13.4.14 reads local public OHLCV and historical universe snapshots only. It does not implement a strategy, run a backtest, enter Dry-run, use API keys, call Trade API or Withdraw API, read accounts, read positions, create orders, or auto trade.

Next step: V13.4.15 - Dynamic Regime Strategy V0.1 Implementation
