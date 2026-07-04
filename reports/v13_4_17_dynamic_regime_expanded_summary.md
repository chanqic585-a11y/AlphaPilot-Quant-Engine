# V13.4.17 Dynamic Regime Expanded Validation Summary

## Status

- strategyId: alpha_dynamic_regime_v01
- isMock: false
- dryRunApproved: false
- liveTradingApproved: false
- timerange: 20260101-
- timeframe: 1h
- pairCount: 27
- backtestResultPath: user_data\backtest_results\backtest-result-2026-07-04_21-28-28.zip

## Raw Metrics

- tradeCount: 0
- totalReturnPct: 0.0
- maxDrawdownPct: 0.0
- profitFactor: 0.0
- winRate: 0.0
- maxConsecutiveLosses: 0
- feesPaid: None
- averageHoldingMinutes: None
- slippageAppliedByFreqtrade: False
- slippageAppliedByPostProcessing: False

## Slippage Stress

| One-way slippage | Adj return % | Adj PF | Drawdown % | Trades | Max loss streak | Slippage cost |
|---:|---:|---:|---:|---:|---:|---:|
| 0.0005 | 0.0 | None | 0.0 | 0 | 0 | 0.0 |
| 0.001 | 0.0 | None | 0.0 | 0 | 0 | 0.0 |
| 0.002 | 0.0 | None | 0.0 | 0 | 0 | 0.0 |
| 0.003 | 0.0 | None | 0.0 | 0 | 0 | 0.0 |

## Quality Gate

- passed: False
- reason: trade_count_not_meaningful
- reason: slippage_adjusted_return_not_positive
- reason: slippage_adjusted_profit_factor_not_above_1_15

## Regime Breakdown

- avoid: 69483
- mean_reversion: 25212
- trend: 17330
- unknown: 7654

## Module Breakdown

- trendModulePass: 598
- meanReversionModulePass: 1775
- finalEntrySignals: 0
- skipReasons: {'not_in_dynamic_universe': 82031, 'avoid_regime': 21716, 'probability_score_not_passed': 12469, 'probability_score_unavailable': 2950, 'data_missing': 513}

## Probability Score Summary

- rowsEvaluated: 119679
- available: 62352
- pass: 0
- fail: 119679
- source: reports\v13_4_14_probability_score_table.json

## Liquidity Gate Summary

- available: False
- fallbackUsedRows: 119679
- fallbackPolicy: allowed for expanded validation research only; not a real liquidity approval

## Dynamic Universe

- source: reports\v13_4_13_dynamic_universe_snapshots.json
- snapshotCount: 155
- pairUnionCount: 27
- pairsMode: historical_dynamic_universe_union_for_backtest_with_strategy_date_filter
- note: Backtest pair list is the union of historical selectedPairs; strategy still filters rows by snapshot date.

## Warnings

- none

## Safety

This is a local expanded validation report only. It is not Dry-run approval and not live trading approval. No API key, Trade API, Withdraw API, account read, position read, order creation, or auto trading is used.
