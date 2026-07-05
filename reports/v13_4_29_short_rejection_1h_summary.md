# AlphaPilot V13.4.29 Short Rejection 1H Research Report

Status: completed

V13.4.29 adds a short-only 1h rejection research strategy and reports local
Freqtrade backtest results. It does not enter Dry-run, live trading, private
exchange APIs, account reads, position reads, order creation, or auto trading.

## Strategy

- strategyId: alpha_short_rejection_1h_v01
- strategyName: AlphaPilot Short Rejection 1H V0.1
- timeframe: 1h
- direction: short_only
- primaryRunScope: expanded
- isMock: False

## Primary Metrics

- pairs: BTC/USDT:USDT, ETH/USDT:USDT, SOL/USDT:USDT, DOGE/USDT:USDT, XRP/USDT:USDT, ADA/USDT:USDT, AVAX/USDT:USDT, LINK/USDT:USDT, SUI/USDT:USDT, APT/USDT:USDT, OP/USDT:USDT, ARB/USDT:USDT, LTC/USDT:USDT, BCH/USDT:USDT, DOT/USDT:USDT, NEAR/USDT:USDT, PEPE/USDT:USDT, WIF/USDT:USDT, ORDI/USDT:USDT, INJ/USDT:USDT, FIL/USDT:USDT, ETC/USDT:USDT, TRX/USDT:USDT, UNI/USDT:USDT, AAVE/USDT:USDT, ATOM/USDT:USDT, SEI/USDT:USDT, TIA/USDT:USDT
- timerange: 20260101-
- tradeCount: 5052
- shortTradeCount: 5052
- totalReturnPct: -99.9966
- slippageAdjustedTotalReturnPct: -217.1225
- maxDrawdownPct: 99.9966
- profitFactor: 0.782
- slippageAdjustedProfitFactor: 0.5966
- winRate: 29.711
- maxConsecutiveLosses: 77

## Scope Decisions

- excludedPairs: FET/USDT:USDT, TON/USDT:USDT
- watchlistPairs: ORDI/USDT:USDT
- smokeBacktestSucceeded: True
- expandedBacktestSucceeded: True
- expandedFailed: False

## Research Gate

```json
{
  "researchWorthContinuing": false,
  "reason": "criteria_not_met",
  "topPairTradeShare": 0.0901,
  "criteria": {
    "slippageAdjustedProfitFactorGt105": false,
    "tradeCountAtLeast20": true,
    "maxDrawdownAcceptable": false,
    "maxConsecutiveLossesAcceptable": false,
    "noSinglePairDominates": true
  },
  "dryRunApproved": false
}
```

The research gate may decide whether this idea is worth further research, but
it does not approve Dry-run or live trading.

## Exit Reason Breakdown

- roi: trades=1395 profit_total_pct=353.66
- profitable_short_momentum_exit: trades=106 profit_total_pct=5.11
- short_time_stop_8h_not_profitable: trades=19 profit_total_pct=-1.98
- stop_loss: trades=3532 profit_total_pct=-456.78
- TOTAL: trades=5052 profit_total_pct=-100.0

## Safety Boundary

- dryRunApproved: False
- liveTradingApproved: False
- slippageAppliedByFreqtrade: False
- slippageAppliedByPostProcessing: True
- no Trade API
- no Withdraw API
- no real API key storage
- no account or position reads
- no order creation
- no auto trading

Warnings:

- Research gate failed; this short-only idea is not approved for continuation without redesign.
