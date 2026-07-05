# AlphaPilot V13.4.25 Strategy Research Factory Summary

Status: research-only hypothesis mining.

V13.4.25 reads V13.4.22 factor evaluation, V13.4.23 benchmark suite results,
and V13.4.24 benchmark failure review. It converts that evidence into a
Strategy Research Factory hypothesis registry.

No strategy code was written. No Freqtrade backtest was run. No Dry-run or live
trading approval was granted.

## Inputs

- reports/v13_4_22_factor_evaluation_report.json
- reports/v13_4_22_factor_candidates.json
- reports/v13_4_23_benchmark_suite_report.json
- reports/v13_4_24_benchmark_result_review.json
- reports/v13_4_24_benchmark_status_archive.json

## Hypothesis Counts

- total: 14

By category:

- benchmark_informed: 2
- execution_reality: 3
- factor_based: 3
- regime_based: 2
- rejected: 4

By status:

- deferred: 1
- rejected: 4
- research_only: 9

By priority:

- high: 6
- low: 4
- medium: 4

## High Priority Hypotheses

HYP-001, HYP-002, HYP-004, HYP-006, HYP-007, HYP-008

## Rejected Hypotheses

HYP-R01, HYP-R02, HYP-R03, HYP-R04

## Hypothesis Registry

- HYP-001 | Volatility as Risk Filter | factor_based | research_only | priority=high
- HYP-002 | Trend Strength as Regime Filter | regime_based | research_only | priority=high
- HYP-003 | EMA50 Distance as Pullback Context | factor_based | research_only | priority=medium
- HYP-004 | Bollinger Rebound Requires Regime Filter | benchmark_informed | research_only | priority=high
- HYP-005 | Activity / Volume Expansion as Universe Filter | factor_based | research_only | priority=medium
- HYP-006 | Low Frequency Requirement | execution_reality | research_only | priority=high
- HYP-007 | Liquidity Gate First | execution_reality | research_only | priority=high
- HYP-008 | BuyHoldBTC Benchmark Requirement | benchmark_informed | research_only | priority=high
- HYP-009 | Regime Router Before Rule Family | regime_based | research_only | priority=medium
- HYP-010 | Dynamic Universe Quality Narrowing | execution_reality | deferred | priority=medium
- HYP-R01 | Martingale Rejected | rejected | rejected | priority=low
- HYP-R02 | RSI Only Rejected | rejected | rejected | priority=low
- HYP-R03 | Simple EMA Cross Rejected | rejected | rejected | priority=low
- HYP-R04 | MACD Volume Only Rejected | rejected | rejected | priority=low

## Next Experiment Plan

- versionName: V13.4.26 - Factor Hypothesis Validation Dataset
- goal: Build a validation dataset for the highest-priority research hypotheses before any strategy implementation.

Scope:

- materialize hypothesis validation rows from FactorDataPanel and benchmark reports
- segment by volatility, trend strength, EMA50 distance, Bollinger position, volume expansion, and liquidity context
- compare all candidate contexts against NoTrade, BuyHoldBTC, and BenchmarkBollingerRebound after costs
- record invalidated and deferred hypotheses explicitly

Non-goals:

- no Freqtrade strategy implementation
- no new backtest execution
- no Dry-run
- no Trade API or Withdraw API
- no account or position read
- no order creation
- no auto trading

## Safety Boundary

- dryRunApproved: False
- liveTradingApproved: False
- no strategy code written
- no backtest execution
- no Dry-run
- no Trade API
- no Withdraw API
- no API key
- no account or position reads
- no order creation
- no auto trading

## Outputs

- reports/v13_4_25_strategy_research_factory_report.json
- reports/v13_4_25_strategy_research_factory_summary.md
- reports/v13_4_25_research_hypotheses.json
