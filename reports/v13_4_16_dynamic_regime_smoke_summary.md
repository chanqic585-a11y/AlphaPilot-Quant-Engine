# V13.4.16 Dynamic Regime Smoke Backtest Summary

## Status

- strategyId: alpha_dynamic_regime_v01
- isMock: false
- dryRunApproved: false
- liveTradingApproved: false
- timerange: 20260401-
- timeframe: 1h
- pairs: BTC/USDT:USDT, ETH/USDT:USDT, SOL/USDT:USDT
- backtestResultPath: user_data\backtest_results\backtest-result-2026-07-04_21-19-20.zip

## Metrics

- tradeCount: 0
- totalReturnPct: 0.0
- maxDrawdownPct: 0.0
- profitFactor: 0.0
- winRate: 0.0
- feesPaid: None
- averageHoldingMinutes: None

## Regime Breakdown

- avoid: 3627
- mean_reversion: 1534
- trend: 1174
- unknown: 496

## Module Breakdown

- trendModulePass: 51
- meanReversionModulePass: 163
- finalEntrySignals: 0
- skipReasons: {'avoid_regime': 3570, 'probability_score_not_passed': 2470, 'probability_score_unavailable': 710, 'data_missing': 57, 'not_in_dynamic_universe': 24}

## Probability Score Summary

- rowsEvaluated: 6831
- pass: 0
- fail: 6831
- source: reports/v13_4_14_probability_score_table.json

## Liquidity Gate Summary

- available: False
- fallbackUsedRows: 6831
- fallbackPolicy: allowed for smoke backtest research only; not a real liquidity approval

## Warnings

- none

## Safety

This is a local Freqtrade smoke backtest report only. It is not Dry-run approval and not live trading approval. No API key, Trade API, Withdraw API, account read, position read, order creation, or auto trading is used.
