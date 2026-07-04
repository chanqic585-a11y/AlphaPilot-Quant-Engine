# AlphaPilot V13.4.20 Probability Gate Candidate Summary

Status: research-only candidate wiring plan.

No backtest was run. Default probability gate and strategy code were not
modified. Candidate configs are not wired to Dry-run or live trading.

## Candidate Gates

- probability_gate_c1_trend_medium_safe: allowed=trend_medium_safe; matchedBuckets=1; status=research_only; useForDryRun=False; useForTrading=False
- probability_gate_cd_trend_research_combined: allowed=trend_medium_safe, trend_trend_module_low_safe; matchedBuckets=2; status=research_only; useForDryRun=False; useForTrading=False
- probability_gate_d1_trend_module_low_safe: allowed=trend_trend_module_low_safe; matchedBuckets=1; status=research_only; useForDryRun=False; useForTrading=False

## Rejected Diagnostic Buckets

- avoid_low_weak: diagnostic_only; entryAllowed=False; reason=avoid regime cannot be promoted to entry candidate from bucket-level PF.
- unknown_no_entry_module_low_safe: diagnostic_only; entryAllowed=False; reason=unknown regime or no_entry module cannot become an entry candidate.

## V13.4.21 Backtest Plan

Comparison variants:

- baseline_dynamic_regime_current_gate: Existing AlphaPilotDynamicRegimeV01 current probability gate.
- probability_gate_c1_trend_medium_safe: Research-only candidate gate configuration for comparison backtest.
- probability_gate_cd_trend_research_combined: Research-only candidate gate configuration for comparison backtest.
- probability_gate_d1_trend_module_low_safe: Research-only candidate gate configuration for comparison backtest.

Scopes:

- smoke: pairs=['BTC/USDT:USDT', 'ETH/USDT:USDT', 'SOL/USDT:USDT']; timerange=20260401-; timeframe=1h
- expanded_dynamic_universe: pairs=historical dynamic universe selectedPairs union; timerange=20260101-; timeframe=1h

## Safety Boundary

- useForTrading: false
- useForDryRun: false
- modifiesDefaultProbabilityGate: false
- modifiesStrategyCode: false
- runsBacktest: false
- recommendedNextStep: V13.4.21 - Probability Gate Candidate Backtest
