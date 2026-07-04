# V13.4.9 Trend Pullback Expanded Validation Summary

## Decision

- isMock: False
- dryRunApproved: False
- passedExpandedGate: False
- nextStepRecommendation: V13.4.10 Trend Pullback Redesign Review

## Scope

- Strategy: AlphaPilot Trend Pullback 1H V0.1
- strategyId: alpha_trend_pullback_1h_v01
- Universe: fixed_top30
- Timeframe: 1h
- Timerange: 20260101-

## Raw Metrics

- tradeCount: 472
- totalReturnPct: -61.0503
- maxDrawdownPct: 67.296
- winRate: 31.5678
- profitFactor: 0.7067
- maxConsecutiveLosses: 13

## Slippage-Adjusted Metrics

- slippageAdjustedTotalReturnPct: -113.218
- slippageAdjustedProfitFactor: 0.5361
- maxDrawdownPct: 112.2244
- maxConsecutiveLosses: 13
- slippageCost: 521.67704423
- slippageAppliedByFreqtrade: False
- slippageAppliedByPostProcessing: True

## Supported Pairs

BTC/USDT:USDT, ETH/USDT:USDT, SOL/USDT:USDT, DOGE/USDT:USDT, XRP/USDT:USDT, ADA/USDT:USDT, AVAX/USDT:USDT, LINK/USDT:USDT, SUI/USDT:USDT, APT/USDT:USDT, OP/USDT:USDT, ARB/USDT:USDT, LTC/USDT:USDT, BCH/USDT:USDT, DOT/USDT:USDT, NEAR/USDT:USDT, PEPE/USDT:USDT, WIF/USDT:USDT, ORDI/USDT:USDT, INJ/USDT:USDT, FIL/USDT:USDT, ETC/USDT:USDT, TRX/USDT:USDT, UNI/USDT:USDT, AAVE/USDT:USDT, ATOM/USDT:USDT, SEI/USDT:USDT, TIA/USDT:USDT

## Excluded Pairs

- TON/USDT:USDT: not present in completed Freqtrade result; pair may be unsupported by exchange or absent in validated data
- FET/USDT:USDT: not present in completed Freqtrade result; pair may be unsupported by exchange or absent in validated data

## Quality Gate Checks

- slippageAdjustedTotalReturnPositive: False
- slippageAdjustedProfitFactorAbove115: False
- strictProfitFactorAbove120: False
- maxDrawdownBelow15: False
- maxConsecutiveLossesAtMost6: False
- tradeCountPresent: True
- largestPairNotDominant: True
- largestMonthNotDominant: True

## Warnings

- Some requested Top30 pairs were excluded or absent from completed result coverage.

## Safety

V13.4.9 is expanded validation only. It does not approve Dry-run, does not approve live trading, does not use API keys, does not call Trade API or Withdraw API, does not read accounts, does not create orders, and does not auto trade.
