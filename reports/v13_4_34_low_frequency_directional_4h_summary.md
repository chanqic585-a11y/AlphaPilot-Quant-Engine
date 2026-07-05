# AlphaPilot V13.4.34 Low-Frequency Directional 4H Research Report

This report summarizes a real local Freqtrade research backtest when available. It is not Dry-run, not live trading, and not a trading command.

## Run Summary

- isMock: False
- strategy: AlphaPilotLowFrequencyDirectional4HV01
- result file: user_data/backtest_results/v13_4_34_low_frequency_directional_4h.zip
- pairs: BTC/USDT:USDT, ETH/USDT:USDT, SOL/USDT:USDT
- timeframe: 4h
- timerange: 20240101-
- tradeCount: 2821
- longTradeCount: 1312
- shortTradeCount: 1509
- totalReturnPct: -99.9659
- slippageAdjustedTotalReturnPct: -150.0949
- maxDrawdownPct: 99.9676
- profitFactor: 0.6099439331834487
- slippageAdjustedProfitFactor: 0.4877
- winRate: 28.0752
- researchWorthContinuing: False

## Direction Metrics

| Direction | Trades | Return % | Win Rate % | Profit Factor | Avg Duration Min | Max Consecutive Losses |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| long | 1312 | -54.2218 | 27.1341 | 0.6461 | 72.439 | 24 |
| short | 1509 | -45.7441 | 28.8933 | 0.5561 | 61.7097 | 22 |

## Pair Performance

| Pair | Trades | Profit % | Profit Abs | Wins | Drawdown % |
| --- | ---: | ---: | ---: | ---: | ---: |
| ETH/USDT:USDT | 911 | -23.58 | -235.79999764 | 258 | None |
| BTC/USDT:USDT | 585 | -27.41 | -274.06372877 | 189 | None |
| SOL/USDT:USDT | 1325 | -48.98 | -489.79546123000006 | 345 | None |
| TOTAL | 2821 | -99.97 | -999.6591876399999 | 792 | None |

## Baseline Comparison

- excessReturnVsNoTradePct: -99.9659
- excessReturnVsEqualWeightPct: -102.4713
- drawdownDifferenceVsEqualWeightPct: 37.0113

## Regime Breakdown

| Regime | Trades | Long | Short | Return % | Win Rate % | Profit Factor |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| bear | 108 | 27 | 81 | -0.0175 | 25.9259 | 0.6087 |
| bull | 5 | 4 | 1 | -0.0014 | 20.0 | 0.431 |
| high_volatility | 4 | 1 | 3 | -0.0007 | 25.0 | 0.58 |
| sideways | 10 | 4 | 6 | -0.0041 | 10.0 | 0.1739 |
| unknown | 2694 | 1276 | 1418 | -99.9422 | 28.248 | 0.61 |

## Research Decision Reasons

- Trade count is large enough for a first research read.
- 0.05% one-way slippage-adjusted return is not positive.
- 0.05% one-way slippage-adjusted profit factor is not above 1.05.
- Max drawdown is high for a low-frequency research candidate.
- Raw return does not beat NoTrade.
- Raw return does not beat EqualWeight BTC/ETH/SOL baseline.

## Safety Boundary

- strategyImplemented: True
- freqtradeBacktestExecuted: True
- dryRunApproved: False
- liveTradingApproved: False
- tradeApiUsed: False
- withdrawApiUsed: False
- apiKeyStored: False
- accountRead: False
- positionRead: False
- orderCreated: False
- autoTradingUsed: False
