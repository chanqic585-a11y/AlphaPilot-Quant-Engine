# AlphaPilot V13.4.20 Alpha Factor Research Summary

Status: design-only, research-only.

No trading strategy was written. No backtest was run. No Dry-run or live
trading approval was granted.

## Purpose

Design Alpha Factor Research Layer and Benchmark Suite

V13.4.20 replaces the previously considered probability-gate wiring step with
an Alpha Factor Research Layer and Benchmark Strategy Suite design. The reason
is that V13.4.19 coarse probability buckets are bucket-level approximations and
should not be promoted directly into strategy entry logic.

## Factor Data Panel

- panelId: factor_data_panel_v01
- primaryIndex: ['timestamp', 'pair']
- fieldCount: 19
- futureFieldCount: 7

## Operator Subset

- timeSeriesOperators: 10
- crossSectionalOperators: 5
- combinationOperators: 6
- excludedFamilies: genetic_programming, automatic_complex_expression_generation, deep_learning_factors, reinforcement_learning_factors

## Manual Factor Library V01

- factorCount: 16
- factors: momentum_3, momentum_12, reversal_3, volume_expansion_24h, volume_expansion_3d, distance_to_ema20, distance_to_ema50, bollinger_position, volatility_24h, volatility_3d, relative_strength_vs_btc, liquidity_rank, atr_pct, trend_strength, mean_reversion_distance, breakout_pressure

## Factor Evaluation

- metricCount: 14
- forwardWindowsBars: [4, 8, 12, 24]
- regimeSegments: ['trend', 'mean_reversion', 'breakout', 'avoid', 'unknown']
- universeSegments: ['BTC_ETH_SOL', 'DynamicTop10', 'DynamicTop15', 'Top30']

## Benchmark Strategy Suite

- benchmarkCount: 7
- benchmarks: benchmark_ema_trend, benchmark_rsi_mean_reversion, benchmark_macd_volume, benchmark_bollinger_rebound, benchmark_td9_exhaustion, benchmark_buy_and_hold_btc, benchmark_no_trade
- rejectedIdeas: martingale_inverse_averaging

## Strategy Research Factory

Workflow:

- generate_candidate_factors
- evaluate_factors
- filter_stable_factors
- combine_factors_into_strategy_hypotheses
- compare_against_benchmark_suite
- implement_freqtrade_strategy_only_after_research_pass
- run_smoke_and_expanded_validation
- keep_dry_run_approval_as_separate_review

## Safety Boundary

- dryRunApproved: False
- liveTradingApproved: False
- no external source code copied
- no API key
- no Trade API
- no Withdraw API
- no account or position reads
- no real orders
- no auto trading
- no backtest execution

## Next Step

V13.4.21 - Factor Data Panel and Manual Factor Library Implementation
